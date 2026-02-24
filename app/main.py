import sys
import pyautogui
import os
import json
import time
import uuid
import traceback
import shutil
import re
import copy
import threading
import datetime
from dataclasses import fields
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog, 
    QMessageBox, QCheckBox, QSpinBox, QDoubleSpinBox, QGroupBox, 
    QFormLayout, QPlainTextEdit, QTabWidget, QGridLayout, QAction,
    QMenu, QMenuBar, QShortcut, QInputDialog, QTimeEdit, QTableWidget, QTableWidgetItem,
    QDialog, QLineEdit, QComboBox, QProgressBar, QScrollArea, QSizePolicy, QFrame, QToolTip
)
from PyQt5.QtCore import Qt, QTimer, QSettings, QSize, QEventLoop, QRect, QTime, QStandardPaths, pyqtSignal, QPoint
from PyQt5.QtGui import QKeySequence, QIcon, QPixmap, QPainter, QColor, QFont, QCursor, QImage

from .ui.dialogs import (
    ImageStepDialog, NotImageDialog, BranchStepDialog, TargetDialog,
    RecordingSettingsDialog, ConditionalActionWizardDialog
)
from .ui.tabs.manager_tab import ManagerTab
from .core.models import TriggerData, StepData, RepeatConfig
from .core.runner import MacroRunner
from .core.recorder import InputRecorder
from .core.trigger_engine import TriggerWatcher
from .core.config import ConfigManager
from .core.scheduler import MacroScheduler
from .core.window_manager import WindowManager
from .core.commands import (
    UndoStack,
    AddStepCommand,
    AddStepsCommand,
    RemoveStepCommand,
    EditStepCommand,
    MoveStepCommand,
    ReorderStepsCommand,
)
from .ui.trigger_dialog import TriggerEditDialog
from .ui.hotkeys import SystemHotkeys, HotkeySettingsDialog
from .ui.widgets import StepList
from .ui.styles import DarkTheme
from .ui.selectors import ROISelector, CrosshairOverlay
from .ui.overlay import VisualImageCaptureOverlay, CoordinateGuideOverlay
from .ui.debug_overlay import DebugOverlay
from .ui.window_selector import WindowSelectorDialog
from .ui.scenario_wizard import ScenarioWizardDialog
from .ui.history_viewer import ExecutionHistoryDialog
from .io.macro_io import MacroIO
from .utils.common import hk_pretty, hk_to_tuple, hk_normalize, encode_png_bytes
from .utils.logging_setup import setup_file_logger
from .utils.runtime_paths import get_resource_path
from .core.ocr_runtime import configure_tesseract_cmd, get_tesseract_status, save_tesseract_cmd_to_settings
from .core.data_orchestration import JobQueueManager
from .core.session_adapter import SessionJobAdapter
from .core.excel_io import ExcelDataLoader, ExcelResultExporter
from .core.template_processor import TemplateProcessor
from .core.input_lock import get_global_input_manager
from .core.evaluator import ConditionEvaluator
from .core.logic_path_simulator import LogicPathSimulator

def _excepthook(type, value, tback):
    sys.__excepthook__(type, value, tback)
    traceback.print_exception(type, value, tback)


class ElidedPathLineEdit(QLineEdit):
    """Read-only path field that shows an elided label while preserving full text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""

    def setText(self, text: str):  # type: ignore[override]
        self._full_text = str(text or "")
        self._apply_elide()

    def text(self) -> str:  # type: ignore[override]
        return self._full_text

    def clear(self):  # type: ignore[override]
        self._full_text = ""
        super().setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self):
        if not self._full_text:
            super().setText("")
            return
        width = max(20, self.contentsRect().width() - 6)
        shown = self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, width)
        super().setText(shown)


class MainWindow(QMainWindow):
    excelOrchEvent = pyqtSignal(dict)
    excelOrchFinished = pyqtSignal(bool, str)
    # Scheduler constants
    SCHED_KEY_TIME = "scheduler/time"
    SCHED_KEY_MACROS = "scheduler/macros"
    SCHED_KEY_ENABLED = "scheduler/enabled"
    SCHED_KEY_FAILURE_POLICY = "scheduler/failure_policy"
    SCHED_KEY_MAX_RETRIES = "scheduler/max_retries"
    SCHED_KEY_RETRY_DELAY_MS = "scheduler/retry_delay_ms"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")
        self.resize(1200, 760)
        
        # Apply Dark Theme
        self.setStyleSheet(DarkTheme.get_stylesheet())
        
        self.steps: list[StepData] = []
        self._active_step_index: int | None = None
        self._last_failed_step_index: int | None = None
        self._last_failed_step_uuid: str | None = None
        self.runner: MacroRunner | None = None
        self.recorder: InputRecorder | None = None
        self._current_macro_path: str | None = None
        self._resume_state: dict | None = None
        self._resume_index: int = 0
        self._main_runner_paused: bool = False
        self._paused_runner: MacroRunner | None = None
        self.trigger_runner: MacroRunner | None = None
        self._excel_mode_running: bool = False
        self._excel_input_path: str = ""
        self._excel_output_path: str = ""
        self._excel_job_manager: JobQueueManager | None = None
        self._excel_adapters: list[SessionJobAdapter] = []
        self._excel_stop_event: threading.Event = threading.Event()
        self._excel_monitor_thread: threading.Thread | None = None
        self._excel_total_jobs: int = 0
        self._excel_payload_by_job_id: dict[str, dict] = {}
        self._excel_preview_cache_path: str = ""
        self._excel_preview_payload: dict = {}
        self._flow_preview_cache: dict[tuple, list[tuple[int, int, str, str]]] = {}
        self._flow_preview_active: bool = False
        self._simulated_indices: set[int] = set()
        self._smart_snap_enabled_default: bool = True
        self._macro_paused_ui: bool = False
        self._record_show_summary = False
        self._was_minimized = False
        self._live_overlays: list[CrosshairOverlay] = []
        trigger_start_log = os.environ.get("IMAGEMACRO_TRIGGER_START_LOG", "")
        self._show_trigger_start_log = str(trigger_start_log).strip().lower() in ("1", "true", "yes", "on")
        self.config = ConfigManager()
        self._load_record_settings()
        
        # Hotkey state
        self._hk_run = "end"
        self._hk_stop = "home"
        self._hk_record = "f9"
        self._hk_add_img = "ctrl+shift+i"
        self._hk_add_notimg = "ctrl+shift+n"
        self._hk_pause = "f10"
        self._hk_kill = "f12"
        self._mods_global = set()
        self._qshortcuts: list[QShortcut] = []
        self._hotkey_dialog_open = False
        self._load_hotkeys()
        self._preset_dir = self._compute_preset_dir()
        self._sched_running = False
        self._sched_ran_today = False
        self.undo_stack = UndoStack()
        self._file_logger = setup_file_logger("Macro")
        self.debug_overlay = DebugOverlay()
        self.debug_overlay.hide()
        self.window_manager = WindowManager()
        self.target_hwnd = None
        self._coordinate_overlay = None
        self._coordinate_preview_suspended = False
        self._coordinate_image_size_cache = {}
        
        # System Hotkeys
        self._system_hotkeys = SystemHotkeys(self)
        
        # Scheduler
        self.scheduler = MacroScheduler(self)
        self.scheduler.log.connect(self.info)
        self.scheduler.statusChanged.connect(self._on_scheduler_status_changed)
        self.scheduler.requestRunMacro.connect(self._run_scheduled_macro)


        self.list = StepList(self)
        self.list.orderChanged.connect(self.sync_order)
        self.list.itemSelectionChanged.connect(self.update_preview)
        self.list.requestRunFrom.connect(self.run_from_index)
        self.list.requestEdit.connect(self.edit_step_at)
        self.list.requestConvertToBranch.connect(self.convert_to_branch_step)
        self.list.requestDuplicate.connect(self.duplicate_step_at)
        self.list.requestDuplicateMany.connect(self.duplicate_steps_at)
        self.list.requestDelete.connect(self.delete_step_at)
        self.list.requestDeleteMany.connect(self.delete_steps_at)
        self.list.requestRename.connect(self.rename_step_at)
        self.list.itemChanged.connect(self._on_list_item_renamed)
        self.list.flowPreviewRequested.connect(self._on_flow_preview_requested)
        self.list.coordinatePreviewRequested.connect(self._on_coordinate_preview_requested)
        self.list.coordinatePreviewCleared.connect(self._clear_coordinate_preview)
        
        # Toolbar
        self.toolbar = self.addToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setIconSize(QSize(24, 24))
        
        style = QApplication.style()
        
        # Save / Load Actions (Keep these in toolbar)
        self.act_save = QAction(style.standardIcon(style.SP_DialogSaveButton), "Save", self)
        self.act_save.triggered.connect(self.save_macro)
        self.toolbar.addAction(self.act_save)
        
        self.act_load = QAction(style.standardIcon(style.SP_DialogOpenButton), "Load", self)
        self.act_load.triggered.connect(self.load_macro)
        self.toolbar.addAction(self.act_load)

        # Undo / Redo actions
        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.triggered.connect(self._do_undo)
        self.act_redo = QAction("Redo", self)
        self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.act_redo.triggered.connect(self._do_redo)
        self.toolbar.addAction(self.act_undo)
        self.toolbar.addAction(self.act_redo)
        
        # Other actions are moved to the left panel buttons to avoid duplication.
        # We keep the action objects if needed for shortcuts or other references, 
        # but we don't add them to the toolbar.
        
        self.act_run = QAction("Run", self)
        self.act_run.triggered.connect(self.run_macro)
        
        self.act_stop = QAction("Stop", self)
        self.act_stop.triggered.connect(self.stop_macro)
        
        self.act_record = QAction("Record", self)
        self.act_record.setCheckable(True)
        self.act_record.toggled.connect(self.toggle_record)
        
        self.act_add_img = QAction("Add Image", self)
        self.act_add_img.triggered.connect(self.add_image_step)
        
        self.act_add_act = QAction("Add Action", self)
        self.act_add_act.triggered.connect(self.add_not_image_step)

        # Main Layout with Splitter
        from PyQt5.QtWidgets import QSplitter
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel (Tabbed: Scenario / Triggers)
        self.left_tabs = QTabWidget()
        
        # Tab 1: Scenario List
        # We move the list directly to the tab, removing the old grid layout buttons
        scenario_widget = QWidget()
        scenario_layout = QVBoxLayout(scenario_widget)
        scenario_layout.setContentsMargins(0,0,0,0)
        scenario_layout.addWidget(self.list)
        
        # Scenario action buttons
        btn_layout = QGridLayout()
        btn_layout.setSpacing(5)
        
        # Helper to format button text with hotkey
        def btn_text(label, hk):
            # hk_pretty가 없으면 그대로 반환 (안전장치)
            try:
                pretty = hk_pretty(hk) if hk else ""
                return f"{label} ({pretty})" if pretty else label
            except NameError:
                return f"{label} ({hk})" if hk else label

        # Row 1: Add buttons
        self.btnAddImg = QPushButton(btn_text("이미지+", self._hk_add_img))
        self.btnAddImg.clicked.connect(self.add_image_step)
        self.btnAddImg.setStyleSheet("background: #1E3A5F; color: white; padding: 8px; font-weight: bold;")
        
        self.btnAddAction = QPushButton(btn_text("일반동작+", self._hk_add_notimg))
        self.btnAddAction.clicked.connect(self.add_not_image_step)
        self.btnAddAction.setStyleSheet("background: #2C5F2D; color: white; padding: 8px; font-weight: bold;")
        
        btn_layout.addWidget(self.btnAddImg, 0, 0)
        btn_layout.addWidget(self.btnAddAction, 0, 1)
        
        # Row 2: Other buttons
        btn_add_branch = QPushButton("🔀 분기 추가")
        btn_add_branch.clicked.connect(self.add_branch_step)
        btn_add_branch.setStyleSheet("background: #5F4C2C; color: white; padding: 8px;")
        
        btn_add_comment = QPushButton("💬 주석 추가")
        btn_add_comment.clicked.connect(self.add_comment_step)
        btn_add_comment.setStyleSheet("background: #3E3E42; color: white; padding: 8px;")
        
        btn_layout.addWidget(btn_add_branch, 1, 0)
        btn_layout.addWidget(btn_add_comment, 1, 1)
        
        # Row 3: Run / Stop buttons
        self.btnRun = QPushButton(btn_text("실행", self._hk_run))
        self.btnRun.clicked.connect(self._on_run_button_clicked)
        self._btn_run_style_normal = "background: #007ACC; color: white; padding: 10px; font-weight: bold;"
        self._btn_run_style_paused = "background: #D79B00; color: #151515; padding: 10px; font-weight: bold; border: 2px solid #F7C948;"
        self.btnRun.setStyleSheet(self._btn_run_style_normal)
        
        self.btnStop = QPushButton(btn_text("정지", self._hk_stop))
        self.btnStop.clicked.connect(self.stop_macro)
        self.btnStop.setStyleSheet("background: #C0392B; color: white; padding: 10px; font-weight: bold;")
        self.btnStop.setEnabled(False)
        
        btn_layout.addWidget(self.btnRun, 2, 0)
        btn_layout.addWidget(self.btnStop, 2, 1)
        
        # Row 4: Record button
        self.btnRecord = QPushButton(btn_text("녹화", self._hk_record))
        self.btnRecord.setCheckable(True)
        self.btnRecord.toggled.connect(self.toggle_record)
        self.btnRecord.setStyleSheet("background: #8B0000; color: white; padding: 10px; font-weight: bold;")
        btn_layout.addWidget(self.btnRecord, 3, 0, 1, 2)

        self.btnScenarioWizard = QPushButton("시나리오 마법사")
        self.btnScenarioWizard.clicked.connect(self.open_scenario_wizard)
        self.btnScenarioWizard.setStyleSheet("background: #6D4C41; color: white; padding: 10px; font-weight: bold;")
        self.btnScenarioWizard.setToolTip("고급 활용 예시 템플릿을 선택해 스텝을 자동 생성합니다.")
        btn_layout.addWidget(self.btnScenarioWizard, 4, 0, 1, 2)

        self.btnConditionalWizard = QPushButton("조건 위저드")
        self.btnConditionalWizard.clicked.connect(self.open_conditional_action_wizard)
        self.btnConditionalWizard.setStyleSheet("background: #455A64; color: white; padding: 10px; font-weight: bold;")
        self.btnConditionalWizard.setToolTip("질문형 입력으로 OCR/분기 스텝을 자동 생성합니다.")
        btn_layout.addWidget(self.btnConditionalWizard, 5, 0, 1, 2)

        self.btnSimulate = QPushButton("경로 시뮬레이션")
        self.btnSimulate.clicked.connect(self.run_logic_simulation)
        self.btnSimulate.setStyleSheet("background: #00695C; color: white; padding: 8px; font-weight: bold;")
        self.btnSimulate.setToolTip("실행 없이 현재 데이터 기준 예상 경로를 하이라이트합니다.")
        btn_layout.addWidget(self.btnSimulate, 6, 0)

        self.chkSensorAssume = QCheckBox("센서 성공 가정")
        self.chkSensorAssume.setToolTip("OCR/이미지 매칭 결과를 시뮬레이션에서 성공으로 가정합니다.")
        self.chkSensorAssume.setChecked(False)
        btn_layout.addWidget(self.chkSensorAssume, 6, 1)
        
        scenario_layout.addLayout(btn_layout)
        
        self.left_tabs.addTab(scenario_widget, "Scenario")
        
        # Tab 2: Triggers
        trigger_widget = self._init_trigger_tab()
        self.left_tabs.addTab(trigger_widget, "Triggers")
        # Tab 3: Multi-Client Manager
        try:
            self.manager_tab = ManagerTab(self)
            self.left_tabs.addTab(self.manager_tab, "Multi-Manager")
        except Exception as e:
            QMessageBox.critical(self, "ManagerTab Load Error", str(e))
            raise
        
        self.splitter.addWidget(self.left_tabs)
        
        # Center Panel (Preview & Log)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0,0,0,0)
        
        # Preview Area
        grp_preview = QGroupBox("Preview")
        preview_layout = QVBoxLayout(grp_preview)
        preview_layout.setContentsMargins(0,10,0,0)
        self.lblPreview = QLabel("No Preview")
        self.lblPreview.setAlignment(Qt.AlignCenter)
        self.lblPreview.setStyleSheet("background:#222;color:#aaa;")
        self.lblPreview.setMinimumHeight(300)
        preview_layout.addWidget(self.lblPreview)
        center_layout.addWidget(grp_preview, 2)
        
        # Log Area
        grp_log = QGroupBox("Log")
        log_layout = QVBoxLayout(grp_log)
        log_layout.setContentsMargins(0,10,0,0)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background:#111;color:#ddd;font-family:Consolas,monospace;")
        log_layout.addWidget(self.log)
        center_layout.addWidget(grp_log, 1)
        
        self.splitter.addWidget(center_widget)
        
        # Right panel (scheduler, presets, settings)
        right_panel = self._create_right_tab_panel()
        self.splitter.addWidget(right_panel)
        self.right_panel = right_panel
        
        # Set Splitter Sizes (approx 25%, 50%, 25%)
        self.splitter.setSizes([300, 600, 300])
        
        self.setCentralWidget(self.splitter)
        
        # Keep references to buttons if other methods use them (e.g. toggle_record uses btnRecord)
        # We should update those methods to use actions instead, or map buttons to actions.
        # For minimal refactoring impact, we can alias self.btnRecord to self.act_record
        # But QAction has different API than QPushButton (setChecked vs setCheckable).
        # We need to check usages of self.btnRecord, self.btnRun, etc.
        
        # Mapping for compatibility - REMOVED
        # self.btnRecord = self.act_record 
        # self.btnRun = self.act_run
        # self.btnStop = self.act_stop
        
        # Other buttons like btnAddImg were connected in __init__. 
        # We already connected actions above.
        
        # Checkboxes need to be placed somewhere. Maybe in a Settings menu or a small toolbar area?
        # Or keep them in the right panel or bottom bar.
        # For now, let's add them to a "Options" toolbar or menu.
        self.chkDry = QCheckBox("Dry Run")
        self.chkAutoMin = QCheckBox("Mini Mode")
        self.chkCaptureFail = QCheckBox("Capture Fail")
        self.chkHumanMode = QCheckBox("Human Mode")
        self.chkDebugOverlay = QCheckBox("Show Debug Overlay")
        
        # Add a secondary toolbar for options
        # Stage 1 UI modernization: split one dense row into Core + Advanced rows
        self.opt_toolbar = self.addToolBar("Options")
        self.opt_toolbar.setMovable(False)
        self.opt_toolbar.setFloatable(False)
        self.opt_toolbar.setAllowedAreas(Qt.TopToolBarArea)

        self._opt_scroll = QScrollArea()
        self._opt_scroll.setWidgetResizable(True)
        self._opt_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._opt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._opt_scroll.setFrameShape(QFrame.NoFrame)

        self._opt_root = QWidget()
        self._opt_root_layout = QVBoxLayout(self._opt_root)
        self._opt_root_layout.setContentsMargins(4, 0, 4, 0)
        self._opt_root_layout.setSpacing(2)

        self._opt_core_row = QWidget()
        self._opt_core_row.setObjectName("optCoreRow")
        self._opt_core_layout = QHBoxLayout(self._opt_core_row)
        self._opt_core_layout.setContentsMargins(0, 0, 0, 0)
        self._opt_core_layout.setSpacing(6)

        self._opt_adv_row = QWidget()
        self._opt_adv_layout = QHBoxLayout(self._opt_adv_row)
        self._opt_adv_layout.setContentsMargins(0, 0, 0, 0)
        self._opt_adv_layout.setSpacing(6)

        self._opt_root_layout.addWidget(self._opt_core_row)
        self._opt_root_layout.addWidget(self._opt_adv_row)

        self._opt_scroll.setWidget(self._opt_root)
        self._opt_scroll.setMinimumHeight(75)
        self.opt_toolbar.addWidget(self._opt_scroll)

        def _opt_core_add(widget, stretch: int = 0):
            self._opt_core_layout.addWidget(widget, stretch)

        def _opt_adv_add(widget, stretch: int = 0):
            self._opt_adv_layout.addWidget(widget, stretch)

        def _opt_core_sep():
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setMinimumHeight(14)
            line.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self._opt_core_layout.addWidget(line)

        def _opt_adv_sep():
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setMinimumHeight(14)
            line.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self._opt_adv_layout.addWidget(line)

        # Backward compatibility for references that used a single row layout.
        self._opt_row_layout = self._opt_core_layout

        # Core row: setup essentials (Target -> Mode/Data -> Monitor)
        self.lblTarget = QLabel("Target:")
        self.edTargetTitle = QLineEdit()
        self.edTargetTitle.setPlaceholderText("Partial Window Name")
        self.edTargetTitle.setMinimumWidth(140)
        self.edTargetTitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btnFindTarget = QPushButton("Find")
        self.btnFindTarget.setToolTip("Find and activate target window")
        self.btnFindTarget.clicked.connect(self._find_target_window)
        self.btnFixWindow = QPushButton("Fix/Shake")
        self.btnFixWindow.setToolTip("Fix black screen/resize glitches")
        self.btnFixWindow.clicked.connect(self._fix_target_window)
        self.btnSelectTarget = QPushButton("...")
        self.btnSelectTarget.setFixedWidth(28)
        self.btnSelectTarget.setToolTip("Open window selector")
        self.btnSelectTarget.clicked.connect(self._open_window_selector)
        _opt_core_add(self.lblTarget)
        _opt_core_add(self.edTargetTitle, 1)
        _opt_core_add(self.btnSelectTarget)
        _opt_core_add(self.btnFindTarget)
        _opt_core_add(self.btnFixWindow)
        _opt_core_sep()

        # Keep most-used Excel controls near the left side of the core row.
        self.chkExcelDataMode = QCheckBox("Excel Data Mode")
        self.chkExcelDataMode.setToolTip("엑셀 행 데이터를 분배해 멀티 세션 자동화를 실행합니다.")
        self.chkExcelDataMode.setMinimumWidth(130)
        self.chkExcelDataMode.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        _opt_core_add(self.chkExcelDataMode)

        self.spExcelParallelism = QSpinBox()
        self.spExcelParallelism.setRange(1, 16)
        self.spExcelParallelism.setValue(2)
        self.spExcelParallelism.setPrefix("P:")
        self.spExcelParallelism.setMinimumWidth(68)
        self.spExcelParallelism.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        _opt_core_add(self.spExcelParallelism)

        self.edExcelDataPath = ElidedPathLineEdit()
        self.edExcelDataPath.setPlaceholderText(".xlsx 파일 경로")
        self.edExcelDataPath.setReadOnly(True)
        self.edExcelDataPath.setMinimumWidth(120)
        self.edExcelDataPath.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        _opt_core_add(self.edExcelDataPath, 1)

        self.btnExcelDataPick = QPushButton("Excel...")
        self.btnExcelDataPick.setToolTip("엑셀 데이터 파일을 선택합니다.")
        self.btnExcelDataPick.clicked.connect(self._pick_excel_data_file)
        self.btnExcelDataPick.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        _opt_core_add(self.btnExcelDataPick)

        self.pbExcelProgress = QProgressBar()
        self.pbExcelProgress.setRange(0, 100)
        self.pbExcelProgress.setValue(0)
        self.pbExcelProgress.setFixedWidth(120)
        _opt_core_add(self.pbExcelProgress)

        self.lblExcelStatus = QLabel("Excel: Idle")
        self.lblExcelStatus.setMinimumWidth(150)
        self.lblExcelStatus.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        _opt_core_add(self.lblExcelStatus)

        self.lblBatchModeBadge = QLabel("BATCH MODE ACTIVE")
        self.lblBatchModeBadge.setObjectName("batchModeBadge")
        self.lblBatchModeBadge.setStyleSheet(
            "QLabel#batchModeBadge {"
            "background-color: #1B5E20; color: white;"
            "padding: 2px 8px; border-radius: 10px; font-weight: 600;"
            "}"
        )
        self.lblBatchModeBadge.hide()
        _opt_core_add(self.lblBatchModeBadge)

        self.btnToolbarRun = QPushButton("Run")
        self.btnToolbarRun.setToolTip("Start macro (or resume if paused)")
        self.btnToolbarRun.setMinimumWidth(85)
        self.btnToolbarRun.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btnToolbarRun.setStyleSheet(
            "QPushButton { background-color: #0078D4; color: white; padding: 5px 12px; font-weight: 600; }"
            "QPushButton:disabled { background-color: #40515f; color: #c7c7c7; }"
        )
        self.btnToolbarRun.clicked.connect(self._on_run_button_clicked)
        _opt_core_add(self.btnToolbarRun)

        self.btnToolbarStop = QPushButton("Stop")
        self.btnToolbarStop.setToolTip("Stop running macro")
        self.btnToolbarStop.setMinimumWidth(85)
        self.btnToolbarStop.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btnToolbarStop.setStyleSheet(
            "QPushButton { background-color: #2b1f1f; color: #ff6b6b; border: 1px solid #9f2f2f; padding: 5px 12px; font-weight: 600; }"
            "QPushButton:disabled { color: #8f8f8f; border-color: #555; }"
        )
        self.btnToolbarStop.clicked.connect(self._on_stop_button_clicked)
        self.btnToolbarStop.setEnabled(False)
        _opt_core_add(self.btnToolbarStop)

        self.btnSmartCapture = QPushButton("스마트 캡처")
        self.btnSmartCapture.setToolTip("화면에서 드래그 캡처 후 이미지 기반 스텝을 즉시 생성합니다.")
        self.btnSmartCapture.setMinimumWidth(105)
        self.btnSmartCapture.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btnSmartCapture.setStyleSheet(
            "QPushButton { background-color: #35586C; color: #f4fbff; padding: 5px 10px; font-weight: 600; }"
            "QPushButton:disabled { background-color: #3a3a3a; color: #8f8f8f; }"
        )
        self.btnSmartCapture.clicked.connect(self._open_smart_capture_menu)
        _opt_core_add(self.btnSmartCapture)

        self._opt_core_layout.addStretch(0)
        self._opt_core_layout.setStretchFactor(self.edTargetTitle, 2)
        self._opt_core_layout.setStretchFactor(self.edExcelDataPath, 3)

        # Advanced row: secondary runtime options
        self.chkAutoEnterAfterText = QCheckBox("Auto Enter")
        self.chkAutoEnterAfterText.setToolTip("텍스트 입력 액션 뒤에 Enter 키를 자동 입력합니다.")
        self.chkAutoEnterAfterText.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        _opt_adv_add(self.chkAutoEnterAfterText)
        self.chkSmartSnap = QCheckBox("Smart Snap")
        self.chkSmartSnap.setToolTip("WZ 세트 스텝 이동 시 내부 흐름이 깨지지 않도록 그룹 이동/보정을 수행합니다.")
        self.chkSmartSnap.setChecked(True)
        self.chkSmartSnap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        _opt_adv_add(self.chkSmartSnap)
        _opt_adv_sep()
        _opt_adv_add(self.chkDry)
        _opt_adv_add(self.chkAutoMin)
        _opt_adv_add(self.chkCaptureFail)
        _opt_adv_add(self.chkHumanMode)
        _opt_adv_add(self.chkDebugOverlay)
        self._opt_adv_layout.addStretch(0)

        # For backward compatibility with existing methods
        self.edTargetWindow = self.edTargetTitle
        self.chkDebugOverlay.toggled.connect(lambda v: self.debug_overlay.setVisible(v))
        self.chkExcelDataMode.toggled.connect(self._on_excel_mode_toggled)
        self.edExcelDataPath.textChanged.connect(self._on_excel_preview_source_changed)
        self._apply_excel_mode_visual_state(self.chkExcelDataMode.isChecked(), announce=False)
        self._sync_toolbar_run_stop_buttons()
        
        # Menu Bar
        menubar = self.menuBar()
        
        # Settings Menu
        settings_menu = menubar.addMenu("Settings")
        
        act_hotkeys = QAction("Hotkey Settings", self)
        act_hotkeys.triggered.connect(self._open_hotkey_dialog)
        settings_menu.addAction(act_hotkeys)
        
        act_recording = QAction("Recording Settings", self)
        act_recording.triggered.connect(self._open_record_settings)
        settings_menu.addAction(act_recording)
        
        act_tesseract = QAction("OCR (Tesseract) Path...", self)
        act_tesseract.triggered.connect(self._open_tesseract_settings)
        settings_menu.addAction(act_tesseract)
        
        # Help Menu
        help_menu = menubar.addMenu("Help")

        act_history = QAction("Execution History", self)
        act_history.triggered.connect(self._open_execution_history)
        help_menu.addAction(act_history)

        act_guide = QAction("User Guide", self)
        act_guide.triggered.connect(self._open_user_guide)
        help_menu.addAction(act_guide)
        
        self._init_status_bar()
        self._update_hotkey_labels()
        self._install_qshortcuts()
        self._setup_global_hotkey_engine()
        self._load_general_settings()
        self._load_scheduler_settings()
        self._maybe_prompt_tesseract_setup()
        self._update_undo_buttons()
        self._init_open_panel_button()
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        self.excelOrchEvent.connect(self._on_excel_orch_event)
        self.excelOrchFinished.connect(self._on_excel_orch_finished)

    def _update_undo_buttons(self):
        """Enable/disable undo/redo actions based on stack state."""
        try:
            can_undo = self.undo_stack.can_undo()
            can_redo = self.undo_stack.can_redo()
        except Exception:
            # Fallback if the stack API changes
            can_undo = bool(getattr(self.undo_stack, "undo_stack", []))
            can_redo = bool(getattr(self.undo_stack, "redo_stack", []))

        if hasattr(self, "act_undo"):
            self.act_undo.setEnabled(bool(can_undo))
        if hasattr(self, "act_redo"):
            self.act_redo.setEnabled(bool(can_redo))

    def _push_command(self, command, focus_index: int | None = None):
        """Execute a command, refresh UI, and update undo/redo state."""
        self.undo_stack.push(command)
        self._simulated_indices = set()
        try:
            self.refresh_step_list(focus_index=focus_index)
        except TypeError:
            # Backward compatibility if refresh_step_list has no args
            self.refresh_step_list()
        # Restore selection if requested
        if focus_index is not None and hasattr(self, "list"):
            try:
                self.list.setCurrentRow(max(0, min(focus_index, self.list.count() - 1)))
            except Exception as e:
                self._warn_once("push_command_focus", f"Failed to restore focused row after command push: {e}")
        self._update_undo_buttons()

    def _do_undo(self):
        if not self.undo_stack.can_undo():
            return
        try:
            self.undo_stack.undo()
        except Exception as e:
            self.err(f"Undo failed: {e}")
            return
        try:
            self.refresh_step_list()
        except Exception as e:
            self._warn_once("undo_refresh_step_list", f"Undo completed but step list refresh failed: {e}")
        self._update_undo_buttons()

    def _do_redo(self):
        if not self.undo_stack.can_redo():
            return
        try:
            self.undo_stack.redo()
        except Exception as e:
            self.err(f"Redo failed: {e}")
            return
        try:
            self.refresh_step_list()
        except Exception as e:
            self._warn_once("redo_refresh_step_list", f"Redo completed but step list refresh failed: {e}")
        self._update_undo_buttons()


    def _spawn_crosshair(self, x, y, dur):
        try:
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[0]
                left, top, w, h = int(mon["left"]), int(mon["top"]), int(mon["width"]), int(mon["height"])
        except Exception:
            scr = QApplication.primaryScreen()
            vg = scr.virtualGeometry()
            left, top, w, h = vg.x(), vg.y(), vg.width(), vg.height()
            
        ov = CrosshairOverlay(left, top, w, h, x, y, dur)
        self._live_overlays.append(ov)
        QTimer.singleShot(dur + 50, lambda: self._live_overlays.remove(ov) if ov in self._live_overlays else None)

    # --- Serialization helpers ---
    def _encode_bytes(self, obj):
        import base64
        if isinstance(obj, bytes):
            return {"__bytes__": True, "data": base64.b64encode(obj).decode("ascii")}
        if isinstance(obj, dict):
            return {k: self._encode_bytes(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._encode_bytes(x) for x in obj]
        return obj

    def _decode_bytes(self, obj):
        import base64
        if isinstance(obj, dict):
            if obj.get("__bytes__") and "data" in obj:
                try:
                    return base64.b64decode(obj["data"])
                except Exception:
                    return obj
            return {k: self._decode_bytes(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._decode_bytes(x) for x in obj]
        return obj

    def _json_default(self, obj):
        if isinstance(obj, bytes):
            import base64
            return {"__bytes__": True, "data": base64.b64encode(obj).decode("ascii")}
        if hasattr(obj, "to_dict"):
            try:
                return self._encode_bytes(obj.to_dict())
            except Exception as e:
                self._warn_once("json_default_to_dict", f"Failed to serialize via to_dict(); falling back to __dict__: {e}")
        if hasattr(obj, "__dict__"):
            return self._encode_bytes(obj.__dict__)
        return str(obj)

    def _get_step_fields(self):
        if not hasattr(self, "_step_field_names"):
            self._step_field_names = {f.name for f in fields(StepData)}
        return self._step_field_names

    def _coerce_step(self, s):
        if isinstance(s, StepData):
            return s
        if isinstance(s, dict):
            allowed = self._get_step_fields()
            filtered = {k: v for k, v in s.items() if k in allowed}
            if "id" not in filtered:
                filtered["id"] = s.get("id") or str(uuid.uuid4())
            if "name" not in filtered:
                filtered["name"] = s.get("name") or "Step"
            if "type" not in filtered:
                filtered["type"] = s.get("type") or "comment"
            try:
                return StepData(**filtered)
            except Exception:
                return StepData(id=str(filtered.get("id", uuid.uuid4())), name=filtered.get("name", "Step"), type=filtered.get("type", "comment"))
        return StepData(id=str(uuid.uuid4()), name="Step", type="comment")

    # --- File I/O ---
    def save_macro(self):
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Save Macro",
            "",
            "GameBot Files (*.json *.macro);;All Files (*)",
        )
        if not fname:
            return
        # 기본 확장자 .json
        if "." not in os.path.basename(fname):
            fname = f"{fname}.json"
        
        try:
            rc = RepeatConfig(
                repeat_count=self.sbRepeatCount.value(),
                repeat_cooldown_ms=int(self.sbCooldown.value() * 1000),
                stop_on_fail=self.cbStopOnFail.isChecked(),
                max_duration_ms=self.sbMaxDuration.value() * 60 * 1000
            )
            meta = {
                "version": "1.0",
                "target_window": self._get_target_window_title() if hasattr(self, "_get_target_window_title") else "",
                "description": "",
            }
            if str(fname).lower().endswith(".macro"):
                steps_for_save = [s if isinstance(s, StepData) else self._coerce_step(s) for s in self.steps]
                MacroIO.save_macro(fname, steps_for_save, rc, meta=meta)
            else:
                serialized_steps = []
                for step in self.steps:
                    payload = step
                    if hasattr(step, "to_dict"):
                        try:
                            payload = step.to_dict()
                        except Exception:
                            payload = step
                    elif hasattr(step, "__dict__"):
                        payload = dict(step.__dict__)
                    # Fallback: ensure no non-string keys
                    try:
                        payload = self._encode_bytes(payload)
                    except Exception:
                        payload = self._encode_bytes(dict(payload))
                    serialized_steps.append(payload)

                save_data = {
                    "meta": meta,
                    "steps": self._encode_bytes(serialized_steps),
                    "repeat": rc.__dict__,
                }
                # Use json dump to preserve meta
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(self._encode_bytes(save_data), f, ensure_ascii=False, indent=2, default=self._json_default)
            self.info(f"Saved to {fname}")
            try:
                self._current_macro_path = os.path.abspath(fname)
            except Exception:
                self._current_macro_path = fname
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def load_macro(self):
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Load Macro",
            "",
            "GameBot Files (*.json *.macro);;All Files (*)",
        )
        if not fname:
            return
        self._load_macro_from_path(fname)

    def _load_macro_from_path(self, path: str):
        """
        Load macro with backward compatibility.
        - New format: dict with meta/repeat/steps.
        - Legacy JSON list: steps only.
        - Fallback: MacroIO.load_macro for .macro files.
        """
        new_steps = None
        rc: RepeatConfig | None = None
        json_err = None
        raw_text = None

        def _process_data(data_obj):
            nonlocal new_steps, rc
            if isinstance(data_obj, list):
                new_steps = [self._coerce_step(self._decode_bytes(s)) for s in data_obj]
                rc = RepeatConfig()
                self.info("Loaded legacy macro format.")
            elif isinstance(data_obj, dict):
                new_steps = [self._coerce_step(self._decode_bytes(s)) for s in data_obj.get("steps", [])]
                rep_cfg = data_obj.get("repeat", {}) or {}
                rc = RepeatConfig(**rep_cfg) if isinstance(rep_cfg, dict) else RepeatConfig()
                meta = data_obj.get("meta", {}) or {}
                target = meta.get("target_window", "")
                if hasattr(self, "edTargetTitle"):
                    self.edTargetTitle.setText(target)
                self.info(f"Loaded macro with target: {target}")
            else:
                raise ValueError("Unsupported macro format")

        # Try JSON first (handles .json and JSON-formatted .macro)
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            data = self._decode_bytes(json.loads(raw_text))
            _process_data(data)
        except Exception as e_json:
            json_err = e_json
            # Fallback: MacroIO (zip-based .macro)
            try:
                new_steps, rc = MacroIO.load_macro(path)
                new_steps = [self._coerce_step(self._decode_bytes(s)) for s in new_steps]
                try:
                    payload = MacroIO.load_macro_payload(path)
                    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
                    target = meta.get("target_window", "") if isinstance(meta, dict) else ""
                    if hasattr(self, "edTargetTitle"):
                        self.edTargetTitle.setText(target)
                except Exception:
                    pass
            except Exception as e_zip:  # noqa: BLE001
                # Last resort: tolerant literal_eval for loosely formatted text macros
                import ast

                try:
                    if raw_text is None:
                        with open(path, "r", encoding="utf-8") as f:
                            raw_text = f.read()
                    data = self._decode_bytes(ast.literal_eval(raw_text))
                    _process_data(data)
                except Exception as e_literal:
                    msg = str(e_zip)
                    if json_err:
                        msg = f"{msg}\n(JSON parse failed: {json_err})"
                    msg = f"{msg}\n(Literal parse failed: {e_literal})"
                    QMessageBox.critical(self, "Load Error", msg)
                    return False

        if rc is None:
            rc = RepeatConfig()
        if hasattr(self, 'sbRepeatCount'):
            self.sbRepeatCount.setValue(rc.repeat_count)
        if hasattr(self, 'sbCooldown'):
            self.sbCooldown.setValue(rc.repeat_cooldown_ms / 1000.0)
        if hasattr(self, 'cbStopOnFail'):
            self.cbStopOnFail.setChecked(rc.stop_on_fail)
        if hasattr(self, 'sbMaxDuration'):
            self.sbMaxDuration.setValue(rc.max_duration_ms // 60000)
        
        self.steps = new_steps or []
        self.list.clear()
        for s in self.steps:
            self.add_list_item(s)
        self.update_preview()
        self.info(f"Loaded: {path}")
        try:
            self._current_macro_path = os.path.abspath(path)
        except Exception:
            self._current_macro_path = path
        return True

    def info(self, msg: str):
        if hasattr(self, 'log'):
            self.log.appendHtml(f"<span style='color:#cccccc;'>[INFO] {msg}</span>")
        print(f"[INFO] {msg}")
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(msg, 3000)

    def warn(self, msg: str):
        if hasattr(self, 'log'):
            self.log.appendHtml(f"<span style='color:orange;'>[WARN] {msg}</span>")
        print(f"[WARN] {msg}")
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(f"WARN: {msg}", 3000)

    def err(self, msg: str):
        if hasattr(self, 'log'):
            self.log.appendHtml(f"<span style='color:#ff5555;'>[ERR] {msg}</span>")
        print(f"[ERR] {msg}")
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(f"ERR: {msg}", 5000)

    def _warn_once(self, key: str, msg: str):
        warned = getattr(self, "_warned_once_keys", None)
        if warned is None:
            warned = set()
            self._warned_once_keys = warned
        if key in warned:
            return
        warned.add(key)
        self.warn(msg)

    def _init_status_bar(self):
        self.statusBar().showMessage("Ready")
        
        # Mouse position label
        self.lblMousePos = QLabel("Mouse: 0, 0")
        self.lblMousePos.setStyleSheet("padding: 0 10px; color: #888;")
        self.statusBar().addPermanentWidget(self.lblMousePos)
        self.lblRuntimeStep = QLabel("Run: Idle")
        self.lblRuntimeStep.setStyleSheet("padding: 0 10px; color: #9ecbff;")
        self.statusBar().addPermanentWidget(self.lblRuntimeStep)
        self.lblRuntimeFail = QLabel("Fail: -")
        self.lblRuntimeFail.setStyleSheet("padding: 0 10px; color: #ff9c9c;")
        self.statusBar().addPermanentWidget(self.lblRuntimeFail)
        
        # Timer for mouse tracking
        self.mouse_timer = QTimer(self)
        self.mouse_timer.timeout.connect(self._update_mouse_pos)
        self.mouse_timer.start(100)

    # --- List Management ---
    def _smart_snap_enabled(self) -> bool:
        if hasattr(self, "chkSmartSnap"):
            try:
                return bool(self.chkSmartSnap.isChecked())
            except Exception:
                return bool(self._smart_snap_enabled_default)
        return bool(self._smart_snap_enabled_default)

    @staticmethod
    def _step_uid(step: StepData, fallback_index: int | None = None) -> str:
        raw = str(getattr(step, "id", "") or "").strip()
        if raw:
            return raw
        if fallback_index is None:
            return "__missing_id__"
        return f"__idx_{fallback_index}"

    @staticmethod
    def _step_has_wz_marker(step: StepData) -> bool:
        name = str(getattr(step, "name", "") or "")
        comment = str(getattr(step, "comment", "") or "")
        combined = f"{name} {comment}".lower()
        return "wz" in combined

    @staticmethod
    def _extract_step_ref_ids(step: StepData) -> set[str]:
        refs: set[str] = set()
        for field_name in (
            "start_loop_id",
            "target_true_id",
            "target_false_id",
            "jump_to_step_id",
            "on_match_goto_id",
            "branch_on_fail_goto_id",
            "branch_true_goto_id",
            "branch_false_goto_id",
            "pixel_success_goto_id",
        ):
            value = str(getattr(step, field_name, "") or "").strip()
            if value:
                refs.add(value)
        return refs

    @staticmethod
    def _positions_are_contiguous(positions: list[int]) -> bool:
        if len(positions) <= 1:
            return True
        seq = sorted(int(p) for p in positions)
        return all((b - a) == 1 for a, b in zip(seq, seq[1:]))

    def collect_step_group(self, seed_index: int, steps: list[StepData] | None = None) -> list[int]:
        step_list = list(steps if steps is not None else self.steps)
        if seed_index < 0 or seed_index >= len(step_list):
            return []

        ids = [self._step_uid(step, i) for i, step in enumerate(step_list)]
        id_to_index = {sid: i for i, sid in enumerate(ids)}

        refs_out: dict[str, set[str]] = {sid: set() for sid in ids}
        refs_in: dict[str, set[str]] = {sid: set() for sid in ids}
        for i, step in enumerate(step_list):
            sid = ids[i]
            for target_id in self._extract_step_ref_ids(step):
                if target_id not in id_to_index:
                    continue
                refs_out[sid].add(target_id)
                refs_in[target_id].add(sid)

        wz_ids = {ids[i] for i, step in enumerate(step_list) if self._step_has_wz_marker(step)}
        if not wz_ids:
            return [seed_index]

        candidates: set[str] = set(wz_ids)
        for sid in list(wz_ids):
            candidates.update(refs_out.get(sid, set()))
            candidates.update(refs_in.get(sid, set()))

        seed_id = ids[seed_index]
        contiguous_ids: set[str] = set()
        if self._step_has_wz_marker(step_list[seed_index]):
            left = seed_index
            right = seed_index
            while left - 1 >= 0 and self._step_has_wz_marker(step_list[left - 1]):
                left -= 1
            while right + 1 < len(step_list) and self._step_has_wz_marker(step_list[right + 1]):
                right += 1
            contiguous_ids = {ids[i] for i in range(left, right + 1)}
            candidates.update(contiguous_ids)
            for sid in contiguous_ids:
                candidates.update(refs_out.get(sid, set()))
                candidates.update(refs_in.get(sid, set()))

        if seed_id not in candidates and not self._step_has_wz_marker(step_list[seed_index]):
            return [seed_index]
        candidates.add(seed_id)

        stack = [seed_id]
        visited: set[str] = set()
        while stack:
            sid = stack.pop()
            if sid in visited:
                continue
            visited.add(sid)
            neighbors = (refs_out.get(sid, set()) | refs_in.get(sid, set())) & candidates
            for nxt in neighbors:
                if nxt not in visited:
                    stack.append(nxt)

        if contiguous_ids:
            visited.update(contiguous_ids)

        if not visited:
            return [seed_index]
        return sorted(id_to_index[sid] for sid in visited if sid in id_to_index)

    def _collect_wz_groups(self, steps: list[StepData]) -> list[list[str]]:
        groups: list[list[str]] = []
        consumed: set[str] = set()
        for idx, step in enumerate(steps):
            sid = self._step_uid(step, idx)
            if sid in consumed or not self._step_has_wz_marker(step):
                continue
            group_indices = self.collect_step_group(idx, steps=steps)
            if len(group_indices) < 2:
                consumed.add(sid)
                continue
            group_ids = [self._step_uid(steps[i], i) for i in sorted(group_indices)]
            groups.append(group_ids)
            consumed.update(group_ids)
        return groups

    def _normalize_legacy_jump_indices(self, ordered_steps: list[StepData]) -> list[StepData]:
        normalized = [copy.deepcopy(step) for step in ordered_steps]
        id_to_index = {
            self._step_uid(step, idx): idx
            for idx, step in enumerate(normalized)
        }
        for step in normalized:
            true_target_id = str(
                getattr(step, "target_true_id", None)
                or getattr(step, "jump_to_step_id", None)
                or ""
            ).strip()
            false_target_id = str(
                getattr(step, "target_false_id", None)
                or getattr(step, "branch_on_fail_goto_id", None)
                or getattr(step, "branch_false_goto_id", None)
                or ""
            ).strip()
            start_loop_id = str(getattr(step, "start_loop_id", None) or "").strip()

            true_index = id_to_index.get(true_target_id) if true_target_id else None
            false_index = id_to_index.get(false_target_id) if false_target_id else None
            loop_start_index = id_to_index.get(start_loop_id) if start_loop_id else None

            if hasattr(step, "target_true_index"):
                step.target_true_index = true_index
            if hasattr(step, "jump_to_index"):
                step.jump_to_index = true_index
            if hasattr(step, "target_false_index"):
                step.target_false_index = false_index
            if hasattr(step, "start_loop_index"):
                setattr(step, "start_loop_index", loop_start_index)
        return normalized

    def _apply_smart_snap_reorder(self, proposed_steps: list[StepData]) -> tuple[list[StepData], dict]:
        ordered_steps = list(proposed_steps)
        ordered_ids = [self._step_uid(step, i) for i, step in enumerate(ordered_steps)]
        id_to_step = {self._step_uid(step, i): step for i, step in enumerate(ordered_steps)}
        old_steps = list(self.steps)
        old_index_by_id = {self._step_uid(step, i): i for i, step in enumerate(old_steps)}
        wz_groups = self._collect_wz_groups(old_steps)
        adjusted_groups = 0

        for group_ids in wz_groups:
            if any(gid not in id_to_step for gid in group_ids):
                continue
            current_positions = [ordered_ids.index(gid) for gid in group_ids]
            sorted_positions = sorted(current_positions)
            current_order = [ordered_ids[pos] for pos in sorted_positions]
            already_stable = self._positions_are_contiguous(sorted_positions) and current_order == group_ids
            if already_stable:
                continue

            adjusted_groups += 1
            anchor_id = max(
                group_ids,
                key=lambda gid: abs(ordered_ids.index(gid) - old_index_by_id.get(gid, ordered_ids.index(gid))),
            )
            anchor_pos = ordered_ids.index(anchor_id)
            stripped = [sid for sid in ordered_ids if sid not in group_ids]
            insert_pos = sum(1 for sid in ordered_ids[:anchor_pos] if sid not in group_ids)
            ordered_ids = stripped[:insert_pos] + list(group_ids) + stripped[insert_pos:]

        reordered = [id_to_step[sid] for sid in ordered_ids if sid in id_to_step]
        normalized = self._normalize_legacy_jump_indices(reordered)
        preview_edges = self._build_flow_preview_edges(normalized)

        group_split = False
        for group_ids in wz_groups:
            if any(gid not in ordered_ids for gid in group_ids):
                continue
            positions = [ordered_ids.index(gid) for gid in group_ids]
            if not self._positions_are_contiguous(positions):
                group_split = True
                break

        dangling = any((len(edge) >= 4 and str(edge[3]) == "dangling") for edge in preview_edges)
        return normalized, {
            "adjusted_groups": adjusted_groups,
            "group_split": group_split,
            "dangling": dangling,
            "preview_edges": preview_edges,
        }

    def _show_toast(self, message: str, timeout_ms: int = 2400):
        try:
            local_pos = QPoint(24, max(24, int(self.opt_toolbar.height()) + 8))
            global_pos = self.mapToGlobal(local_pos)
            QToolTip.showText(global_pos, message, self, self.rect(), timeout_ms)
        except Exception:
            if hasattr(self, "statusBar"):
                self.statusBar().showMessage(message, timeout_ms)

    def sync_order(self):
        proposed_steps: list[StepData] = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            step = item.data(Qt.UserRole)
            if step is not None:
                proposed_steps.append(step)
        if proposed_steps == self.steps:
            return

        focused_step_id = ""
        focus_index = None
        try:
            current_row = int(self.list.currentRow())
            focus_index = current_row
            if 0 <= current_row < self.list.count():
                item = self.list.item(current_row)
                focused = item.data(Qt.UserRole) if item else None
                focused_step_id = str(getattr(focused, "id", "") or "")
        except Exception:
            focus_index = None

        snap_meta = {
            "adjusted_groups": 0,
            "group_split": False,
            "dangling": False,
            "preview_edges": [],
        }
        if self._smart_snap_enabled():
            reordered_steps, snap_meta = self._apply_smart_snap_reorder(proposed_steps)
        else:
            reordered_steps = self._normalize_legacy_jump_indices(proposed_steps)
            snap_meta["preview_edges"] = self._build_flow_preview_edges(reordered_steps)
            snap_meta["dangling"] = any((len(edge) >= 4 and str(edge[3]) == "dangling") for edge in snap_meta["preview_edges"])

        if reordered_steps == self.steps:
            return

        if focused_step_id:
            for idx, step in enumerate(reordered_steps):
                if str(getattr(step, "id", "") or "") == focused_step_id:
                    focus_index = idx
                    break

        self._push_command(ReorderStepsCommand(self.steps, reordered_steps), focus_index=focus_index)
        self._flow_preview_active = False

        has_warning = bool(snap_meta.get("group_split") or snap_meta.get("dangling"))
        if has_warning:
            if hasattr(self.list, "set_flow_edges"):
                self.list.set_flow_edges(snap_meta.get("preview_edges") or [])
            reason_bits = []
            if snap_meta.get("group_split"):
                reason_bits.append("그룹 분리")
            if snap_meta.get("dangling"):
                reason_bits.append("dangling 연결")
            reason = ", ".join(reason_bits) if reason_bits else "흐름 경고"
            msg = f"Smart Snap 경고: {reason}"
            self.warn(msg)
            if hasattr(self, "statusBar"):
                self.statusBar().showMessage(msg, 4500)
            self._show_toast(msg, timeout_ms=2200)

    def run_from_index(self, idx):
        self.run_macro(start_index=idx)

    def convert_to_branch_step(self, idx):
        if idx < 0 or idx >= len(self.steps): return
        step = self.steps[idx]
        if step.type not in {'image_click', 'wait_for_image'}: return
        if not step.png_bytes:
            QMessageBox.warning(self, "Convert Failed", "Select an image template before converting to a branch step.")
            return
        
        import copy
        original = copy.deepcopy(step)
        new_step = copy.deepcopy(step)
        new_step.type = 'image_branch'
        new_step.name = f"Branch: {step.name}"
        goto_target = None
        if idx + 1 < len(self.steps):
            goto_target = self.steps[idx + 1].id
        target = {
            "id": str(uuid.uuid4())[:8],
            "name": step.name,
            "png_bytes": step.png_bytes,
            "threshold": step.threshold,
            "min_confidence": step.min_confidence or step.threshold,
            "image_action": getattr(step, "image_action", "click"),
            "click_button": getattr(step, "click_button", None) or step.click_btn,
            "click_double": getattr(step, "click_double", False),
            "goto_id": goto_target,
        }
        if step.search_roi_enabled and step.search_roi_width > 0 and step.search_roi_height > 0:
            target.update({
                "search_roi_enabled": True,
                "search_roi_left": step.search_roi_left,
                "search_roi_top": step.search_roi_top,
                "search_roi_width": step.search_roi_width,
                "search_roi_height": step.search_roi_height,
            })
        new_step.conditional_targets = [target]
        
        self._push_command(EditStepCommand(self.steps, idx, original, new_step), focus_index=idx)
        self.info(f"Converted step {idx+1} to Branch Step.")

    def _on_list_item_renamed(self, item):
        idx = self.list.row(item)
        if 0 <= idx < len(self.steps):
            try:
                new_name = item.text().strip()
            except Exception:
                new_name = ""
            if new_name:
                self.rename_step_at(idx, new_name)

    def rename_step_at(self, idx, new_name: str):
        if idx < 0 or idx >= len(self.steps):
            return
        name = new_name.strip()
        if not name:
            return
        step = self.steps[idx]
        if step.name == name:
            return
        original = copy.deepcopy(step)
        updated = copy.deepcopy(step)
        updated.name = name
        self._push_command(EditStepCommand(self.steps, idx, original, updated), focus_index=idx)

    def refresh_list_item(self, idx):
        item = self.list.item(idx)
        if not item:
            return
        step = self.steps[idx]
        item.setData(Qt.UserRole, step)
        id_to_index = {str(getattr(s, "id", "") or ""): i for i, s in enumerate(self.steps)}
        preview_payload = self._get_excel_preview_payload()
        flow_hint = self._build_step_flow_hint(step, id_to_index)
        excel_preview = self._build_step_excel_preview(step, preview_payload)
        tooltip_parts = [p for p in [flow_hint, excel_preview] if p]
        item.setToolTip("\n".join(tooltip_parts))
        from .ui.widgets import StepItemWidget
        new_widget = StepItemWidget(step, idx + 1, flow_hint=flow_hint, excel_preview=excel_preview)
        self.list.setItemWidget(item, new_widget)
        if hasattr(self.list, "set_flow_edges"):
            self.list.set_flow_edges(self._collect_step_flow_edges(id_to_index))
        if hasattr(self.list, "set_simulated_indices"):
            self.list.set_simulated_indices(self._simulated_indices)

    def refresh_step_list(self, focus_index: int | None = None):
        self.list.clear()
        id_to_index = {str(getattr(s, "id", "") or ""): i for i, s in enumerate(self.steps)}
        preview_payload = self._get_excel_preview_payload()
        for i, s in enumerate(self.steps):
            flow_hint = self._build_step_flow_hint(s, id_to_index)
            excel_preview = self._build_step_excel_preview(s, preview_payload)
            tooltip_parts = [p for p in [flow_hint, excel_preview] if p]
            tooltip = "\n".join(tooltip_parts)
            self.add_list_item(s, idx=i, flow_hint=flow_hint, excel_preview=excel_preview, tooltip=tooltip)
        self.list.refresh_indices()
        if hasattr(self.list, "set_flow_edges"):
            self.list.set_flow_edges(self._collect_step_flow_edges(id_to_index))
        if hasattr(self.list, "set_simulated_indices"):
            self.list.set_simulated_indices(self._simulated_indices)
        if focus_index is not None and 0 <= focus_index < self.list.count():
            self.list.setCurrentRow(focus_index)
            self.list.scrollToItem(self.list.item(focus_index))
        self._apply_active_step_highlight()

    def _apply_active_step_highlight(self, scroll: bool = False):
        idx = getattr(self, "_active_step_index", None)
        failed_idx = getattr(self, "_last_failed_step_index", None)
        if not hasattr(self, "list"):
            return
        try:
            self.list.set_active_index(idx)
            self.list.set_failed_index(failed_idx)
            if scroll and idx is not None and 0 <= idx < self.list.count():
                self.list.scrollToItem(self.list.item(idx))
        except Exception as e:
            self._warn_once("active_step_highlight", f"Failed to update active-step highlight: {e}")

    def _on_runner_step_changed(self, idx: int):
        self._active_step_index = idx
        self._apply_active_step_highlight(scroll=True)

    def _find_step_row_by_uuid(self, step_uuid: str) -> int | None:
        sid = str(step_uuid or "").strip()
        if not sid:
            return None
        for idx, step in enumerate(self.steps):
            source_id = str(getattr(step, "source_step_id", "") or "").strip()
            runtime_id = str(getattr(step, "id", "") or "").strip()
            if sid == source_id or sid == runtime_id:
                return idx
        return None

    def _on_runner_step_started(self, step_uuid: str, step_name: str):
        row = self._find_step_row_by_uuid(step_uuid)
        if row is not None:
            self._active_step_index = row
            self._apply_active_step_highlight(scroll=True)
        title = str(step_name or "").strip() or "unnamed"
        sid = str(step_uuid or "").strip() or "-"
        if hasattr(self, "lblRuntimeStep"):
            self.lblRuntimeStep.setText(f"Run: {title} [{sid}]")

    def _on_runner_step_succeeded(self, step_uuid: str):
        sid = str(step_uuid or "").strip() or "-"
        if hasattr(self, "lblRuntimeStep"):
            self.lblRuntimeStep.setText(f"Run: OK [{sid}]")

    def _on_runner_step_failed(self, step_uuid: str, step_name: str, error_message: str):
        sid = str(step_uuid or "").strip() or "-"
        row = self._find_step_row_by_uuid(sid)
        self._last_failed_step_uuid = sid
        self._last_failed_step_index = row
        if row is not None:
            self._active_step_index = row
        self._apply_active_step_highlight(scroll=row is not None)

        name = str(step_name or "").strip() or "unnamed"
        message = str(error_message or "").strip() or "step failed"
        if hasattr(self, "lblRuntimeFail"):
            self.lblRuntimeFail.setText(f"Fail: {name} [{sid}] - {message}")
        self.warn(f"[Step Fail] {name} [{sid}] - {message}")

    def add_list_item(self, step: StepData, idx=-1, flow_hint: str = "", excel_preview: str = "", tooltip: str = ""):
        if idx == -1:
            self.list.add_step_item(step, flow_hint=flow_hint, excel_preview=excel_preview, tooltip=tooltip)
        else:
            # QListWidget doesn't have insertItem with widget easily?
            # We have to insert item then set widget.
            item = QListWidgetItem()
            item_height = 50
            if str(flow_hint or "").strip():
                item_height += 16
            if str(excel_preview or "").strip():
                item_height += 16
            item.setSizeHint(QSize(0, item_height))
            item.setData(Qt.UserRole, step)
            if tooltip:
                item.setToolTip(str(tooltip))
            self.list.insertItem(idx, item)
            
            from .ui.widgets import StepItemWidget
            widget = StepItemWidget(step, idx + 1, flow_hint=flow_hint, excel_preview=excel_preview)
            self.list.setItemWidget(item, widget)

    def update_preview(self):
        items = self.list.selectedItems()
        if not items:
            self.lblPreview.setText("No Selection")
            self.lblPreview.setPixmap(QPixmap())
            return
            
        item = items[0]
        step: StepData = item.data(Qt.UserRole)
        
        if step.type in {'image_click', 'wait_for_image'} and step.png_bytes:
            pix = QPixmap()
            pix.loadFromData(step.png_bytes)
            if not pix.isNull():
                scaled = pix.scaled(self.lblPreview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lblPreview.setPixmap(scaled)
                self.lblPreview.setText("")
            else:
                self.lblPreview.setText("Invalid Image")
        elif step.type == 'image_branch':
             # Show first target image or something
             if step.conditional_targets and step.conditional_targets[0].get('png_bytes'):
                pix = QPixmap()
                pix.loadFromData(step.conditional_targets[0]['png_bytes'])
                if not pix.isNull():
                    scaled = pix.scaled(self.lblPreview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.lblPreview.setPixmap(scaled)
                    self.lblPreview.setText("")
                else:
                    self.lblPreview.setText("Invalid Image")
             else:
                self.lblPreview.setText("Branch Step (No Image)")
        else:
            self.lblPreview.clear()
            self.lblPreview.setText(f"Step: {step.name}\nType: {step.type}")

    def _update_mouse_pos(self):
        try:
            pos = pyautogui.position()
            self.lblMousePos.setText(f"Mouse: {pos.x}, {pos.y}")
        except Exception as e:
            self._warn_once("mouse_pos_update", f"Mouse position update failed: {e}")

    # --- Hotkey Management ---
    def _load_hotkeys(self):
        hk = self.config.load_hotkeys()
        self._hk_run = hk["run"]
        self._hk_stop = hk["stop"]
        self._hk_record = hk["record"]
        self._hk_add_img = hk["add_img"]
        self._hk_add_notimg = hk["add_notimg"]
        self._hk_pause = hk.get("pause", self._hk_pause)
        self._hk_kill = hk.get("kill", self._hk_kill)

    def _save_hotkeys(self):
        self.config.save_hotkeys({
            "run": self._hk_run,
            "stop": self._hk_stop,
            "record": self._hk_record,
            "add_img": self._hk_add_img,
            "add_notimg": self._hk_add_notimg,
            "pause": self._hk_pause,
            "kill": self._hk_kill,
        })

    def _format_hotkey_hint(self, base: str, hk: str) -> str:
        try:
            pretty = hk_pretty(hk) if hk else ""
            return f"{base} ({pretty})" if pretty else base
        except NameError:
            return f"{base} ({hk})" if hk else base

    def _hotkey_conflicts(self, mapping: dict[str, str]) -> dict[str, list[str]]:
        by_combo: dict[str, list[str]] = {}
        for label, combo in mapping.items():
            normalized = hk_normalize(combo)
            if not normalized:
                continue
            by_combo.setdefault(normalized, []).append(label)
        return {combo: labels for combo, labels in by_combo.items() if len(labels) > 1}

    def _set_macro_paused_ui(self, paused: bool):
        self._macro_paused_ui = bool(paused)
        running = bool(self.runner and self.runner.isRunning())

        if hasattr(self, "statusBar"):
            if self._macro_paused_ui:
                pause_key = hk_pretty(self._hk_pause) if getattr(self, "_hk_pause", "") else "F10"
                self.statusBar().showMessage(f"PAUSED - press {pause_key} to resume", 0)
            elif running:
                self.statusBar().showMessage("Running...", 1200)
            else:
                self.statusBar().showMessage("Ready", 1200)

        if hasattr(self, "lblRuntimeStep"):
            if self._macro_paused_ui:
                pause_key = hk_pretty(self._hk_pause) if getattr(self, "_hk_pause", "") else "F10"
                self.lblRuntimeStep.setText(f"Run: Paused ({pause_key} to resume)")
            elif not running:
                self.lblRuntimeStep.setText("Run: Idle")

        if hasattr(self, "btnRun"):
            if self._macro_paused_ui:
                self.btnRun.setText(self._format_hotkey_hint("▶ 재개", self._hk_pause))
                self.btnRun.setStyleSheet(self._btn_run_style_paused)
                self.btnRun.setEnabled(True)
            else:
                self.btnRun.setText(self._format_hotkey_hint("실행", self._hk_run))
                self.btnRun.setStyleSheet(self._btn_run_style_normal)
                if running:
                    self.btnRun.setEnabled(False)
                else:
                    self.btnRun.setEnabled(True)
        self._sync_toolbar_run_stop_buttons()

    def _on_run_button_clicked(self):
        if self._excel_mode_running:
            self.info("Excel orchestration is already running.")
            return
        if self.runner and self.runner.isRunning():
            try:
                if hasattr(self.runner, "is_paused") and self.runner.is_paused():
                    self._act_pause_resume_from_hotkey()
                    return
            except Exception:
                pass
        if hasattr(self, "chkExcelDataMode") and self.chkExcelDataMode.isChecked():
            self.run_excel_orchestration()
            return
        self.run_macro()

    def _on_stop_button_clicked(self):
        self.stop_macro()

    def _sync_toolbar_run_stop_buttons(self):
        stop_enabled = False
        if hasattr(self, "btnToolbarRun"):
            run_enabled = bool(self.btnRun.isEnabled()) if hasattr(self, "btnRun") else bool(self.act_run.isEnabled())
            self.btnToolbarRun.setEnabled(run_enabled)
        if hasattr(self, "btnToolbarStop"):
            stop_enabled = bool(self.btnStop.isEnabled()) if hasattr(self, "btnStop") else bool(self.act_stop.isEnabled())
            self.btnToolbarStop.setEnabled(stop_enabled)
        if hasattr(self, "btnSmartCapture"):
            self.btnSmartCapture.setEnabled(not stop_enabled)

    def _pick_excel_data_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Excel 데이터 파일 선택",
            "",
            "Excel Files (*.xlsx)",
        )
        if path:
            self.edExcelDataPath.setText(path)

    def _apply_excel_mode_visual_state(self, enabled: bool, *, announce: bool = False) -> None:
        is_enabled = bool(enabled)
        if hasattr(self, "_opt_core_row"):
            if is_enabled:
                self._opt_core_row.setStyleSheet(
                    "QWidget#optCoreRow { background-color: #E6F4EA; border-radius: 6px; }"
                )
            else:
                self._opt_core_row.setStyleSheet(
                    "QWidget#optCoreRow { background-color: transparent; border-radius: 6px; }"
                )
        if hasattr(self, "lblBatchModeBadge"):
            self.lblBatchModeBadge.setVisible(is_enabled)
        if announce and hasattr(self, "statusBar"):
            mode_msg = "Excel Batch Mode Activated" if is_enabled else "Standard Mode Activated"
            self.statusBar().showMessage(mode_msg, 2200)

    def _on_excel_mode_toggled(self, enabled: bool) -> None:
        self._apply_excel_mode_visual_state(enabled, announce=self.isVisible())
        self.refresh_step_list()

    def _on_excel_preview_source_changed(self, _text: str) -> None:
        self._excel_preview_cache_path = ""
        self._excel_preview_payload = {}
        self.refresh_step_list()

    def _get_excel_text_template(self) -> str:
        for step in self.steps:
            action_type = str(getattr(step, "type", None) or getattr(step, "action_type", "") or "").lower()
            if action_type == "text":
                text = getattr(step, "key_string", None)
                if text not in (None, ""):
                    return str(text)
                continue
            if action_type == "keyboard":
                key_mode = str(getattr(step, "keyboard_mode", None) or getattr(step, "key_mode", "") or "").lower()
                if key_mode != "text":
                    continue
                text = getattr(step, "key_string", None)
                if text not in (None, ""):
                    return str(text)
        return ""

    def _build_excel_payload_runner(self):
        parent = self

        class _ExcelPayloadRunner:
            def __init__(self, owner: "MainWindow"):
                self._owner = owner
                self._dry_run = bool(owner.chkDry.isChecked()) if hasattr(owner, "chkDry") else False
                self._auto_enter_after_text = bool(owner.chkAutoEnterAfterText.isChecked()) if hasattr(owner, "chkAutoEnterAfterText") else False
                self._poll_interval = 0.05
                self._input_lock_manager = get_global_input_manager()
                self._input_lock_timeout_sec = 10.0
                if hasattr(owner, "_get_perf_level") and hasattr(owner, "chkPerfPlayback"):
                    try:
                        if bool(owner.chkPerfPlayback.isChecked()):
                            level = int(owner._get_perf_level())
                            if level >= 3:
                                self._poll_interval = 0.0
                            elif level == 2:
                                self._poll_interval = 0.01
                    except Exception:
                        self._poll_interval = 0.05

            def _maybe_press_enter_locked(self) -> None:
                if not self._auto_enter_after_text:
                    return
                pyautogui.press("enter")
                if self._poll_interval > 0.0:
                    time.sleep(min(0.05, max(0.0, float(self._poll_interval))))

            @staticmethod
            def _requires_clipboard_paste(text: str) -> bool:
                # pyautogui.write may drop/garble IME/non-ASCII chars; use paste path for safety.
                return any(ord(ch) > 127 for ch in str(text or ""))

            @staticmethod
            def _get_clipboard_text() -> str | None:
                try:
                    pyperclip = __import__("pyperclip")
                    return pyperclip.paste()
                except Exception:
                    pass
                try:
                    return QApplication.clipboard().text()
                except Exception:
                    return None

            @staticmethod
            def _set_clipboard_text(text: str) -> bool:
                data = str(text or "")
                try:
                    pyperclip = __import__("pyperclip")
                    pyperclip.copy(data)
                    return True
                except Exception:
                    pass
                try:
                    QApplication.clipboard().setText(data)
                    return True
                except Exception:
                    return False

            def _paste_text(self, text: str) -> bool:
                with self._input_lock_manager.acquire(
                    timeout_sec=self._input_lock_timeout_sec,
                    owner="excel_payload_runner",
                    operation="keyboard_paste",
                ):
                    prev = self._get_clipboard_text()
                    if not self._set_clipboard_text(text):
                        return False
                    try:
                        pyautogui.hotkey("ctrl", "v")
                        self._maybe_press_enter_locked()
                        return True
                    finally:
                        if prev is not None:
                            self._set_clipboard_text(prev)

            def execute_job(self, payload: dict):
                payload_map = dict(payload or {})
                payload_map.pop("__job_id", None)
                payload_map.pop("__excel_row_index", None)
                if self._dry_run:
                    return True
                template_text = self._owner._get_excel_text_template()
                if template_text not in (None, ""):
                    text = TemplateProcessor.render(str(template_text), payload_map)
                else:
                    text = payload_map.get("text")
                    if text is None:
                        text = payload_map.get("message")
                    text = TemplateProcessor.render(str(text or ""), payload_map)
                if TemplateProcessor.has_unresolved_placeholder(text):
                    raise RuntimeError(f"unresolved_placeholder: {text}")
                try:
                    if self._requires_clipboard_paste(text):
                        if not self._paste_text(text):
                            raise RuntimeError("clipboard_unavailable")
                    else:
                        with self._input_lock_manager.acquire(
                            timeout_sec=self._input_lock_timeout_sec,
                            owner="excel_payload_runner",
                            operation="keyboard_typewrite",
                        ):
                            pyautogui.write(text, interval=self._poll_interval)
                            self._maybe_press_enter_locked()
                except Exception as e:
                    raise RuntimeError(f"input_failed: {e}") from e
                return True

        return _ExcelPayloadRunner(parent)

    def _build_excel_adapter(
        self,
        orchestrator: JobQueueManager,
        runner,
        consumer_id: str,
        stop_event: threading.Event,
    ) -> SessionJobAdapter:
        return SessionJobAdapter(
            orchestrator,
            runner,
            consumer_id=consumer_id,
            stop_event=stop_event,
        )

    def _default_excel_output_path(self, input_path: str) -> str:
        stem, ext = os.path.splitext(input_path)
        suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if not ext:
            ext = ".xlsx"
        return f"{stem}_result_{suffix}{ext}"

    def _on_excel_result_sink_event(self, event: dict):
        try:
            self.excelOrchEvent.emit(dict(event or {}))
        except Exception:
            return

    def _render_excel_progress(self, snapshot: dict, status_note: str = ""):
        total = max(0, int(snapshot.get("total_jobs") or 0))
        succeeded = max(0, int(snapshot.get("succeeded") or 0))
        failed = max(0, int(snapshot.get("failed") or 0))
        done = min(total, succeeded + failed)

        if hasattr(self, "pbExcelProgress"):
            if total > 0:
                self.pbExcelProgress.setRange(0, total)
                self.pbExcelProgress.setValue(done)
            else:
                self.pbExcelProgress.setRange(0, 100)
                self.pbExcelProgress.setValue(0)
        if hasattr(self, "lblExcelStatus"):
            base = f"Excel: {done}/{total} (ok {succeeded}, fail {failed})"
            if status_note:
                base = f"{base} - {status_note}"
            self.lblExcelStatus.setText(base)

    def _on_excel_orch_event(self, event: dict):
        manager = self._excel_job_manager
        if manager is None:
            return
        worker_note = self._build_excel_worker_note(event)
        if worker_note:
            self.info(worker_note)
        snapshot = manager.snapshot()
        status_note = str((event or {}).get("event") or "")
        self._render_excel_progress(snapshot, status_note=status_note)

    def _lookup_excel_payload_value(self, payload: dict, key: str):
        if not payload:
            return ""
        if key in payload:
            return payload.get(key)
        lowered = str(key or "").strip().lower()
        for k, v in payload.items():
            if str(k).strip().lower() == lowered:
                return v
        return ""

    @staticmethod
    def _extract_placeholders(template_text: str) -> list[str]:
        text = str(template_text or "")
        found: list[str] = []
        seen: set[str] = set()
        for pattern in (r"\{\{\s*([^{}]+?)\s*\}\}", r"\{\s*([^{}]+?)\s*\}"):
            for m in re.finditer(pattern, text):
                name = str(m.group(1) or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                found.append(name)
        return found

    def _get_excel_preview_payload(self) -> dict:
        if not hasattr(self, "chkExcelDataMode") or not self.chkExcelDataMode.isChecked():
            return {}
        path = self.edExcelDataPath.text().strip() if hasattr(self, "edExcelDataPath") else ""
        if not path:
            return {}
        if path == self._excel_preview_cache_path:
            return dict(self._excel_preview_payload)
        if not os.path.exists(path):
            self._excel_preview_cache_path = path
            self._excel_preview_payload = {}
            return {}
        try:
            loaded_rows = ExcelDataLoader.load_rows(path)
            payload = dict(loaded_rows[0][1] or {}) if loaded_rows else {}
        except Exception:
            payload = {}
        self._excel_preview_cache_path = path
        self._excel_preview_payload = dict(payload)
        return dict(payload)

    def _build_step_flow_hint(self, step: StepData, id_to_index: dict[str, int]) -> str:
        stype = str(getattr(step, "type", "") or "").lower()
        parts: list[str] = []

        if stype in {"jump_if", "ocr_jump_if"}:
            target_id = getattr(step, "target_true_id", None) or getattr(step, "jump_to_step_id", None)
            if target_id:
                target_idx = id_to_index.get(str(target_id))
                if target_idx is not None:
                    parts.append(f"흐름: 조건 참 -> #{target_idx + 1}")
                else:
                    parts.append(f"흐름: 조건 참 -> ID {target_id}")
            fail_id = getattr(step, "branch_on_fail_goto_id", None)
            if fail_id:
                fail_idx = id_to_index.get(str(fail_id))
                if fail_idx is not None:
                    parts.append(f"흐름: 조건 실패 -> #{fail_idx + 1}")

        if stype == "end_loop":
            start_id = getattr(step, "start_loop_id", None)
            if start_id:
                start_idx = id_to_index.get(str(start_id))
                if start_idx is not None:
                    parts.append(f"흐름: 루프 복귀 -> #{start_idx + 1}")

        if stype == "start_loop":
            loop_count = int(getattr(step, "loop_count", 0) or 0)
            if loop_count <= 0:
                parts.append("흐름: 반복 시작 (무한)")
            else:
                parts.append(f"흐름: 반복 시작 ({loop_count}회)")

        return " | ".join(parts)

    def _collect_step_flow_edges(self, id_to_index: dict[str, int]) -> list[tuple[int, int, str]]:
        edges: list[tuple[int, int, str]] = []
        seen: set[tuple[int, int, str]] = set()

        for src_idx, step in enumerate(self.steps):
            stype = str(getattr(step, "type", "") or "").lower()

            def _append(target_id, kind: str) -> None:
                if not target_id:
                    return
                dst_idx = id_to_index.get(str(target_id))
                if dst_idx is None:
                    return
                edge = (src_idx, int(dst_idx), kind)
                if edge in seen:
                    return
                seen.add(edge)
                edges.append(edge)

            if stype in {"jump_if", "ocr_jump_if"}:
                _append(
                    getattr(step, "target_true_id", None) or getattr(step, "jump_to_step_id", None),
                    "jump_true",
                )
                _append(
                    getattr(step, "target_false_id", None) or getattr(step, "branch_on_fail_goto_id", None),
                    "jump_false",
                )
                continue

            if stype == "image_branch":
                _append(
                    getattr(step, "target_true_id", None) or getattr(step, "branch_true_goto_id", None),
                    "branch_true",
                )
                _append(
                    getattr(step, "target_false_id", None) or getattr(step, "branch_false_goto_id", None),
                    "branch_false",
                )
                continue

            if stype == "end_loop":
                _append(getattr(step, "start_loop_id", None), "loop_back")
                continue

            # Generic step-level branch metadata used by multiple action types.
            _append(getattr(step, "on_match_goto_id", None), "jump_true")
            _append(getattr(step, "branch_on_fail_goto_id", None), "jump_false")

        return edges

    def _build_flow_preview_edges(self, temp_steps: list[StepData]) -> list[tuple[int, int, str, str]]:
        order_hash = tuple(str(getattr(s, "id", "") or "") for s in temp_steps)
        edge_source_hash = tuple(
            (
                str(getattr(s, "id", "") or ""),
                str(getattr(s, "type", "") or "").lower(),
                str(getattr(s, "target_true_id", "") or getattr(s, "jump_to_step_id", "") or ""),
                str(getattr(s, "target_false_id", "") or getattr(s, "branch_on_fail_goto_id", "") or ""),
                str(getattr(s, "branch_true_goto_id", "") or ""),
                str(getattr(s, "branch_false_goto_id", "") or ""),
                str(getattr(s, "on_match_goto_id", "") or ""),
                str(getattr(s, "start_loop_id", "") or ""),
            )
            for s in temp_steps
        )
        cache_key = (order_hash, edge_source_hash)
        cached = self._flow_preview_cache.get(cache_key)
        if cached is not None:
            return [tuple(e) for e in cached]

        id_to_index = {str(getattr(s, "id", "") or ""): i for i, s in enumerate(temp_steps)}
        edges: list[tuple[int, int, str, str]] = []
        seen: set[tuple[int, int, str, str]] = set()

        def _append(src_idx: int, target_id, kind: str):
            if not target_id:
                return
            dst_idx = id_to_index.get(str(target_id))
            status = "ok"
            dst = src_idx
            if dst_idx is None:
                status = "dangling"
            else:
                dst = int(dst_idx)
                if dst == src_idx:
                    status = "self_jump"
            edge = (src_idx, dst, kind, status)
            if edge in seen:
                return
            seen.add(edge)
            edges.append(edge)

        for src_idx, step in enumerate(temp_steps):
            stype = str(getattr(step, "type", "") or "").lower()
            if stype in {"jump_if", "ocr_jump_if"}:
                _append(
                    src_idx,
                    getattr(step, "target_true_id", None) or getattr(step, "jump_to_step_id", None),
                    "jump_true",
                )
                _append(
                    src_idx,
                    getattr(step, "target_false_id", None) or getattr(step, "branch_on_fail_goto_id", None),
                    "jump_false",
                )
                continue
            if stype == "image_branch":
                _append(
                    src_idx,
                    getattr(step, "target_true_id", None) or getattr(step, "branch_true_goto_id", None),
                    "branch_true",
                )
                _append(
                    src_idx,
                    getattr(step, "target_false_id", None) or getattr(step, "branch_false_goto_id", None),
                    "branch_false",
                )
                continue
            if stype == "end_loop":
                _append(src_idx, getattr(step, "start_loop_id", None), "loop_back")
                continue
            _append(src_idx, getattr(step, "on_match_goto_id", None), "jump_true")
            _append(src_idx, getattr(step, "branch_on_fail_goto_id", None), "jump_false")

        self._flow_preview_cache[cache_key] = [tuple(e) for e in edges]
        if len(self._flow_preview_cache) > 96:
            # simple bounded cache (insertion-order in modern dicts)
            oldest_key = next(iter(self._flow_preview_cache.keys()))
            self._flow_preview_cache.pop(oldest_key, None)
        return edges

    def _on_flow_preview_requested(self, preview_rows: list):
        if not hasattr(self, "list") or not hasattr(self.list, "set_flow_edges"):
            return
        if not preview_rows:
            if self._flow_preview_active:
                id_to_index = {str(getattr(s, "id", "") or ""): i for i, s in enumerate(self.steps)}
                self.list.set_flow_edges(self._collect_step_flow_edges(id_to_index))
                self._flow_preview_active = False
            return

        temp_steps: list[StepData] = []
        used_obj_ids: set[int] = set()
        for raw in preview_rows:
            try:
                row = int(raw)
            except Exception:
                continue
            if row < 0 or row >= self.list.count():
                continue
            item = self.list.item(row)
            if item is None:
                continue
            step = item.data(Qt.UserRole)
            if step is None:
                continue
            temp_steps.append(step)
            used_obj_ids.add(id(step))
        if len(temp_steps) != len(self.steps):
            for step in self.steps:
                if id(step) in used_obj_ids:
                    continue
                temp_steps.append(step)
        if not temp_steps:
            return

        self.list.set_flow_edges(self._build_flow_preview_edges(temp_steps))
        self._flow_preview_active = True

    def _get_coordinate_overlay(self):
        overlay = getattr(self, "_coordinate_overlay", None)
        if overlay is None:
            overlay = CoordinateGuideOverlay.get_shared(self)
            self._coordinate_overlay = overlay
        return overlay

    def _set_coordinate_preview_suspended(self, suspended: bool):
        self._coordinate_preview_suspended = bool(suspended)
        if suspended:
            self._clear_coordinate_preview()

    def _is_coordinate_preview_blocked(self) -> bool:
        if bool(getattr(self, "_coordinate_preview_suspended", False)):
            return True
        if bool(getattr(self, "_excel_mode_running", False)):
            return True
        try:
            if self.runner and self.runner.isRunning():
                return True
        except Exception:
            pass
        return False

    def _load_image_size_cached(self, image_path: str | None, png_bytes: bytes | None):
        cache = getattr(self, "_coordinate_image_size_cache", None)
        if cache is None:
            cache = {}
            self._coordinate_image_size_cache = cache

        if image_path:
            key = ("path", os.path.normcase(os.path.abspath(str(image_path))))
            if key in cache:
                return cache[key]
            img = QImage(str(image_path))
            size = None if img.isNull() else (int(img.width()), int(img.height()))
            cache[key] = size
            return size

        if png_bytes:
            key = ("bytes", hash(bytes(png_bytes)))
            if key in cache:
                return cache[key]
            img = QImage()
            ok = img.loadFromData(png_bytes)
            size = None if (not ok or img.isNull()) else (int(img.width()), int(img.height()))
            cache[key] = size
            return size

        return None

    def _resolve_coordinate_preview_bbox(self, payload: dict):
        if not isinstance(payload, dict):
            return None
        ptype = str(payload.get("type", "") or "").lower()
        if ptype != "image_click":
            return None
        try:
            row = int(payload.get("index", 0)) - 1
        except Exception:
            return None
        if row < 0 or row >= len(self.steps):
            return None
        step = self.steps[row]
        image_path = str(payload.get("image_path", "") or "").strip()
        if image_path and not os.path.isabs(image_path):
            base_dir = os.path.dirname(self._current_macro_path) if self._current_macro_path else os.getcwd()
            image_path = os.path.abspath(os.path.join(base_dir, image_path))
        if not image_path:
            raw_path = str(getattr(step, "anchor_image_path", "") or getattr(step, "image_path", "") or "").strip()
            if raw_path:
                if os.path.isabs(raw_path):
                    image_path = raw_path
                else:
                    base_dir = os.path.dirname(self._current_macro_path) if self._current_macro_path else os.getcwd()
                    image_path = os.path.abspath(os.path.join(base_dir, raw_path))

        png_bytes = getattr(step, "png_bytes", None)
        size = self._load_image_size_cached(image_path or None, png_bytes)
        if not size:
            return None
        w, h = size
        if w <= 0 or h <= 0:
            return None
        return (int(w), int(h))

    def _on_coordinate_preview_requested(self, payload: dict):
        if self._is_coordinate_preview_blocked():
            return
        if not isinstance(payload, dict):
            return
        try:
            x = int(payload.get("x"))
            y = int(payload.get("y"))
            idx = int(payload.get("index", 0))
        except Exception:
            return
        stype = str(payload.get("type", "") or "")
        bbox = self._resolve_coordinate_preview_bbox(payload)
        overlay = self._get_coordinate_overlay()
        if overlay is None:
            return
        overlay.show_marker(x, y, idx, stype, bbox=bbox)

    def _clear_coordinate_preview(self):
        overlay = getattr(self, "_coordinate_overlay", None)
        if overlay is None:
            return
        try:
            overlay.clear_marker()
        except Exception:
            pass

    def _build_step_excel_preview(self, step: StepData, payload: dict) -> str:
        if not payload:
            return ""
        stype = str(getattr(step, "type", "") or "").lower()
        template = ""
        if stype == "text":
            template = str(getattr(step, "key_string", "") or "")
        elif stype == "keyboard":
            mode = str(getattr(step, "keyboard_mode", "") or "").lower()
            if mode == "text":
                template = str(getattr(step, "key_string", "") or "")
        if not template:
            return ""

        placeholders = self._extract_placeholders(template)
        if not placeholders:
            return ""

        rendered = TemplateProcessor.render(template, payload)
        unresolved = TemplateProcessor.has_unresolved_placeholder(rendered)

        token = placeholders[0]
        token_label = f"{{{{{token}}}}}"
        raw_val = self._lookup_excel_payload_value(payload, token)
        value = "" if raw_val is None else str(raw_val)
        if unresolved:
            return f"데이터 미리보기: {token_label} -> (미매핑)"
        shown = value if value else str(rendered or "")
        shown = shown.strip()
        if len(shown) > 48:
            shown = shown[:45] + "..."
        return f"데이터 미리보기: {token_label} -> {shown}"

    def _build_simulation_context(self) -> dict:
        payload = {}
        path = ""
        if hasattr(self, "edExcelDataPath"):
            try:
                path = str(self.edExcelDataPath.text() or "").strip()
            except Exception:
                path = ""
        if path and os.path.exists(path):
            try:
                loaded_rows = ExcelDataLoader.load_rows(path)
                if loaded_rows:
                    payload = dict(loaded_rows[0][1] or {})
            except Exception as e:
                self.warn(f"Simulation context load failed: {e}")
        if not payload:
            payload = self._get_excel_preview_payload()
        # Case-insensitive alias map for evaluator lookups.
        lowered = {}
        for k, v in payload.items():
            key = str(k or "")
            lk = key.lower()
            if lk and lk not in lowered:
                lowered[lk] = v
        merged = dict(payload)
        for lk, v in lowered.items():
            if lk not in merged:
                merged[lk] = v
        return merged

    def clear_logic_simulation_highlight(self):
        self._simulated_indices = set()
        if hasattr(self, "list") and hasattr(self.list, "set_simulated_indices"):
            self.list.set_simulated_indices([])

    def run_logic_simulation(self):
        if not self.steps:
            self.warn("시뮬레이션할 스텝이 없습니다.")
            self.clear_logic_simulation_highlight()
            return

        context = self._build_simulation_context()
        assume_sensor = bool(self.chkSensorAssume.isChecked()) if hasattr(self, "chkSensorAssume") else False
        evaluator = ConditionEvaluator()
        simulator = LogicPathSimulator(
            self.steps,
            context,
            evaluator=evaluator,
            max_hops=180,
            assume_sensor_match=assume_sensor,
        )
        start_idx = 0
        try:
            current = int(self.list.currentRow())
            if 0 <= current < len(self.steps):
                start_idx = current
        except Exception:
            start_idx = 0

        report = simulator.simulate(start_index=start_idx)
        self._simulated_indices = set(int(x) for x in report.visited_indices)
        if hasattr(self.list, "set_simulated_indices"):
            self.list.set_simulated_indices(self._simulated_indices)

        if report.visited_indices:
            visited = " -> ".join(f"#{i+1}" for i in report.visited_indices[:20])
            if len(report.visited_indices) > 20:
                visited += " -> ..."
            self.info(
                f"[Sim] visited {len(report.visited_indices)} step(s), "
                f"terminate={report.terminated_reason}, sensor_assume={assume_sensor}"
            )
            self.info(f"[Sim] path: {visited}")
        else:
            self.info(f"[Sim] no path (terminate={report.terminated_reason})")

        for warning in report.warnings[:5]:
            self.warn(f"[Sim] {warning}")

    def _build_excel_worker_note(self, event: dict) -> str:
        if not isinstance(event, dict):
            return ""
        if str(event.get("event") or "") != "job_dispatched":
            return ""
        job_id = str(event.get("job_id") or "").strip()
        if not job_id:
            return ""
        payload = dict(self._excel_payload_by_job_id.get(job_id) or {})
        if not payload:
            return ""

        consumer_id = str(event.get("consumer_id") or "worker")
        worker_match = re.search(r"(\d+)$", consumer_id)
        worker_name = f"Worker {worker_match.group(1)}" if worker_match else consumer_id

        template_text = str(self._get_excel_text_template() or "")
        resolved = ""
        token_label = ""
        token_value = ""
        if template_text.strip():
            resolved = TemplateProcessor.render(template_text, payload)
            token_match = re.search(r"\{\{\s*([^{}]+)\s*\}\}", template_text)
            if token_match is None:
                token_match = re.search(r"\{\s*([^{}]+)\s*\}", template_text)
            if token_match is not None:
                token_name = str(token_match.group(1) or "").strip()
                token_label = f"{{{{{token_name}}}}}"
                raw_value = self._lookup_excel_payload_value(payload, token_name)
                token_value = "" if raw_value is None else str(raw_value)
        if not resolved:
            fallback = payload.get("text")
            if fallback is None:
                fallback = payload.get("message")
            resolved = TemplateProcessor.render(str(fallback or ""), payload)
        resolved = str(resolved or "").strip()
        if token_label:
            shown_value = token_value if token_value else resolved
            return f"[{worker_name}] 처리 중: {token_label} -> {shown_value}"
        if not resolved:
            return f"[{worker_name}] 처리 중"
        if len(resolved) > 80:
            resolved = resolved[:77] + "..."
        return f"[{worker_name}] 처리 중: {resolved}"

    def _excel_monitor_loop(self):
        manager = self._excel_job_manager
        if manager is None:
            self.excelOrchFinished.emit(False, "orchestrator_missing")
            return
        try:
            while True:
                if manager.is_fully_done():
                    self.excelOrchFinished.emit(True, "completed")
                    return
                if self._excel_stop_event.is_set():
                    if manager.is_fully_done():
                        self.excelOrchFinished.emit(True, "completed")
                    else:
                        self.excelOrchFinished.emit(False, "stopped")
                    return
                sleep_sec = manager.get_recommended_sleep_sec(default_backoff=0.2)
                self._excel_stop_event.wait(timeout=max(0.05, float(sleep_sec)))
        except Exception as e:
            self.excelOrchFinished.emit(False, f"monitor_error: {e}")

    def _cleanup_excel_runtime(self):
        adapters = list(self._excel_adapters)
        for adapter in adapters:
            try:
                adapter.stop()
            except Exception:
                pass
        for adapter in adapters:
            try:
                adapter.join(1.0)
            except Exception:
                pass
        self._excel_adapters = []
        self._excel_payload_by_job_id = {}
        self._excel_mode_running = False
        self._excel_stop_event.set()

    def run_excel_orchestration(self):
        if self._excel_mode_running:
            self.warn("Excel orchestration is already running.")
            return
        if self.runner and self.runner.isRunning():
            self.warn("Cannot start Excel mode while macro is running.")
            return

        input_path = self.edExcelDataPath.text().strip() if hasattr(self, "edExcelDataPath") else ""
        if not input_path:
            self.warn("Excel data file path is empty.")
            return
        if not os.path.exists(input_path):
            self.err(f"Excel file not found: {input_path}")
            return

        try:
            loaded_rows = ExcelDataLoader.load_rows(input_path)
        except Exception as e:
            self.err(f"Excel data load failed: {e}")
            return

        if not loaded_rows:
            self.warn("No usable rows found in the selected Excel file.")
            return

        payload_rows = []
        self._excel_payload_by_job_id = {}
        for row_idx, payload in loaded_rows:
            p = dict(payload or {})
            p["__excel_row_index"] = int(row_idx)
            p["job_id"] = f"excel-{int(row_idx)}"
            payload_rows.append(p)
            self._excel_payload_by_job_id[p["job_id"]] = dict(payload or {})

        self._excel_total_jobs = len(payload_rows)
        self._excel_input_path = input_path
        self._excel_output_path = self._default_excel_output_path(input_path)
        self._excel_stop_event = threading.Event()
        self._excel_job_manager = JobQueueManager(
            payload_rows,
            max_retry=2,
            retry_delay_sec=0.2,
            result_sink=self._on_excel_result_sink_event,
        )
        self._excel_adapters = []

        requested = 1
        if hasattr(self, "spExcelParallelism"):
            requested = int(self.spExcelParallelism.value())
        parallelism = max(1, min(requested, len(payload_rows)))

        for idx in range(parallelism):
            adapter = self._build_excel_adapter(
                self._excel_job_manager,
                self._build_excel_payload_runner(),
                consumer_id=f"excel-{idx+1}",
                stop_event=threading.Event(),
            )
            self._excel_adapters.append(adapter)

        self._set_coordinate_preview_suspended(True)
        self._excel_mode_running = True
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)
        self.act_record.setEnabled(False)
        if hasattr(self, "btnRun"):
            self.btnRun.setEnabled(False)
        if hasattr(self, "btnStop"):
            self.btnStop.setEnabled(True)
        self._set_macro_paused_ui(False)
        if hasattr(self, "pbExcelProgress"):
            self.pbExcelProgress.setRange(0, self._excel_total_jobs)
            self.pbExcelProgress.setValue(0)
        if hasattr(self, "lblExcelStatus"):
            self.lblExcelStatus.setText(f"Excel: 0/{self._excel_total_jobs} (starting)")

        for adapter in self._excel_adapters:
            adapter.start()
        self._excel_monitor_thread = threading.Thread(
            target=self._excel_monitor_loop,
            name="ExcelOrchestrationMonitor",
            daemon=True,
        )
        self._excel_monitor_thread.start()
        self.info(f"Excel orchestration started: rows={self._excel_total_jobs}, workers={parallelism}")

    def _on_excel_orch_finished(self, completed: bool, reason: str):
        if not self._excel_job_manager:
            self._cleanup_excel_runtime()
            self._set_coordinate_preview_suspended(False)
            self.act_run.setEnabled(True)
            self.act_stop.setEnabled(False)
            self.act_record.setEnabled(True)
            if hasattr(self, "btnRun"):
                self.btnRun.setEnabled(True)
            if hasattr(self, "btnStop"):
                self.btnStop.setEnabled(False)
            self._sync_toolbar_run_stop_buttons()
            return

        snapshot = self._excel_job_manager.snapshot()
        self._render_excel_progress(snapshot, status_note=reason)

        if completed and self._excel_job_manager.is_fully_done():
            try:
                out_path = ExcelResultExporter.export_with_results(
                    self._excel_input_path,
                    self._excel_output_path or self._default_excel_output_path(self._excel_input_path),
                    snapshot,
                )
                self.info(f"Excel orchestration finished. Result saved: {out_path}")
            except Exception as e:
                self.err(f"Excel result export failed: {e}")
        else:
            self.warn(f"Excel orchestration stopped: {reason}")

        self._cleanup_excel_runtime()
        self._excel_job_manager = None
        self._set_coordinate_preview_suspended(False)
        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)
        self.act_record.setEnabled(True)
        if hasattr(self, "btnRun"):
            self.btnRun.setEnabled(True)
        if hasattr(self, "btnStop"):
            self.btnStop.setEnabled(False)
        self._set_macro_paused_ui(False)

    def _request_stop_excel_orchestration(self, reason: str = "user_stop"):
        if not self._excel_mode_running:
            return
        self.info(f"Stopping Excel orchestration ({reason})...")
        self._excel_stop_event.set()
        for adapter in list(self._excel_adapters):
            try:
                adapter.stop()
            except Exception:
                pass
        self.act_stop.setEnabled(False)
        if hasattr(self, "btnStop"):
            self.btnStop.setEnabled(False)
        self._sync_toolbar_run_stop_buttons()

    def _disable_all_hotkeys(self):
        for sc in getattr(self, "_qshortcuts", []):
            try:
                sc.setEnabled(False)
            except Exception as e:
                self.warn(f"Failed to disable a local shortcut: {e}")
        try:
            self._system_hotkeys.uninstall()
        except Exception as e:
            self.warn(f"Failed to uninstall system hotkeys: {e}")

    def _enable_all_hotkeys(self):
        for sc in getattr(self, "_qshortcuts", []):
            try:
                sc.setEnabled(True)
            except Exception as e:
                self.warn(f"Failed to enable a local shortcut: {e}")
        self._setup_global_hotkey_engine()

    def _open_hotkey_dialog(self):
        self._hotkey_dialog_open = True
        self._disable_all_hotkeys()
        try:
            dlg = HotkeySettingsDialog(
                self._hk_run,
                self._hk_stop,
                self._hk_record,
                self._hk_pause,
                self._hk_kill,
                self._hk_add_img,
                self._hk_add_notimg,
                self
            )
            if dlg.exec_() == QDialog.Accepted:
                res = dlg.result_hotkeys()
                if res:
                    (
                        hk_run,
                        hk_stop,
                        hk_record,
                        hk_pause,
                        hk_kill,
                        hk_add_img,
                        hk_add_notimg,
                    ) = res
                    conflicts = self._hotkey_conflicts(
                        {
                            "Run": hk_run,
                            "Stop": hk_stop,
                            "Record": hk_record,
                            "Pause/Resume": hk_pause,
                            "Emergency Kill": hk_kill,
                            "Add Image": hk_add_img,
                            "Add Action": hk_add_notimg,
                        }
                    )
                    if conflicts:
                        combo = sorted(conflicts.keys())[0]
                        labels = ", ".join(conflicts[combo])
                        QMessageBox.warning(
                            self,
                            "Hotkey Conflict",
                            f"이미 사용 중인 단축키입니다:\n{combo} ({labels})",
                        )
                        return
                    self._hk_run = hk_run
                    self._hk_stop = hk_stop
                    self._hk_record = hk_record
                    self._hk_pause = hk_pause
                    self._hk_kill = hk_kill
                    self._hk_add_img = hk_add_img
                    self._hk_add_notimg = hk_add_notimg
                    self._save_hotkeys()
                    self._update_hotkey_labels()
                    self._install_qshortcuts()
                    self._setup_global_hotkey_engine()
                    self.info("Hotkeys updated.")
        finally:
            self._hotkey_dialog_open = False
            self._enable_all_hotkeys()

    def _get_perf_level(self) -> int:
        try:
            cb = getattr(self, "cbPerfLevel", None)
            if cb:
                val = cb.currentData()
                return int(val) if val else 1
        except Exception as e:
            self.warn(f"Failed to read performance level; fallback to 1: {e}")
        return 1

    def _load_general_settings(self):
        """Load simple toggle settings such as Human Mode."""
        try:
            st = QSettings("ImageMacro", "MVP")
            human = st.value("general/human_mode", False, type=bool)
            self.chkHumanMode.setChecked(human)
            dbg = st.value("general/debug_overlay", False, type=bool)
            self.chkDebugOverlay.setChecked(dbg)
            smart_snap = st.value("general/smart_snap", True, type=bool)
            if hasattr(self, "chkSmartSnap"):
                self.chkSmartSnap.setChecked(bool(smart_snap))
            perf_playback = st.value("general/perf_playback", True, type=bool)
            if hasattr(self, "chkPerfPlayback"):
                self.chkPerfPlayback.setChecked(perf_playback)
            perf_recording = st.value("general/perf_recording", True, type=bool)
            if hasattr(self, "chkPerfRecording"):
                self.chkPerfRecording.setChecked(perf_recording)
            perf_level_raw = st.value("general/perf_level", 1)
            try:
                perf_level = int(perf_level_raw)
            except Exception:
                perf_level = 1
            if perf_level not in (1, 2, 3):
                perf_level = 1
            if hasattr(self, "cbPerfLevel"):
                idx = self.cbPerfLevel.findData(int(perf_level))
                if idx < 0:
                    idx = self.cbPerfLevel.findData(1)
                if idx < 0 and self.cbPerfLevel.count() > 0:
                    idx = 0
                if idx >= 0:
                    self.cbPerfLevel.setCurrentIndex(idx)
            # Always start with no target window selected on app startup.
            # Keep saving behavior intact for compatibility, but ignore persisted title here.
            if hasattr(self, "edTargetTitle"):
                self.edTargetTitle.clear()
            if not getattr(self, "_general_settings_signals_connected", False):
                self.chkHumanMode.toggled.connect(lambda _: self._save_general_settings())
                self.chkDebugOverlay.toggled.connect(lambda _: self._save_general_settings())
                if hasattr(self, "chkSmartSnap"):
                    self.chkSmartSnap.toggled.connect(lambda _: self._save_general_settings())
                if hasattr(self, "chkPerfPlayback"):
                    self.chkPerfPlayback.toggled.connect(lambda _: self._save_general_settings())
                if hasattr(self, "chkPerfRecording"):
                    self.chkPerfRecording.toggled.connect(lambda _: self._save_general_settings())
                if hasattr(self, "cbPerfLevel"):
                    self.cbPerfLevel.currentIndexChanged.connect(lambda _: self._save_general_settings())
                self._general_settings_signals_connected = True
        except Exception as e:
            self.warn(f"Failed to load general settings: {e}")

    def _save_general_settings(self):
        try:
            st = QSettings("ImageMacro", "MVP")
            st.setValue("general/human_mode", self.chkHumanMode.isChecked())
            st.setValue("general/debug_overlay", self.chkDebugOverlay.isChecked())
            if hasattr(self, "chkSmartSnap"):
                st.setValue("general/smart_snap", bool(self.chkSmartSnap.isChecked()))
            if hasattr(self, "chkPerfPlayback"):
                st.setValue("general/perf_playback", self.chkPerfPlayback.isChecked())
            if hasattr(self, "chkPerfRecording"):
                st.setValue("general/perf_recording", self.chkPerfRecording.isChecked())
            if hasattr(self, "cbPerfLevel"):
                st.setValue("general/perf_level", self._get_perf_level())
            st.setValue("general/target_window_title", self._get_target_window_title() if hasattr(self, "_get_target_window_title") else "")
        except Exception as e:
            self.warn(f"Failed to save general settings: {e}")

    def _install_qshortcuts(self):
        # Properly dispose previous shortcuts to avoid stacking duplicate handlers.
        for sc in getattr(self, "_qshortcuts", []):
            try:
                sc.setEnabled(False)
            except Exception as e:
                self._warn_once("shortcut_disable", f"Failed to disable previous shortcut: {e}")
            try:
                sc.activated.disconnect()
            except Exception as e:
                self._warn_once("shortcut_disconnect", f"Failed to disconnect previous shortcut signal: {e}")
            try:
                sc.deleteLater()
            except Exception as e:
                self._warn_once("shortcut_delete", f"Failed to dispose previous shortcut object: {e}")
        self._qshortcuts.clear()
        def make_sc(combo, slot):
            if not combo: return
            mods, base = hk_to_tuple(combo)
            if not base: return
            # Convert to QKeySequence format (e.g. "Ctrl+Shift+A")
            # Our hk_to_tuple returns set of mods and base string.
            # We need to construct a string that QKeySequence understands.
            key = base.upper()
            if len(key) == 1 and key.isalpha():
                seq = QKeySequence(
                    (Qt.CTRL if 'ctrl' in mods else Qt.NoModifier) |
                    (Qt.SHIFT if 'shift' in mods else Qt.NoModifier) |
                    (Qt.ALT if 'alt' in mods else Qt.NoModifier) |
                    (Qt.MetaModifier if 'win' in mods else Qt.NoModifier) |
                    getattr(Qt, f"Key_{key.upper()}")
                )
            else:
                parts = []
                if 'ctrl' in mods: parts.append("Ctrl")
                if 'shift' in mods: parts.append("Shift")
                if 'alt' in mods: parts.append("Alt")
                if 'win' in mods: parts.append("Meta")
                parts.append(key)
                seq = QKeySequence("+".join(parts))
            
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(slot)
            self._qshortcuts.append(sc)
            
        make_sc(self._hk_run, self._act_run_from_hotkey)
        make_sc(self._hk_stop, self._act_stop_from_hotkey)
        make_sc(self._hk_record, self._act_record_from_hotkey)
        make_sc(self._hk_pause, self._act_pause_resume_from_hotkey)
        make_sc(self._hk_kill, self._act_kill_from_hotkey)
        make_sc(self._hk_add_img, self.add_image_step)
        make_sc(self._hk_add_notimg, self.add_not_image_step)

    def _setup_global_hotkey_engine(self):
        # Always use system hotkeys on Windows if possible
        if sys.platform.startswith("win") and not self._hotkey_dialog_open:
            self._system_hotkeys.install()

    def _act_run_from_hotkey(self):
        if getattr(self, "_hotkey_dialog_open", False):
            return
        self.info("[Hotkey] Run")
        self._on_run_button_clicked()

    def _act_stop_from_hotkey(self):
        if getattr(self, "_hotkey_dialog_open", False):
            return
        self.info("[Hotkey] Stop")
        self.stop_macro()

    def _act_record_from_hotkey(self):
        if getattr(self, "_hotkey_dialog_open", False):
            return
        self.info("[Hotkey] Record Toggle")
        self.act_record.trigger()

    def _act_pause_resume_from_hotkey(self):
        if getattr(self, "_hotkey_dialog_open", False):
            return
        if not (self.runner and self.runner.isRunning()):
            self.info("[Hotkey] Pause/Resume ignored (no running macro)")
            self._set_macro_paused_ui(False)
            return
        try:
            if hasattr(self.runner, "is_paused") and self.runner.is_paused():
                if hasattr(self.runner, "resume_run") and self.runner.resume_run():
                    self.info("[Hotkey] Resumed")
                    self._set_macro_paused_ui(False)
                return
            if hasattr(self.runner, "pause") and self.runner.pause():
                self.info("[Hotkey] Paused")
                self._set_macro_paused_ui(True)
        except Exception as e:
            self.err(f"[Hotkey] Pause/Resume failed: {e}")

    def _act_kill_from_hotkey(self):
        if getattr(self, "_hotkey_dialog_open", False):
            return
        if not (self.runner and self.runner.isRunning()):
            self.info("[Hotkey] Kill ignored (no running macro)")
            return
        self.info("[Hotkey] Emergency Kill")
        try:
            if hasattr(self.runner, "kill"):
                self.runner.kill(reason="global_hotkey")
            else:
                self.runner.stop()
            self.act_stop.setEnabled(False)
            if hasattr(self, "btnStop"):
                self.btnStop.setEnabled(False)
            self._set_macro_paused_ui(False)
        except Exception as e:
            self.err(f"[Hotkey] Kill failed: {e}")

    # --- Recording ---
    def _load_record_settings(self):
        rs = self.config.load_record_settings()
        self.rec_typed_gap_ms = rs["typed_gap_ms"]
        self.rec_click_merge_ms = rs["click_merge_ms"]
        self.rec_click_radius_px = rs["click_radius_px"]
        self.rec_scroll_flush_ms = rs["scroll_flush_ms"]
        self.rec_scroll_scale_dx = rs["scroll_scale_dx"]
        self.rec_scroll_scale_dy = rs["scroll_scale_dy"]
        self.rec_record_delay_enabled = bool(rs.get("record_delay_enabled", False))

    def _save_record_settings(self):
        self.config.save_record_settings({
            "typed_gap_ms": self.rec_typed_gap_ms,
            "click_merge_ms": self.rec_click_merge_ms,
            "click_radius_px": self.rec_click_radius_px,
            "scroll_flush_ms": self.rec_scroll_flush_ms,
            "scroll_scale_dx": self.rec_scroll_scale_dx,
            "scroll_scale_dy": self.rec_scroll_scale_dy,
            "record_delay_enabled": self.rec_record_delay_enabled,
        })

    def _on_record_delay_toggle(self, checked: bool):
        self.rec_record_delay_enabled = bool(checked)
        self._save_record_settings()

    def _set_record_labels(self, recording: bool):
        shortcut_text = ""
        try:
            sc = self.act_record.shortcut() if getattr(self, "act_record", None) else None
            shortcut_text = sc.toString() if sc else ""
        except Exception as e:
            self._warn_once("record_label_shortcut_read", f"Failed to read record shortcut text: {e}")
        if not shortcut_text:
            try:
                shortcut_text = getattr(self, "_hk_record", "").upper()
            except Exception:
                shortcut_text = ""
        base = "녹화 정지" if recording else "녹화"
        label = f"{base} ({shortcut_text})" if shortcut_text else base
        for obj in (getattr(self, "act_record", None), getattr(self, "btnRecord", None)):
            try:
                if obj:
                    obj.setText(label)
            except Exception as e:
                self._warn_once("record_label_set_text", f"Failed to update record label text: {e}")

    def _open_record_settings(self):
        perf_recording = False
        perf_level = 1
        try:
            if hasattr(self, "chkPerfRecording"):
                perf_recording = bool(self.chkPerfRecording.isChecked())
            if hasattr(self, "cbPerfLevel"):
                perf_level = int(self.cbPerfLevel.currentData() or 1)
        except Exception:
            perf_level = 1
        dlg = RecordingSettingsDialog(
            self,
            (
                self.rec_typed_gap_ms,
                self.rec_click_merge_ms,
                self.rec_click_radius_px,
                self.rec_scroll_flush_ms,
                self.rec_scroll_scale_dx,
                self.rec_scroll_scale_dy,
            ),
            perf_recording=perf_recording,
            perf_level=perf_level,
        )
        if dlg.exec_() == QDialog.Accepted:
            (self.rec_typed_gap_ms, self.rec_click_merge_ms, self.rec_click_radius_px,
             self.rec_scroll_flush_ms, self.rec_scroll_scale_dx, self.rec_scroll_scale_dy) = dlg.values()
            self._save_record_settings()
            try:
                perf_recording, perf_level = dlg.perf_values()
            except Exception:
                perf_recording, perf_level = None, None
            if hasattr(self, "chkPerfRecording") and perf_recording is not None:
                chk = self.chkPerfRecording
                try:
                    chk.blockSignals(True)
                    chk.setChecked(bool(perf_recording))
                finally:
                    try:
                        chk.blockSignals(False)
                    except Exception as e:
                        self._warn_once("record_settings_chk_unblock", f"Failed to restore PerfRecording checkbox signals: {e}")
            if hasattr(self, "cbPerfLevel") and perf_level is not None:
                cb = self.cbPerfLevel
                try:
                    idx = cb.findData(int(perf_level))
                except Exception:
                    idx = -1
                if idx >= 0:
                    try:
                        cb.blockSignals(True)
                        cb.setCurrentIndex(idx)
                    finally:
                        try:
                            cb.blockSignals(False)
                        except Exception as e:
                            self._warn_once("record_settings_cb_unblock", f"Failed to restore PerfLevel combobox signals: {e}")
            self._save_general_settings()

    def _open_execution_history(self):
        try:
            dlg = ExecutionHistoryDialog(self)
            dlg.exec_()
        except Exception as e:
            self.warn(f"Failed to open execution history: {e}")

    def _open_user_guide(self):
        guide_path = get_resource_path("USER_GUIDE.md")
        if not os.path.exists(guide_path):
            # Fallback: beside executable in frozen deployments.
            try:
                guide_path = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "USER_GUIDE.md"))
            except Exception:
                guide_path = get_resource_path("USER_GUIDE.md")
        
        if os.path.exists(guide_path):
            try:
                import subprocess
                if sys.platform == "win32":
                    os.startfile(guide_path)
                elif sys.platform == "darwin":
                    subprocess.call(["open", guide_path])
                else:
                    subprocess.call(["xdg-open", guide_path])
            except Exception as e:
                QMessageBox.information(self, "User Guide", 
                    f"User guide location:\n{guide_path}\n\nError opening: {e}")
        else:
            QMessageBox.warning(self, "Not Found", f"User guide not found at:\n{guide_path}")
            self.info("Recording settings updated.")

    def _open_tesseract_settings(self):
        current = ""
        try:
            status = get_tesseract_status()
            current = str(status.get("cmd") or "")
        except Exception:
            current = ""
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select tesseract.exe",
            current,
            "Tesseract Executable (tesseract.exe);;Executable (*.exe);;All Files (*)",
        )
        if not fname:
            return
        if not save_tesseract_cmd_to_settings(fname):
            QMessageBox.warning(self, "OCR", "Failed to save Tesseract path in settings.")
            return
        cmd, source = configure_tesseract_cmd()
        self.info(f"OCR path configured: {cmd or fname} ({source})")

    def _maybe_prompt_tesseract_setup(self):
        # Keep startup headless-safe for tests/CI.
        if str(os.getenv("QT_QPA_PLATFORM", "") or "").strip().lower() == "offscreen":
            return
        if str(os.getenv("IMAGEMACRO_SKIP_TESSERACT_PROMPT", "") or "").strip().lower() in {"1", "true", "yes", "on"}:
            return
        try:
            cmd, _ = configure_tesseract_cmd()
            if cmd:
                return
        except Exception:
            return
        try:
            st = QSettings("ImageMacro", "MVP")
            prompted = str(st.value("ocr/prompted_missing_once", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
            if prompted:
                return
            st.setValue("ocr/prompted_missing_once", True)
        except Exception:
            pass

        reply = QMessageBox.question(
            self,
            "OCR Setup",
            "Tesseract 경로가 설정되지 않았습니다.\n"
            "OCR 기능을 사용하려면 경로를 지정하세요.\n\n"
            "지금 설정하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self._open_tesseract_settings()

    def _start_record(self):
        g = self.geometry()
        ignore_rect = QRect(g.x(), g.y(), g.width(), g.height())
        perf_recording = False
        try:
            perf_recording = bool(self.chkPerfRecording.isChecked())
        except Exception:
            perf_recording = False
        if perf_recording:
            level = self._get_perf_level()
            if level >= 3:
                max_queue_size = 100000
                move_min_distance_px = 0
            elif level == 2:
                max_queue_size = 50000
                move_min_distance_px = 0
            else:
                max_queue_size = 20000
                move_min_distance_px = 1
        else:
            max_queue_size = 5000
            move_min_distance_px = 3
        self.recorder = InputRecorder(
            ignore_rect, self,
            typed_gap_ms=self.rec_typed_gap_ms,
            click_merge_ms=self.rec_click_merge_ms,
            click_radius_px=self.rec_click_radius_px,
            scroll_flush_ms=self.rec_scroll_flush_ms,
            scroll_scale_dx=self.rec_scroll_scale_dx,
            scroll_scale_dy=self.rec_scroll_scale_dy,
            record_delay_enabled=self.rec_record_delay_enabled,
            max_queue_size=max_queue_size,
            move_min_distance_px=move_min_distance_px,
            ignore_combos=[self._hk_record]
        )
        self.recorder.finished.connect(self._on_record_done)
        self.recorder.pausedChanged.connect(lambda p: self.info(f"[Record] {'Paused' if p else 'Resumed'}"))
        self.recorder.start()

    def _stop_record(self, show_summary: bool = True):
        if not self.recorder:
            return
        self._record_show_summary = show_summary
        try:
            self.recorder.stop()
        except Exception as e:
            self.warn(f"Recorder stop error: {e}")
            self._record_show_summary = False
            self.recorder = None

    def _on_record_done(self, new_steps: list):
        recorder = getattr(self, "recorder", None)
        stats = {}
        if recorder:
            try:
                stats = recorder.metrics or {}
            except Exception:
                stats = {}
        show_summary = bool(getattr(self, "_record_show_summary", False))
        self._record_show_summary = False
        if recorder:
            self.recorder = None

        if not new_steps:
            self.info("No steps recorded.")
        else:
            insert_index = len(self.steps)
            focus_index = insert_index + len(new_steps) - 1
            self._push_command(
                AddStepsCommand(self.steps, new_steps, index=insert_index),
                focus_index=focus_index
            )
            self.info(f"Recorded {len(new_steps)} steps.")

        if show_summary:
            total = stats.get("total", 0)
            dropped_move = stats.get("dropped_move", 0)
            dropped_scroll = stats.get("dropped_scroll", 0)
            max_q = stats.get("max_queue", 0)
            msg = (
                "Recording Finished!\n"
                f"Total Events: {total}\n"
                f"Dropped (Moves): {dropped_move}\n"
                f"Dropped (Scrolls): {dropped_scroll}\n"
                f"Max Queue: {max_q}"
            )
            if getattr(self, "_file_logger", None):
                try:
                    self._file_logger.info(msg.replace("\n", " | "))
                except Exception as e:
                    self._warn_once("record_summary_file_logger", f"Failed to write recording summary to file logger: {e}")
            self.info(msg.replace("\n", " | "))
            try:
                self.statusBar().showMessage(msg.replace("\n", " | "), 4000)
            except Exception as e:
                self._warn_once("record_summary_statusbar", f"Failed to show recording summary in status bar: {e}")
            try:
                QMessageBox.information(self, "Recording Finished", msg)
            except Exception as e:
                self._warn_once("record_summary_dialog", f"Failed to show recording summary dialog: {e}")

    def _import_profile(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Import Profile', '', 'JSON Files (*.json)')
        if not fname: return
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                prof = json.load(f)
            
            hk = prof.get('hotkeys', {})
            if hk:
                self._hk_run = hk.get('run', self._hk_run)
                self._hk_stop = hk.get('stop', self._hk_stop)
                self._hk_record = hk.get('record', self._hk_record)
                self._hk_add_img = hk.get('add_img', self._hk_add_img)
                self._hk_add_notimg = hk.get('add_notimg', self._hk_add_notimg)
                self._hk_pause = hk.get('pause', self._hk_pause)
                self._hk_kill = hk.get('kill', self._hk_kill)
                self._save_hotkeys()
                self._update_hotkey_labels()
                self._install_qshortcuts()
                self._setup_global_hotkey_engine()
            
            self.info("Profile imported.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _export_profile(self):
        fname, _ = QFileDialog.getSaveFileName(self, 'Export Profile', '', 'JSON Files (*.json)')
        if not fname: return
        try:
            prof = {
                'hotkeys': {
                    'run': self._hk_run,
                    'stop': self._hk_stop,
                    'record': self._hk_record,
                    'add_img': self._hk_add_img,
                    'add_notimg': self._hk_add_notimg,
                    'pause': self._hk_pause,
                    'kill': self._hk_kill,
                }
            }
            with open(fname, 'w', encoding='utf-8') as f:
                json.dump(prof, f, indent=2)
            self.info(f"Profile exported to {fname}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def run_macro(self, start_index=0):
        if not self.steps:
            self.info("No steps to run.")
            return
        if self.runner and self.runner.isRunning():
            self.warn("Already running.")
            return
        self._set_coordinate_preview_suspended(True)
        self._set_macro_paused_ui(False)
        self._active_step_index = None
        self._last_failed_step_index = None
        self._last_failed_step_uuid = None
        if hasattr(self, "lblRuntimeStep"):
            self.lblRuntimeStep.setText("Run: Starting...")
        if hasattr(self, "lblRuntimeFail"):
            self.lblRuntimeFail.setText("Fail: -")
        self._apply_active_step_highlight()
            
        # Options
        dry_run = self.chkDry.isChecked() if hasattr(self, 'chkDry') else False
        mini_mode = self.chkAutoMin.isChecked() if hasattr(self, 'chkAutoMin') else False
        capture_on_fail = self.chkCaptureFail.isChecked() if hasattr(self, 'chkCaptureFail') else False
        human_mode = self.chkHumanMode.isChecked() if hasattr(self, 'chkHumanMode') else False
        perf_mode = True
        try:
            perf_mode = bool(self.chkPerfPlayback.isChecked())
        except Exception:
            perf_mode = True
        poll_interval = 0.1
        if perf_mode:
            level = self._get_perf_level()
            if level >= 3:
                poll_interval = 0.0
            elif level == 2:
                poll_interval = 0.01
            else:
                poll_interval = 0.05
        
        self.info(f"Starting macro... Human mode: {'ON' if human_mode else 'OFF'}, Perf: {'ON' if perf_mode else 'OFF'}")
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)
        self.act_record.setEnabled(False)
        
        # [Sync] Button State
        if hasattr(self, 'btnRun'):
            self.btnRun.setEnabled(False)
        if hasattr(self, 'btnStop'): self.btnStop.setEnabled(True)
        self._sync_toolbar_run_stop_buttons()
        
        # Convert cooldown sec to ms, max duration min to ms
        rc = RepeatConfig(
            repeat_count=self.sbRepeatCount.value(),
            repeat_cooldown_ms=int(self.sbCooldown.value() * 1000),
            stop_on_fail=self.cbStopOnFail.isChecked(),
            max_duration_ms=self.sbMaxDuration.value() * 60 * 1000
        )
        
        if mini_mode and not dry_run:
            self.showMinimized()
            self._was_minimized = True
        
        try:
            self.runner = MacroRunner(
                self.steps,
                repeat=rc,
                dry_run=dry_run,
                start_index=start_index,
                capture_on_fail=capture_on_fail,
                human_mode=human_mode,
                perf_mode=perf_mode,
                parent=self,
                current_file_path=self._current_macro_path,
                target_window_title=self._get_target_window_title() if hasattr(self, "_get_target_window_title") else "",
                structured_logging=True,
                auto_enter_after_text=bool(self.chkAutoEnterAfterText.isChecked()) if hasattr(self, "chkAutoEnterAfterText") else False,
            )
            try:
                self.runner.poll_interval = poll_interval
            except Exception as e:
                self.warn(f"Failed to set runner poll interval ({poll_interval}): {e}")
            if hasattr(self, "window_manager"):
                try:
                    self.runner._window_manager = self.window_manager
                except Exception as e:
                    self.warn(f"Failed to attach window manager to runner: {e}")
            try:
                self.runner.target_window_title = self._get_target_window_title()
            except Exception as e:
                self.warn(f"Failed to set target window title for runner: {e}")
            # Pre-activation using UI window manager (helps tests/mocks)
            try:
                if hasattr(self, "window_manager"):
                    title = self._get_target_window_title() if hasattr(self, "_get_target_window_title") else ""
                    if title:
                        hwnd = self.window_manager.find_window(title)
                        if hwnd:
                            self.window_manager.activate_window(hwnd)
            except Exception as e:
                self.warn(f"Runner pre-activation failed: {e}")
            self.runner.log.connect(self.info)
            self.runner.finished.connect(self._on_macro_finished)
            # Connect debug overlay events
            if hasattr(self.runner, "debugEvent"):
                self.runner.debugEvent.connect(self._on_debug_event)
            if hasattr(self.runner, "stepChanged"):
                self.runner.stepChanged.connect(self._on_runner_step_changed)
            if hasattr(self.runner, "stepStarted"):
                self.runner.stepStarted.connect(self._on_runner_step_started)
            if hasattr(self.runner, "stepSucceeded"):
                self.runner.stepSucceeded.connect(self._on_runner_step_succeeded)
            if hasattr(self.runner, "stepFailed"):
                self.runner.stepFailed.connect(self._on_runner_step_failed)
            self.runner.start()
        except Exception as e:
            self.err(f"Failed to start macro: {e}")
            self.runner = None
            self._set_coordinate_preview_suspended(False)
            self.act_run.setEnabled(True)
            self.act_stop.setEnabled(False)
            self.act_record.setEnabled(True)
            self._active_step_index = None
            self._last_failed_step_index = None
            self._last_failed_step_uuid = None
            if hasattr(self, "lblRuntimeStep"):
                self.lblRuntimeStep.setText("Run: Idle")
            if hasattr(self, "lblRuntimeFail"):
                self.lblRuntimeFail.setText("Fail: -")
            self._apply_active_step_highlight()
            if hasattr(self, "btnRun"):
                self.btnRun.setEnabled(True)
            if hasattr(self, "btnStop"):
                self.btnStop.setEnabled(False)
            self._sync_toolbar_run_stop_buttons()
            self._set_macro_paused_ui(False)
            if self._was_minimized:
                self.showNormal()
                self._was_minimized = False

    def stop_macro(self):
        if self._excel_mode_running:
            self._request_stop_excel_orchestration("manual_stop")
            return
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            self.info("Stopping macro...")
            self.act_stop.setEnabled(False)
            if hasattr(self, 'btnStop'): self.btnStop.setEnabled(False)
            self._set_macro_paused_ui(False)
        else:
            self.info("Macro is not running.")

    def _on_macro_finished(self, success):
        self.info(f"Macro finished. Success: {success}")
        self._set_coordinate_preview_suspended(False)
        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)
        self.act_record.setEnabled(True)
        self._set_macro_paused_ui(False)
        
        if self._was_minimized:
            self.showNormal()
            self._was_minimized = False
        
        # [Sync] Button State
        if hasattr(self, 'btnRun'):
            self.btnRun.setEnabled(True)
        if hasattr(self, 'btnStop'): self.btnStop.setEnabled(False)
        try:
            if hasattr(self.runner, "debugEvent"):
                self.runner.debugEvent.disconnect(self._on_debug_event)
        except Exception as e:
            self.warn(f"Failed to disconnect runner debugEvent: {e}")
        try:
            if hasattr(self.runner, "stepChanged"):
                self.runner.stepChanged.disconnect(self._on_runner_step_changed)
        except Exception as e:
            self.warn(f"Failed to disconnect runner stepChanged: {e}")
        try:
            if hasattr(self.runner, "stepStarted"):
                self.runner.stepStarted.disconnect(self._on_runner_step_started)
        except Exception as e:
            self.warn(f"Failed to disconnect runner stepStarted: {e}")
        try:
            if hasattr(self.runner, "stepSucceeded"):
                self.runner.stepSucceeded.disconnect(self._on_runner_step_succeeded)
        except Exception as e:
            self.warn(f"Failed to disconnect runner stepSucceeded: {e}")
        try:
            if hasattr(self.runner, "stepFailed"):
                self.runner.stepFailed.disconnect(self._on_runner_step_failed)
        except Exception as e:
            self.warn(f"Failed to disconnect runner stepFailed: {e}")
        self._active_step_index = None
        self._last_failed_step_index = None
        self._last_failed_step_uuid = None
        if hasattr(self, "lblRuntimeStep"):
            self.lblRuntimeStep.setText("Run: Idle")
        if hasattr(self, "lblRuntimeFail"):
            self.lblRuntimeFail.setText("Fail: -")
        self._apply_active_step_highlight()
        self.runner = None

    # --- Scheduler Logic ---

    def _load_scheduler_settings(self):
        """QSettings에서 스케줄러 설정을 로드합니다."""
        try:
            st = QSettings("ImageMacro", "MVP")
            
            default_time = QTime(9, 0)
            time_val = st.value(self.SCHED_KEY_TIME, default_time)
            paths = st.value(self.SCHED_KEY_MACROS, [])
            policy = st.value(self.SCHED_KEY_FAILURE_POLICY, MacroScheduler.FAILURE_CONTINUE)
            max_retries = st.value(self.SCHED_KEY_MAX_RETRIES, 1, type=int)
            retry_delay_ms = st.value(self.SCHED_KEY_RETRY_DELAY_MS, 1000, type=int)

            self.sched_time_edit.blockSignals(True)
            self.sched_time_edit.setTime(time_val)
            self.sched_time_edit.blockSignals(False)

            self.sched_failure_policy.blockSignals(True)
            idx = self.sched_failure_policy.findData(policy)
            if idx < 0:
                idx = self.sched_failure_policy.findData(MacroScheduler.FAILURE_CONTINUE)
            if idx >= 0:
                self.sched_failure_policy.setCurrentIndex(idx)
            self.sched_failure_policy.blockSignals(False)

            self.sched_retry_count.blockSignals(True)
            self.sched_retry_count.setValue(max(0, int(max_retries)))
            self.sched_retry_count.blockSignals(False)

            self.sched_retry_delay_ms.blockSignals(True)
            self.sched_retry_delay_ms.setValue(max(0, int(retry_delay_ms)))
            self.sched_retry_delay_ms.blockSignals(False)
            self._update_scheduler_retry_controls()
            
            self.sched_list.clear()
            for path in paths:
                self._add_path_to_sched_list(path)

            self._apply_scheduler_failure_settings()
            
            is_enabled = st.value(self.SCHED_KEY_ENABLED, False, type=bool)
            if is_enabled and self.sched_list.count() > 0:
                self.sched_btnToggle.setChecked(True)
            else:
                self.sched_btnToggle.setChecked(False)

        except Exception as e:
            self.info(f"[WARN] Failed to load scheduler settings: {e}")

    def _save_scheduler_settings(self):
        """스케줄러 설정을 QSettings에 저장합니다."""
        try:
            st = QSettings("ImageMacro", "MVP")
            
            time_val = self.sched_time_edit.time()
            paths = [self.sched_list.item(i).data(Qt.UserRole) 
                     for i in range(self.sched_list.count())]
            
            st.setValue(self.SCHED_KEY_TIME, time_val)
            st.setValue(self.SCHED_KEY_MACROS, paths)
            st.setValue(self.SCHED_KEY_ENABLED, self.sched_btnToggle.isChecked())
            st.setValue(self.SCHED_KEY_FAILURE_POLICY, self._get_sched_failure_policy())
            st.setValue(self.SCHED_KEY_MAX_RETRIES, int(self.sched_retry_count.value()))
            st.setValue(self.SCHED_KEY_RETRY_DELAY_MS, int(self.sched_retry_delay_ms.value()))

        except Exception as e:
            self.info(f"[WARN] Failed to save scheduler settings: {e}")

    def _get_sched_failure_policy(self) -> str:
        policy = MacroScheduler.FAILURE_CONTINUE
        try:
            selected = self.sched_failure_policy.currentData()
            if isinstance(selected, str) and selected in MacroScheduler.VALID_FAILURE_POLICIES:
                policy = selected
        except Exception:
            policy = MacroScheduler.FAILURE_CONTINUE
        return policy

    def _apply_scheduler_failure_settings(self):
        self._update_scheduler_retry_controls()
        policy = self._get_sched_failure_policy()
        retries = 0
        delay_ms = 0
        try:
            retries = int(self.sched_retry_count.value())
        except Exception:
            retries = 0
        try:
            delay_ms = int(self.sched_retry_delay_ms.value())
        except Exception:
            delay_ms = 0
        self.scheduler.set_failure_policy(policy)
        self.scheduler.set_retry_options(retries, delay_ms)

    def _on_sched_failure_settings_changed(self, *_):
        self._save_scheduler_settings()
        self._apply_scheduler_failure_settings()

    def _update_scheduler_retry_controls(self):
        if not hasattr(self, "sched_retry_count") or not hasattr(self, "sched_retry_delay_ms"):
            return
        use_retry_policy = self._get_sched_failure_policy() == MacroScheduler.FAILURE_RETRY
        self.sched_retry_count.setEnabled(use_retry_policy)
        self.sched_retry_delay_ms.setEnabled(use_retry_policy)

    def _on_scheduler_status_changed(self, status: str):
        if hasattr(self, "sched_status_label"):
            self.sched_status_label.setText(str(status))

    def _add_path_to_sched_list(self, path: str):
        if not path or not isinstance(path, str):
            return
            
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path)
        
        if not os.path.exists(path):
            item.setForeground(QColor("red"))
            item.setToolTip(f"File not found: {path}")

        self.sched_list.addItem(item)

    def _sched_add_macro(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Macro Files", "", "Macro (*.macro)")
        for path in paths:
            if path:
                self._add_path_to_sched_list(path)
        
        if paths:
            self._save_scheduler_settings()

    def _sched_remove_macro(self):
        selected_items = self.sched_list.selectedItems()
        if not selected_items: return
        for item in selected_items:
            self.sched_list.takeItem(self.sched_list.row(item))
        self._save_scheduler_settings()

    def _sched_move_up(self):
        current_row = self.sched_list.currentRow()
        if current_row > 0:
            item = self.sched_list.takeItem(current_row)
            self.sched_list.insertItem(current_row - 1, item)
            self.sched_list.setCurrentRow(current_row - 1)
            self._save_scheduler_settings()

    def _sched_move_down(self):
        current_row = self.sched_list.currentRow()
        if current_row < self.sched_list.count() - 1:
            item = self.sched_list.takeItem(current_row)
            self.sched_list.setCurrentRow(current_row + 1)
            self._save_scheduler_settings()

    def _on_sched_enable_changed(self, state):
        enabled = (state == Qt.Checked)
        self._sched_running = enabled
        
        queue = []
        if hasattr(self, 'sched_list'):
            for i in range(self.sched_list.count()):
                item = self.sched_list.item(i)
                path = item.data(Qt.UserRole)
                if path:
                    queue.append(path)
        
        self.scheduler.set_macro_queue(queue)
        self.scheduler.set_target_time(self.sched_time_edit.time())
        self._apply_scheduler_failure_settings()
        self.scheduler.set_enabled(enabled)

    def _check_schedule(self):
        """Minimal scheduler tick used in tests."""
        if getattr(self, "sched_btnToggle", None) and self.sched_btnToggle.isChecked():
            try:
                self._run_scheduled_sequence()
                self._sched_ran_today = True
            except AttributeError:
                # Fallback: run the scheduler's check if defined
                if hasattr(self, "scheduler") and hasattr(self.scheduler, "run"):
                    try:
                        self.scheduler.run()
                    except Exception as e:
                        self.warn(f"Scheduler fallback run failed: {e}")

    def _run_scheduled_sequence(self):
        """Placeholder for scheduled run; tests may monkeypatch this."""
        if hasattr(self, "scheduler"):
            try:
                self.scheduler.run()
            except Exception as e:
                self.warn(f"Scheduled sequence run failed: {e}")

    def _run_scheduled_macro(self, path):
        base_name = os.path.basename(path)
        self._on_scheduler_status_changed(f"Status: Running {base_name}")
        
        if self._load_macro_from_path(path):
            try:
                self.runner.finished.disconnect(self._on_scheduled_run_finished)
            except Exception as e:
                self.warn(f"Failed to disconnect scheduled finished handler: {e}")
            
            self.run_macro()
            if self.runner:
                self.runner.finished.connect(self._on_scheduled_run_finished)
            else:
                self.warn(f"[Scheduler] Failed to start {base_name}")
                self.scheduler.notify_macro_finished(False)
        else:
            self.info(f"[Scheduler] Failed to load {base_name}")
            self.scheduler.notify_macro_finished(False)

    def _on_scheduled_run_finished(self, ok=True):
        self.scheduler.notify_macro_finished(ok)

    # --- Preset Logic ---

    def _refresh_preset_list(self):
        if not hasattr(self, "presetList"):
            return
        directory = getattr(self, "_preset_dir", None) or self._compute_preset_dir()
        self._preset_dir = directory
        if hasattr(self, "lblPresetDir"):
            self.lblPresetDir.setText(directory)
        self.presetList.clear()
        try:
            entries = sorted(
                [
                    name
                    for name in os.listdir(directory)
                    if name.lower().endswith(".macro")
                ]
            )
        except Exception:
            entries = []

        if not entries:
            if hasattr(self, "lblPresetStatus"):
                self.lblPresetStatus.setText(".macro 파일을 찾지 못했습니다.")
            return

        for name in entries:
            full_path = os.path.join(directory, name)
            item = QListWidgetItem(name)
            item.setToolTip(full_path)
            item.setData(Qt.UserRole, full_path)
            self.presetList.addItem(item)
        if hasattr(self, "lblPresetStatus"):
            self.lblPresetStatus.setText(f"{len(entries)}개의 프리셋을 찾았습니다.")

    def _load_preset_item(self, item):
        if item:
            self.presetList.setCurrentItem(item)
            self._load_selected_preset()

    def _load_selected_preset(self):
        if not hasattr(self, "presetList"):
            return
        item = self.presetList.currentItem()
        if item is None:
            if hasattr(self, "lblPresetStatus"):
                self.lblPresetStatus.setText("먼저 프리셋을 선택하세요.")
            return
        path = item.data(Qt.UserRole)
        if not path:
            return
        if self._load_macro_from_path(path):
            if hasattr(self, "lblPresetStatus"):
                base = os.path.basename(path)
                self.lblPresetStatus.setText(f"불러오기 완료: {base}")

    def _compute_preset_dir(self) -> str:
        try:
            if getattr(sys, "frozen", False):
                return os.path.abspath(os.path.dirname(sys.executable))
        except Exception as e:
            self._warn_once("compute_preset_dir_frozen", f"Failed to resolve frozen executable directory: {e}")
        try:
            base = os.path.abspath(os.path.dirname(__file__))
        except Exception:
            base = os.getcwd()
        return base

    def closeEvent(self, e):
        def _shutdown_safe(label: str, fn):
            try:
                fn()
            except Exception as ex:
                try:
                    self.err(f"Shutdown cleanup failed ({label}): {ex}")
                except Exception:
                    print(f"[WARN] Shutdown cleanup failed ({label}): {ex}")

        _shutdown_safe("coordinate_preview", self._clear_coordinate_preview)
        _shutdown_safe(
            "runner",
            lambda: (
                self.runner.stop(),
                self.runner.wait(2000),
            ) if self.runner and self.runner.isRunning() else None,
        )
        _shutdown_safe("excel_orchestration", lambda: self._request_stop_excel_orchestration("window_close"))
        _shutdown_safe("excel_runtime_cleanup", self._cleanup_excel_runtime)
        _shutdown_safe(
            "recorder",
            lambda: self._stop_record(show_summary=False) if self.recorder else None,
        )
        _shutdown_safe(
            "trigger_watcher",
            lambda: self.trigger_watcher.stop()
            if getattr(self, "trigger_watcher", None) and self.trigger_watcher.isRunning()
            else None,
        )
        _shutdown_safe(
            "trigger_runner",
            lambda: (
                self.trigger_runner.stop(),
                self.trigger_runner.wait(2000),
            )
            if getattr(self, "trigger_runner", None) and self.trigger_runner.isRunning()
            else None,
        )
        _shutdown_safe(
            "scheduler",
            lambda: (
                self.scheduler.set_enabled(False),
                self.scheduler.timer.stop(),
            )
            if getattr(self, "scheduler", None)
            else None,
        )
        _shutdown_safe("hotkeys", lambda: self._system_hotkeys.uninstall())
        _shutdown_safe("save_general_settings", lambda: self._save_general_settings())
        super().closeEvent(e)

    def _refresh_trigger_list(self):
        self.trigger_list.clear()
        for t in self.triggers:
            item = QListWidgetItem(f"{t.name} ({'ON' if t.enabled else 'OFF'})")
            item.setData(Qt.UserRole, t)
            if not t.enabled:
                item.setForeground(QColor("gray"))
            self.trigger_list.addItem(item)

    def _add_trigger(self):
        t = TriggerData(id=str(uuid.uuid4())[:8], name="New Trigger")
        # Default condition step is created in __init__ of TriggerData
        
        dlg = TriggerEditDialog(t, self)
        if dlg.exec_() == QDialog.Accepted:
            self.triggers.append(t)
            self._refresh_trigger_list()
            self._save_triggers()
            self.trigger_watcher.update_triggers(self.triggers)

    def _on_debug_event(self, data: dict):
        if not self.chkDebugOverlay.isChecked():
            return
        rect = data.get("rect") or (0, 0, 50, 50)
        text = data.get("text", "")
        color = data.get("color", (0, 255, 0))
        try:
            self.debug_overlay.add_event(rect, text=text, color=color, duration=2.0)
            if not self.debug_overlay.isVisible():
                self.debug_overlay.show()
                self.debug_overlay.raise_()
        except Exception as e:
            self._warn_once("debug_overlay_event", f"Failed to render debug overlay event: {e}")

    def _edit_trigger_item(self, item):
        t = item.data(Qt.UserRole)
        dlg = TriggerEditDialog(t, self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_trigger_list()
            self._save_triggers()
            self.trigger_watcher.update_triggers(self.triggers)

    def _del_trigger(self):
        row = self.trigger_list.currentRow()
        if row >= 0:
            self.triggers.pop(row)
            self._refresh_trigger_list()
            self._save_triggers()
            self.trigger_watcher.update_triggers(self.triggers)

    def _trigger_storage_dir(self) -> str:
        try:
            base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or ""
        except Exception:
            base = ""
        if not base:
            try:
                base = os.path.join(os.path.expanduser("~"), ".imagemacro")
            except Exception:
                base = os.getcwd()
        path = os.path.join(base, "triggers")
        os.makedirs(path, exist_ok=True)
        return path

    def _trigger_json_path(self) -> str:
        return os.path.join(self._trigger_storage_dir(), "triggers.json")

    def _trigger_image_dir(self) -> str:
        path = os.path.join(self._trigger_storage_dir(), "images")
        os.makedirs(path, exist_ok=True)
        return path

    def _legacy_trigger_json_path(self) -> str:
        return os.path.join(os.getcwd(), "triggers.json")

    def _legacy_trigger_image_dir(self) -> str:
        return os.path.join(os.getcwd(), "triggers", "images")

    def _resolve_trigger_sources(self) -> tuple[str | None, list[str]]:
        primary_json = self._trigger_json_path()
        legacy_json = self._legacy_trigger_json_path()
        source_json = primary_json if os.path.exists(primary_json) else None
        if source_json is None and os.path.exists(legacy_json):
            source_json = legacy_json

        image_dirs = []
        primary_image = self._trigger_image_dir()
        legacy_image = self._legacy_trigger_image_dir()
        if source_json:
            source_image = os.path.join(os.path.dirname(source_json), "images")
            image_dirs.append(source_image)
        image_dirs.extend([primary_image, legacy_image])

        seen = set()
        deduped = []
        for d in image_dirs:
            k = os.path.abspath(d)
            if k in seen:
                continue
            seen.add(k)
            deduped.append(d)
        return source_json, deduped

    def _load_triggers(self):
        try:
            src_json, image_dirs = self._resolve_trigger_sources()
            if not src_json:
                return

            with open(src_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.triggers.clear()
            for d in data:
                t = TriggerData.from_dict(d)
                
                # Load image if exists
                s = t.condition_step
                if s.type == 'image_click':
                    for img_dir in image_dirs:
                        img_path = os.path.join(img_dir, f"{s.id}.png")
                        if os.path.exists(img_path):
                            with open(img_path, "rb") as imgf:
                                s.png_bytes = imgf.read()
                                s.ensure_tpl()
                            break
                
                self.triggers.append(t)
                
            self.trigger_watcher.update_triggers(self.triggers)
            # If loaded from legacy location, migrate to the new app-data location.
            if os.path.abspath(src_json) == os.path.abspath(self._legacy_trigger_json_path()):
                self._save_triggers()
        except Exception as e:
            self.err(f"Failed to load triggers: {e}")

    def _save_triggers(self):
        try:
            image_dir = self._trigger_image_dir()
            json_path = self._trigger_json_path()
                
            data = []
            for t in self.triggers:
                d = t.to_dict()
                # Save image bytes to file
                s = t.condition_step
                if s.png_bytes:
                    with open(os.path.join(image_dir, f"{s.id}.png"), "wb") as f:
                        f.write(s.png_bytes)
                    # Remove bytes from json to keep it clean
                    d['condition_step'].pop('png_bytes', None)
                    d['condition_step'].pop('_tpl_bgr', None)
                    d['condition_step'].pop('_tpl_mask', None)
                
                data.append(d)
                
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.err(f"Failed to save triggers: {e}")

    def _resume_paused_runner(self) -> bool:
        paused_runner = self._paused_runner
        if not paused_runner:
            self._resume_state = None
            return False

        try:
            self.runner = paused_runner
            self._set_macro_paused_ui(False)
            self.act_run.setEnabled(False)
            self.act_stop.setEnabled(True)
            self.act_record.setEnabled(False)
            if hasattr(self, "btnRun"):
                self.btnRun.setEnabled(False)
            if hasattr(self, "btnStop"):
                self.btnStop.setEnabled(True)
            self._sync_toolbar_run_stop_buttons()
            if hasattr(self.runner, "debugEvent"):
                try:
                    self.runner.debugEvent.disconnect(self._on_debug_event)
                except Exception as e:
                    self.warn(f"Failed to refresh debugEvent connection on resume: {e}")
                self.runner.debugEvent.connect(self._on_debug_event)
            if hasattr(self.runner, "stepChanged"):
                try:
                    self.runner.stepChanged.disconnect(self._on_runner_step_changed)
                except Exception as e:
                    self.warn(f"Failed to refresh stepChanged connection on resume: {e}")
                self.runner.stepChanged.connect(self._on_runner_step_changed)
            if hasattr(self.runner, "stepStarted"):
                try:
                    self.runner.stepStarted.disconnect(self._on_runner_step_started)
                except Exception as e:
                    self.warn(f"Failed to refresh stepStarted connection on resume: {e}")
                self.runner.stepStarted.connect(self._on_runner_step_started)
            if hasattr(self.runner, "stepSucceeded"):
                try:
                    self.runner.stepSucceeded.disconnect(self._on_runner_step_succeeded)
                except Exception as e:
                    self.warn(f"Failed to refresh stepSucceeded connection on resume: {e}")
                self.runner.stepSucceeded.connect(self._on_runner_step_succeeded)
            if hasattr(self.runner, "stepFailed"):
                try:
                    self.runner.stepFailed.disconnect(self._on_runner_step_failed)
                except Exception as e:
                    self.warn(f"Failed to refresh stepFailed connection on resume: {e}")
                self.runner.stepFailed.connect(self._on_runner_step_failed)

            if hasattr(self.runner, "resume"):
                self.runner.resume(self._resume_index, self._resume_state)
            else:
                self.runner.start_index = int(self._resume_index)
                self.runner.start()
            return True
        except Exception as e:
            self.err(f"[Trigger] Failed to resume paused macro: {e}")
            self.runner = None
            return False
        finally:
            self._resume_state = None
            self._paused_runner = None

    def _on_trigger_fired(self, t: TriggerData):
        if self._main_runner_paused:
            self.info(f"[Trigger] Ignored {t.name} (Already handling a trigger)")
            return

        self.info(f"!!! TRIGGER FIRED: {t.name} !!!")
        
        if t.action_type == "notification":
            self.info(f"[Notification] {t.action_value}")
            return
            
        elif t.action_type == "stop":
            self.stop_macro()
            return
            
        elif t.action_type == "run_macro":
            macro_path = os.path.expandvars(os.path.expanduser(t.action_value or "")).strip()
            if macro_path and not os.path.isabs(macro_path) and self._current_macro_path:
                try:
                    base = os.path.dirname(os.path.abspath(self._current_macro_path))
                    macro_path = os.path.abspath(os.path.join(base, macro_path))
                except Exception as e:
                    self.warn(f"[Trigger] Failed to resolve relative macro path '{macro_path}': {e}")
            if not os.path.exists(macro_path):
                self.err(f"[Trigger] Macro file not found: {macro_path}")
                return
                
            if self.runner and self.runner.isRunning():
                paused_runner = self.runner
                self._main_runner_paused = True
                self._paused_runner = paused_runner
                
                # Capture current step index before stopping
                self._resume_index = paused_runner.current_step_index
                self._resume_state = None
                if hasattr(paused_runner, "snapshot_state"):
                    try:
                        self._resume_state = paused_runner.snapshot_state()
                    except Exception:
                        self._resume_state = None
                self.info(f"[Trigger] Pausing main macro at step {self._resume_index + 1}...")
                
                paused_runner.stop()
                paused_runner.wait(1000)
                
                try:
                    trigger_steps = self._load_steps_from_file(macro_path)
                    if not trigger_steps:
                        self._main_runner_paused = False
                        self.warn("[Trigger] Trigger macro load failed; resuming main macro.")
                        self._resume_paused_runner()
                        return

                    self.trigger_runner = MacroRunner(
                        trigger_steps,
                        parent=self,
                        current_file_path=macro_path,
                        structured_logging=True,
                        auto_enter_after_text=bool(self.chkAutoEnterAfterText.isChecked()) if hasattr(self, "chkAutoEnterAfterText") else False,
                    )
                    self.trigger_runner.finished.connect(self._on_trigger_finished)
                    self.trigger_runner.log.connect(self.info)
                    self.trigger_runner.start()
                    
                except Exception as e:
                    self.err(f"[Trigger] Failed to load macro: {e}")
                    self._main_runner_paused = False
                    self._resume_paused_runner()
            else:
                trigger_steps = self._load_steps_from_file(macro_path)
                if not trigger_steps:
                    self.err(f"[Trigger] Failed to load trigger macro: {macro_path}")
                    return
                try:
                    self.trigger_runner = MacroRunner(
                        trigger_steps,
                        parent=self,
                        current_file_path=macro_path,
                        structured_logging=True,
                        auto_enter_after_text=bool(self.chkAutoEnterAfterText.isChecked()) if hasattr(self, "chkAutoEnterAfterText") else False,
                    )
                    self.trigger_runner.finished.connect(self._on_trigger_finished)
                    self.trigger_runner.log.connect(self.info)
                    self.trigger_runner.start()
                except Exception as e:
                    self.err(f"[Trigger] Failed to start trigger macro: {e}")
                    self.trigger_runner = None

    def _load_steps_from_file(self, path):
        # Helper to load steps without affecting UI.
        # Supports JSON (.json/.macro-json) and zip-based .macro files.
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = self._decode_bytes(json.load(f))
            if isinstance(data, list):
                return [self._coerce_step(self._decode_bytes(s)) for s in data]
            if isinstance(data, dict):
                steps_data = data.get("steps", []) or []
                return [self._coerce_step(self._decode_bytes(s)) for s in steps_data]
        except Exception:
            self.warn(f"[Trigger] JSON step load failed for '{path}', trying MacroIO format.")
        try:
            steps, _ = MacroIO.load_macro(path)
            return [self._coerce_step(self._decode_bytes(s)) for s in steps]
        except Exception:
            return None

    def _on_trigger_finished(self, success):
        self.info(f"[Trigger] Finished. Success: {success}")
        self.trigger_runner = None
        
        if self._main_runner_paused:
            self.info(f"[Trigger] Resuming main macro from step {self._resume_index + 1}...")
            self._main_runner_paused = False
            if not self._resume_paused_runner():
                self.warn("[Trigger] Main macro resume was requested, but runner was unavailable.")

    def _on_trigger_log(self, msg: str):
        if msg == "Trigger Watcher Started." and not self._show_trigger_start_log:
            return
        self.info(msg)

    def _init_trigger_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.trigger_list = QListWidget()
        self.trigger_list.itemDoubleClicked.connect(self._edit_trigger_item)
        
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add Trigger")
        btn_add.clicked.connect(self._add_trigger)
        btn_del = QPushButton("Del Trigger")
        btn_del.clicked.connect(self._del_trigger)
        
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        
        layout.addWidget(QLabel("Background Triggers (Watchdog)"))
        layout.addWidget(self.trigger_list)
        layout.addLayout(btn_layout)
        
        self.triggers = []
        self.trigger_watcher = TriggerWatcher(self.triggers, self)
        self.trigger_watcher.triggerFired.connect(self._on_trigger_fired)
        self.trigger_watcher.log.connect(self._on_trigger_log)
        self.trigger_watcher.start()
        
        self._load_triggers()
        self._refresh_trigger_list()
        
        return widget

    def _create_right_tab_panel(self):
        tabs = QTabWidget()
        
        # --- 1. Presets Tab (Create & Add First) ---
        preset_tab = QWidget()
        preset_layout = QVBoxLayout(preset_tab)
        
        self.lblPresetDir = QLabel()
        self.lblPresetDir.setStyleSheet("color: gray; font-size: 10px;")
        self.presetList = QListWidget()
        self.presetList.itemDoubleClicked.connect(self._load_preset_item)
        self.lblPresetStatus = QLabel("Ready")
        
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_preset_list)
        
        preset_layout.addWidget(QLabel("Presets (.macro)"))
        preset_layout.addWidget(self.lblPresetDir)
        preset_layout.addWidget(self.presetList)
        preset_layout.addWidget(btn_refresh)
        preset_layout.addWidget(self.lblPresetStatus)
        
        self._refresh_preset_list()
        
        tabs.addTab(preset_tab, "Presets")
        
        # --- 2. Scheduler Tab (Create & Add Second) ---
        sched_tab = QWidget()
        sched_layout = QVBoxLayout(sched_tab)
        
        # Macro List
        self.sched_list = QListWidget()
        sched_layout.addWidget(self.sched_list)
        
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self._sched_add_macro)
        btn_rem = QPushButton("Remove")
        btn_rem.clicked.connect(self._sched_remove_macro)
        btn_up = QPushButton("Up")
        btn_up.clicked.connect(self._sched_move_up)
        btn_down = QPushButton("Down")
        btn_down.clicked.connect(self._sched_move_down)
        
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_rem)
        btn_layout.addWidget(btn_up)
        btn_layout.addWidget(btn_down)
        sched_layout.addLayout(btn_layout)
        
        form = QFormLayout()
        self.sched_time_edit = QTimeEdit()
        self.sched_time_edit.setDisplayFormat("HH:mm")
        self.sched_time_edit.timeChanged.connect(self._save_scheduler_settings)
        
        self.sched_enable_chk = QCheckBox("Enable Scheduler")
        self.sched_enable_chk.stateChanged.connect(self._on_sched_enable_changed)
        # Alias for tests expecting a toggle button with setChecked
        self.sched_btnToggle = self.sched_enable_chk

        self.sched_failure_policy = QComboBox()
        self.sched_failure_policy.addItem("On Fail: Continue Next", MacroScheduler.FAILURE_CONTINUE)
        self.sched_failure_policy.addItem("On Fail: Stop Sequence", MacroScheduler.FAILURE_STOP)
        self.sched_failure_policy.addItem("On Fail: Retry Then Continue", MacroScheduler.FAILURE_RETRY)
        self.sched_failure_policy.currentIndexChanged.connect(self._on_sched_failure_settings_changed)

        self.sched_retry_count = QSpinBox()
        self.sched_retry_count.setRange(0, 10)
        self.sched_retry_count.setValue(1)
        self.sched_retry_count.valueChanged.connect(self._on_sched_failure_settings_changed)

        self.sched_retry_delay_ms = QSpinBox()
        self.sched_retry_delay_ms.setRange(0, 60000)
        self.sched_retry_delay_ms.setSingleStep(100)
        self.sched_retry_delay_ms.setSuffix(" ms")
        self.sched_retry_delay_ms.setValue(1000)
        self.sched_retry_delay_ms.valueChanged.connect(self._on_sched_failure_settings_changed)
        
        form.addRow("Run Time:", self.sched_time_edit)
        form.addRow(self.sched_enable_chk)
        form.addRow("Failure Policy:", self.sched_failure_policy)
        form.addRow("Retry Count:", self.sched_retry_count)
        form.addRow("Retry Delay:", self.sched_retry_delay_ms)
        
        self.sched_status_label = QLabel("Status: Idle")
        sched_layout.addLayout(form)
        sched_layout.addWidget(self.sched_status_label)
        
        tabs.addTab(sched_tab, "Scheduler")
        
        # Settings Tab (Repeat Config)
        settings_tab = QWidget()
        settings_layout = QFormLayout(settings_tab)
        
        self.sbRepeatCount = QSpinBox()
        self.sbRepeatCount.setRange(0, 9999)
        self.sbRepeatCount.setValue(1)
        self.sbRepeatCount.setSpecialValueText("Infinite")
        
        self.sbCooldown = QDoubleSpinBox()
        self.sbCooldown.setRange(0, 3600)
        self.sbCooldown.setValue(0)
        self.sbCooldown.setSuffix(" s")
        
        self.cbStopOnFail = QCheckBox("Stop on Fail")
        self.cbStopOnFail.setChecked(True)
        
        self.sbMaxDuration = QSpinBox()
        self.sbMaxDuration.setRange(0, 1440) # 24 hours
        self.sbMaxDuration.setValue(0)
        self.sbMaxDuration.setSuffix(" min")
        
        settings_layout.addRow("Repeat Count (0=Inf):", self.sbRepeatCount)
        settings_layout.addRow("Cooldown:", self.sbCooldown)
        settings_layout.addRow("Max Duration:", self.sbMaxDuration)
        settings_layout.addRow(self.cbStopOnFail)

        self.chkPerfPlayback = QCheckBox("High Performance Playback")
        self.chkPerfPlayback.setChecked(True)
        self.chkPerfPlayback.setToolTip("Reduce internal sleeps and pyautogui delays.")
        settings_layout.addRow(self.chkPerfPlayback)

        self.chkPerfRecording = QCheckBox("High Performance Recording")
        self.chkPerfRecording.setChecked(True)
        self.chkPerfRecording.setToolTip("Increase recorder buffer and capture rate.")
        settings_layout.addRow(self.chkPerfRecording)

        self.cbPerfLevel = QComboBox()
        self.cbPerfLevel.addItem("Performance Level 1", 1)
        self.cbPerfLevel.addItem("Performance Level 2", 2)
        self.cbPerfLevel.addItem("Performance Level 3", 3)
        settings_layout.addRow("Perf Level:", self.cbPerfLevel)

        self.chkRecordDelay = QCheckBox("Record Action Delays")
        self.chkRecordDelay.setChecked(bool(getattr(self, "rec_record_delay_enabled", False)))
        self.chkRecordDelay.setToolTip("Capture real time gaps between actions during recording.")
        self.chkRecordDelay.toggled.connect(self._on_record_delay_toggle)
        settings_layout.addRow(self.chkRecordDelay)
        
        btn_rec_settings = QPushButton("Recording Settings")
        btn_rec_settings.clicked.connect(self._open_record_settings)
        settings_layout.addRow(btn_rec_settings)
        
        btn_hotkeys = QPushButton("Hotkey Settings")
        btn_hotkeys.clicked.connect(self._open_hotkey_dialog)
        settings_layout.addRow(btn_hotkeys)
        
        tabs.addTab(settings_tab, "Settings")
        
        return tabs

    # --- Floating "Open Panel" button ----------------------------------
    def _init_open_panel_button(self):
        try:
            self.btn_open_panel = QPushButton("◀", self)
            self.btn_open_panel.setFixedSize(24, 64)
            self.btn_open_panel.setStyleSheet(
                "background:#444;color:white;border:1px solid #222;"
                "border-radius:4px; font-weight:bold;"
            )
            self.btn_open_panel.setVisible(False)
            self.btn_open_panel.clicked.connect(self._restore_right_panel)
            self.btn_open_panel.raise_()
            self._reposition_open_panel_button()
        except Exception as e:
            self._warn_once("open_panel_init", f"Failed to initialize floating open-panel button: {e}")

    def _on_splitter_moved(self, pos, index):
        try:
            sizes = self.splitter.sizes()
            right_size = sizes[2] if len(sizes) > 2 else 0
            show_btn = right_size <= 5
            self.btn_open_panel.setVisible(show_btn)
            if show_btn:
                self._reposition_open_panel_button()
        except Exception as e:
            self._warn_once("open_panel_splitter_moved", f"Failed to update open-panel button visibility: {e}")

    def _restore_right_panel(self):
        try:
            total = max(self.width(), 1)
            restore = max(250, int(total * 0.25))
            sizes = self.splitter.sizes()
            if len(sizes) >= 3:
                left = sizes[0] if sizes[0] > 0 else restore
                center = sizes[1] if sizes[1] > 0 else restore
                self.splitter.setSizes([left, center, restore])
            self.btn_open_panel.setVisible(False)
        except Exception as e:
            self._warn_once("open_panel_restore_right", f"Failed to restore right panel size: {e}")

    def _reposition_open_panel_button(self):
        try:
            if not hasattr(self, "btn_open_panel"):
                return
            btn = self.btn_open_panel
            margin = 4
            x = self.width() - btn.width() - margin
            y = max(0, (self.height() - btn.height()) // 2)
            btn.move(x, y)
            btn.raise_()
        except Exception as e:
            self._warn_once("open_panel_reposition", f"Failed to reposition open-panel button: {e}")

    def resizeEvent(self, event):
        try:
            self._reposition_open_panel_button()
        except Exception as e:
            self._warn_once("open_panel_resize_event", f"Resize handling failed while repositioning open-panel button: {e}")
        super().resizeEvent(event)

    # --- Command-pattern overrides for step CRUD (uses UndoStack) ---
    def open_conditional_action_wizard(self):
        try:
            dlg = ConditionalActionWizardDialog(self.steps, self)
            if dlg.exec_() != QDialog.Accepted:
                return

            new_steps = dlg.build_steps()
            if not new_steps:
                self.warn("Conditional wizard generated no steps.")
                return

            insert_index = len(self.steps)
            try:
                selected_row = int(self.list.currentRow())
            except Exception:
                selected_row = -1
            if 0 <= selected_row < len(self.steps):
                insert_index = selected_row + 1

            focus_index = insert_index + len(new_steps) - 1
            self._push_command(
                AddStepsCommand(self.steps, new_steps, index=insert_index),
                focus_index=focus_index,
            )
            self.info(f"Conditional wizard added {len(new_steps)} steps.")
        except Exception as e:
            self.err(f"Error in conditional wizard: {e}")

    def open_scenario_wizard(self):
        try:
            dlg = ScenarioWizardDialog(self)
            if dlg.exec_() != QDialog.Accepted:
                return
            result = dlg.get_result() or {}
            new_steps = result.get("steps") or []
            if not new_steps:
                self.warn("Scenario wizard generated no steps.")
                return

            insert_mode = str(result.get("insert_mode") or "end")
            insert_index = len(self.steps)
            if insert_mode == "after_selection":
                try:
                    selected_row = int(self.list.currentRow())
                except Exception:
                    selected_row = -1
                if 0 <= selected_row < len(self.steps):
                    insert_index = selected_row + 1

            focus_index = insert_index + len(new_steps) - 1
            self._push_command(
                AddStepsCommand(self.steps, new_steps, index=insert_index),
                focus_index=focus_index,
            )
            template_name = result.get("template_title") or result.get("template_id") or "wizard"
            self.info(f"Scenario wizard added {len(new_steps)} steps ({template_name}).")
        except Exception as e:
            self.err(f"Error in scenario wizard: {e}")

    def _resolve_visual_capture_image_dir(self) -> str:
        if self._current_macro_path:
            base_dir = os.path.dirname(os.path.abspath(self._current_macro_path))
        else:
            base_dir = os.getcwd()
        image_dir = os.path.join(base_dir, "images")
        os.makedirs(image_dir, exist_ok=True)
        return image_dir

    def _build_visual_capture_step(
        self,
        step_type: str,
        image_path: str,
        png_bytes: bytes,
        rect: QRect,
        virt_bounds: tuple[int, int, int, int],
    ) -> StepData:
        virt_left, virt_top, _virt_w, _virt_h = virt_bounds
        idx = len(self.steps) + 1
        if step_type == "wait_for_image":
            return StepData(
                id=str(uuid.uuid4())[:8],
                name=f"Visual Wait #{idx}",
                type="wait_for_image",
                png_bytes=png_bytes,
                anchor_image_path=image_path,
                image_path=image_path,
                timeout_ms=5000,
                poll_ms=200,
            )

        center_x = int(virt_left + int(rect.x()) + int(rect.width()) // 2)
        center_y = int(virt_top + int(rect.y()) + int(rect.height()) // 2)
        return StepData(
            id=str(uuid.uuid4())[:8],
            name=f"Visual Click #{idx}",
            type="image_click",
            png_bytes=png_bytes,
            anchor_image_path=image_path,
            image_path=image_path,
            click_x=center_x,
            click_y=center_y,
        )

    def _run_visual_capture(self, step_type: str):
        if step_type not in {"image_click", "wait_for_image"}:
            self.err(f"Unsupported capture step type: {step_type}")
            return
        if self.runner and self.runner.isRunning():
            self.warn("매크로 실행 중에는 스마트 캡처를 사용할 수 없습니다.")
            return
        if getattr(self, "_excel_mode_running", False):
            self.warn("Excel 모드 실행 중에는 스마트 캡처를 사용할 수 없습니다.")
            return

        rect, crop, virt_bounds = VisualImageCaptureOverlay.capture_from_screen(self)
        if crop is None or rect.isNull() or rect.width() < 3 or rect.height() < 3:
            self.info("스마트 캡처가 취소되었습니다.")
            return

        try:
            png_bytes = encode_png_bytes(crop)
            image_dir = self._resolve_visual_capture_image_dir()
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            image_path = os.path.abspath(os.path.join(image_dir, f"smart_capture_{stamp}.png"))
            with open(image_path, "wb") as fp:
                fp.write(png_bytes)

            step = self._build_visual_capture_step(step_type, image_path, png_bytes, rect, virt_bounds)

            insert_index = len(self.steps)
            try:
                current_row = int(self.list.currentRow())
                if 0 <= current_row < len(self.steps):
                    insert_index = current_row + 1
            except Exception:
                insert_index = len(self.steps)

            self._push_command(
                AddStepsCommand(self.steps, [step], index=insert_index),
                focus_index=insert_index,
            )
            self.info(
                f"스마트 캡처 스텝 추가: {step.type} "
                f"(x={int(rect.x())}, y={int(rect.y())}, w={int(rect.width())}, h={int(rect.height())})"
            )
        except Exception as e:
            self.err(f"스마트 캡처 처리 실패: {e}")

    def _open_smart_capture_menu(self):
        if self.runner and self.runner.isRunning():
            self.warn("매크로 실행 중에는 스마트 캡처를 사용할 수 없습니다.")
            return
        if getattr(self, "_excel_mode_running", False):
            self.warn("Excel 모드 실행 중에는 스마트 캡처를 사용할 수 없습니다.")
            return

        menu = QMenu(self)
        act_click = menu.addAction("이미지 클릭 스텝 생성")
        act_wait = menu.addAction("이미지 대기 스텝 생성")
        chosen = None
        if hasattr(self, "btnSmartCapture"):
            origin = self.btnSmartCapture.mapToGlobal(QPoint(0, self.btnSmartCapture.height()))
            chosen = menu.exec_(origin)
        else:
            chosen = menu.exec_(QCursor.pos())

        if chosen == act_click:
            self._run_visual_capture("image_click")
        elif chosen == act_wait:
            self._run_visual_capture("wait_for_image")

    def add_image_step(self):
        try:
            base_name = f"Image Step #{len(self.steps)+1}"
            step = StepData(id=str(uuid.uuid4())[:8], name=base_name, type="image_click")

            # 바로 ROI 캡처해서 스텝 생성 (기존 팝업 없이)
            rect, crop, _ = ROISelector.select_from_screen(self)
            if crop is None:
                return
            step.png_bytes = encode_png_bytes(crop)
            step._tpl_bgr = crop
            step._tpl_mask = None
            step._tpl_cache = {}
            self._push_command(AddStepCommand(self.steps, step), focus_index=len(self.steps))
        except Exception as e:
            self.err(f"Error adding image step: {e}")

    def add_not_image_step(self):
        try:
            base_name = f"Action Step #{len(self.steps)+1}"
            # Use a supported default type so the dialog does not open in legacy mode.
            step = StepData(id=str(uuid.uuid4())[:8], name=base_name, type='keyboard')
            dlg = NotImageDialog(step, self.steps, self)
            res = dlg.exec_()
            self.info(f"Action dialog result: {res}")
            if res != QDialog.Accepted:
                return
            new_step = None
            try:
                new_step = dlg.get_step_data()
            except Exception:
                new_step = None
            if new_step:
                self._push_command(AddStepCommand(self.steps, new_step), focus_index=len(self.steps))
        except Exception as e:
            self.err(f"Error in add_not_image_step: {e}")

    def add_branch_step(self):
        try:
            base_name = f"Branch Step #{len(self.steps)+1}"
            step = StepData(id=str(uuid.uuid4())[:8], name=base_name, type='image_branch')
            dlg = BranchStepDialog(step, self.steps, self)
            if dlg.exec_() == QDialog.Accepted:
                new_step = dlg.get_step_data()
                if new_step:
                    self._push_command(AddStepCommand(self.steps, new_step), focus_index=len(self.steps))
        except Exception as e:
            self.err(f"Error adding branch step: {e}")

    def add_comment_step(self):
        try:
            base_name = f"Note #{len(self.steps)+1}"
            step = StepData(id=str(uuid.uuid4())[:8], name=base_name, type='comment', comment="")
            self._push_command(AddStepCommand(self.steps, step), focus_index=len(self.steps))
        except Exception as e:
            self.err(f"Error adding comment: {e}")

    def edit_step_at(self, idx):
        if idx < 0 or idx >= len(self.steps):
            return
        step = self.steps[idx]
        original = copy.deepcopy(step)
        dlg = None
        res = None
        new_step = None

        try:
            if step.type in {'image_click', 'wait_for_image'}:
                dlg = ImageStepDialog(step, self)
                res = dlg.exec_()
                if res == QDialog.Accepted:
                    new_step = dlg.get_step_data()
            elif step.type == 'image_branch':
                dlg = BranchStepDialog(step, self.steps, self)
                res = dlg.exec_()
                if res == QDialog.Accepted:
                    new_step = dlg.get_step_data()
            elif step.type == 'target':
                dlg = TargetDialog(step, self)
                res = dlg.exec_()
                if res == QDialog.Accepted:
                    new_step = dlg.get_step_data()
            else:
                dlg = NotImageDialog(step, self.steps, self)
                res = dlg.exec_()
                self.info(f"Action dialog result: {res}")
                if res != QDialog.Accepted:
                    return
                try:
                    new_step = dlg.get_step_data()
                except Exception:
                    new_step = None

            if new_step:
                self._push_command(EditStepCommand(self.steps, idx, original, new_step), focus_index=idx)
        except Exception as e:
            self.err(f"Error editing step: {e}")

    def delete_step_at(self, idx):
        if idx < 0 or idx >= len(self.steps):
            return
        try:
            self._push_command(RemoveStepCommand(self.steps, idx), focus_index=min(idx, len(self.steps)-1))
        except Exception as e:
            self.err(f"Error deleting step: {e}")

    def delete_steps_at(self, indices):
        if not indices:
            return
        try:
            for i in sorted(indices, reverse=True):
                if 0 <= i < len(self.steps):
                    self._push_command(RemoveStepCommand(self.steps, i), focus_index=min(i, len(self.steps)-1))
        except Exception as e:
            self.err(f"Error deleting steps: {e}")

    def move_step_up(self, idx):
        if idx <= 0 or idx >= len(self.steps):
            return
        try:
            self._push_command(MoveStepCommand(self.steps, idx, idx-1), focus_index=idx-1)
        except Exception as e:
            self.err(f"Error moving step up: {e}")

    def move_step_down(self, idx):
        if idx < 0 or idx >= len(self.steps)-1:
            return
        try:
            self._push_command(MoveStepCommand(self.steps, idx, idx+1), focus_index=idx+1)
        except Exception as e:
            self.err(f"Error moving step down: {e}")

    def duplicate_step_at(self, idx):
        if idx < 0 or idx >= len(self.steps):
            return
        try:
            clone = copy.deepcopy(self.steps[idx])
            clone.id = str(uuid.uuid4())[:8]
            clone.name = f"{clone.name} (Copy)"
            self._push_command(AddStepCommand(self.steps, clone), focus_index=len(self.steps))
        except Exception as e:
            self.err(f"Error duplicating step: {e}")

    def duplicate_steps_at(self, indices):
        if not indices:
            return
        try:
            for i in indices:
                if 0 <= i < len(self.steps):
                    clone = copy.deepcopy(self.steps[i])
                    clone.id = str(uuid.uuid4())[:8]
                    clone.name = f"{clone.name} (Copy)"
                    self._push_command(AddStepCommand(self.steps, clone), focus_index=len(self.steps))
        except Exception as e:
            self.err(f"Error duplicating steps: {e}")

    def _update_hotkey_labels(self):
        if hasattr(self, "btnAddImg"):
            self.btnAddImg.setText(self._format_hotkey_hint("이미지+", self._hk_add_img))
            self.btnAddImg.setToolTip(f"Shortcut: {hk_pretty(self._hk_add_img)}" if self._hk_add_img else "")
        if hasattr(self, "btnAddAction"):
            self.btnAddAction.setText(self._format_hotkey_hint("일반동작+", self._hk_add_notimg))
            self.btnAddAction.setToolTip(f"Shortcut: {hk_pretty(self._hk_add_notimg)}" if self._hk_add_notimg else "")
        if hasattr(self, "btnStop"):
            self.btnStop.setText(self._format_hotkey_hint("정지", self._hk_stop))
        if hasattr(self, "btnToolbarRun"):
            self.btnToolbarRun.setText(self._format_hotkey_hint("Run", self._hk_run))
        if hasattr(self, "btnToolbarStop"):
            self.btnToolbarStop.setText(self._format_hotkey_hint("Stop", self._hk_stop))

        self.act_run.setText(self._format_hotkey_hint("Run", self._hk_run))
        self.act_stop.setText(self._format_hotkey_hint("Stop", self._hk_stop))
        self.act_add_img.setText(self._format_hotkey_hint("Add Image", self._hk_add_img))
        self.act_add_act.setText(self._format_hotkey_hint("Add Action", self._hk_add_notimg))
        self._set_macro_paused_ui(getattr(self, "_macro_paused_ui", False))

        # 녹화 상태에 맞춰 버튼/액션 텍스트 갱신
        self._set_record_labels_dynamic()

    def _set_record_labels_dynamic(self):
        recording = False
        try:
            recording = bool(getattr(self.recorder, "_active", False))
        except Exception:
            recording = False
        try:
            recording = recording or bool(self.act_record.isChecked())
        except Exception as e:
            self._warn_once("record_dynamic_action_checked", f"Failed to read action recording state: {e}")
        try:
            recording = recording or bool(self.btnRecord.isChecked())
        except Exception as e:
            self._warn_once("record_dynamic_button_checked", f"Failed to read button recording state: {e}")

        shortcut_text = ""
        try:
            sc = self.act_record.shortcut() if getattr(self, "act_record", None) else None
            shortcut_text = sc.toString() if sc else ""
        except Exception:
            shortcut_text = ""
        if not shortcut_text and getattr(self, "_hk_record", None):
            shortcut_text = self._hk_record.upper()

        base = "녹화 정지" if recording else "녹화"
        label = f"{base} ({shortcut_text})" if shortcut_text else base
        for obj in (getattr(self, "act_record", None), getattr(self, "btnRecord", None)):
            try:
                if obj:
                    obj.setText(label)
            except Exception as e:
                self._warn_once("record_dynamic_set_text", f"Failed to apply dynamic recording label: {e}")

    def toggle_record(self, checked):
        if checked:
            if self.runner and self.runner.isRunning():
                self.warn("Cannot record while running.")
                try:
                    self.act_record.setChecked(False)
                    self.btnRecord.setChecked(False)
                except Exception as e:
                    self._warn_once("toggle_record_reset_checked", f"Failed to reset recording toggle state: {e}")
                return
            self.info("Start Recording...")
            if getattr(self, "chkAutoMin", None) and self.chkAutoMin.isChecked():
                self.showMinimized()
                self._was_minimized = True
            self._start_record()
        else:
            self.info("Stop Recording...")
            self._stop_record()
            if getattr(self, "_was_minimized", False):
                self.showNormal()
                self.activateWindow()
                self._was_minimized = False
        # 상태에 맞게 텍스트 갱신
        self._set_record_labels_dynamic()
        # 다른 라벨들도 최신 상태로 유지
        try:
            self._update_hotkey_labels()
        except Exception as e:
            self._warn_once("toggle_record_update_hotkey_labels", f"Failed to refresh hotkey labels after record toggle: {e}")

    def _get_target_window_title(self) -> str:
        try:
            return self.edTargetTitle.text().strip()
        except Exception:
            return ""

    def _find_target_window(self):
        title = self._get_target_window_title()
        if not title:
            self.warn("Target window title is empty.")
            return
        self._save_general_settings()
        try:
            hwnd = self.window_manager.find_window(title)
            if hwnd:
                self.target_hwnd = hwnd
                self.window_manager.activate_window(hwnd)
                self.info(f"Found and activated: {title} (HWND {hwnd})")
            else:
                self.target_hwnd = None
                self.warn(f"Window not found: {title}")
        except Exception as e:
            self.target_hwnd = None
            self.warn(f"Window search failed: {e}")

    def _fix_target_window(self):
        if not self.target_hwnd:
            self.warn("No window handle stored. Click Find first.")
            return
        try:
            self.window_manager.activate_window(self.target_hwnd)
            self.info(f"Fixed/Refreshed HWND {self.target_hwnd}")
        except Exception as e:
            self.warn(f"Fix failed: {e}")

    def _open_window_selector(self):
        try:
            dlg = WindowSelectorDialog(self)
        except Exception as e:
            self.warn(f"Window selector unavailable: {e}")
            return
        if dlg.exec_() == QDialog.Accepted and dlg.selected_title:
            self.edTargetTitle.setText(dlg.selected_title)
            self._save_general_settings()

def main():
    app = QApplication(sys.argv)
    sys.excepthook = _excepthook
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

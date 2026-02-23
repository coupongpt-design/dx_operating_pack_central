import os
import uuid
import cv2
import numpy as np
import mss
import pyautogui
from dataclasses import asdict
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QSpinBox, 
    QDoubleSpinBox, QCheckBox, QComboBox, QPushButton, QLabel, QWidget, 
    QTabWidget, QGroupBox, QDialogButtonBox, QFileDialog, QMessageBox, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QGridLayout, QApplication, QShortcut,
    QRadioButton, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, QEventLoop, QSettings, QSize, QEvent
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence

from ..core.models import StepData
from ..core.vision import ImageProcessor
from ..core.commands import UndoStack, AddStepCommand, RemoveStepCommand
from ..utils.common import (
    cvimg_to_qpixmap, encode_png_bytes, decode_png_bytes, decode_png_with_mask,
    hk_normalize, hk_pretty, warn, err
)
from ..utils.matcher import Matcher
from .selectors import ROISelector, safe_select_point

SETTINGS_ORG = "ImageMacro"
SETTINGS_APP = "MVP"
LEGACY_SETTINGS_ORG = "AutoCording"
LEGACY_SETTINGS_APP = "MacroTool"

class BaseDialog(QDialog):
    def _warn_once(self, key: str, msg: str):
        warned = getattr(self, "_warned_once_keys", None)
        if warned is None:
            warned = set()
            self._warned_once_keys = warned
        if key in warned:
            return
        warned.add(key)
        warn(msg)

    def _robust_restore_self(self):
        """
        좌표 픽킹 후 다이얼로그가 숨김/최소화/비활성 상태로 남았을 때,
        확실하게 화면 전면/활성 상태로 복구시키는 루틴.
        """
        try:
            # 1) 최소화 풀기 + 보이기
            st = self.windowState()
            if st & Qt.WindowMinimized:
                self.setWindowState(st & ~Qt.WindowMinimized)
            if not self.isVisible():
                try:
                    self.showNormal()
                except Exception:
                    self.show()
            # 2) 불투명도/활성화 복구
            try:
                if self.windowOpacity() < 0.99:
                    self.setWindowOpacity(1.0)
            except Exception as e:
                self._warn_once("robust_restore_opacity", f"Dialog opacity restore skipped: {e}")
            try:
                self.setEnabled(True)
            except Exception as e:
                self._warn_once("robust_restore_enabled", f"Dialog enabled-state restore skipped: {e}")
            # 3) 최전면으로 띄우기
            self.show()
            self.raise_()
            self.activateWindow()
            try:
                QApplication.setActiveWindow(self)
            except Exception as e:
                self._warn_once("robust_restore_active_window", f"Active window request failed: {e}")
            # 4) 모달/포커스 다시 띄우기
            try:
                self.setWindowModality(Qt.WindowModal)
            except Exception as e:
                self._warn_once("robust_restore_modality", f"Window modality restore skipped: {e}")
            # 5) 이벤트 루프 처리 및 UI 반영
            try:
                QApplication.processEvents(QEventLoop.AllEvents, 50)
            except Exception as e:
                self._warn_once("robust_restore_process_events", f"Event loop flush skipped: {e}")
            # 6) 타이머를 이용해 한 번 더 확실하게 띄우기
            try:
                QTimer.singleShot(0, self.raise_)
                QTimer.singleShot(0, self.activateWindow)
            except Exception as e:
                self._warn_once("robust_restore_singleshot", f"Delayed raise/activate failed: {e}")
        except Exception as e:
            self._warn_once("robust_restore_root", f"Dialog robust restore routine failed: {e}")

class ImageStepDialog(BaseDialog):
    def __init__(self, step: StepData, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Step")
        self.resize(650, 700)
        self._step = step

        def _ival(val, default=0, min_value=None, max_value=None):
            try:
                v = int(val)
            except (TypeError, ValueError):
                v = default
            if min_value is not None:
                v = max(min_value, v)
            if max_value is not None:
                v = min(max_value, v)
            return v

        def _fval(val, default=0.0, min_value=None, max_value=None):
            try:
                v = float(val)
            except (TypeError, ValueError):
                v = default
            if min_value is not None:
                v = max(min_value, v)
            if max_value is not None:
                v = min(max_value, v)
            return v

        mainLayout = QVBoxLayout(self)
        tabWidget = QTabWidget()
        mainLayout.addWidget(tabWidget)

        # --- 탭 1: 기본 설정 ---
        basicTab = QWidget()
        formLayout1 = QFormLayout(basicTab)
        
        self.edName = QLineEdit(step.name)
        formLayout1.addRow("Step Name", self.edName)
        
        self.lblPreview = QLabel("No Image")
        self.lblPreview.setAlignment(Qt.AlignCenter)
        self.lblPreview.setFixedSize(200, 150)
        self.lblPreview.setStyleSheet("border: 1px solid gray;")
        if step.png_bytes:
            pm = cvimg_to_qpixmap(decode_png_bytes(step.png_bytes))
            if pm: self.lblPreview.setPixmap(pm.scaled(200, 150, Qt.KeepAspectRatio))
        formLayout1.addRow("Template", self.lblPreview)
        
        btnLayout = QHBoxLayout()
        self.btnCapture = QPushButton("Capture Template")
        self.btnLoad = QPushButton("Load Image")
        btnLayout.addWidget(self.btnCapture)
        btnLayout.addWidget(self.btnLoad)
        formLayout1.addRow("", btnLayout)
        
        self.cbAction = QComboBox()
        self.cbAction.addItems(["Click", "Double Click", "Move Only", "None (Just Find)"])
        action = getattr(step, "image_action", None) or getattr(step, "click_button", None) or getattr(step, "click_btn", "click")
        if getattr(step, "click_double", False):
            action = "double"
        action_map = {"click": 0, "double": 1, "move": 2, "move_only": 2, "none": 3}
        if action in action_map:
            self.cbAction.setCurrentIndex(action_map[action])
        formLayout1.addRow("Action", self.cbAction)
        self.spJitter = QSpinBox()
        self.spJitter.setRange(0, 50)
        self.spJitter.setValue(_ival(getattr(step, "jitter", 2), 2))
        formLayout1.addRow("Jitter (px)", self.spJitter)
        self.cbAnchor = QComboBox()
        self.cbAnchor.addItems(["center", "top-left", "top-right", "bottom-left", "bottom-right"])
        idx_anchor = self.cbAnchor.findText(getattr(step, "click_anchor", "center"))
        if idx_anchor >= 0:
            self.cbAnchor.setCurrentIndex(idx_anchor)
        formLayout1.addRow("Click Anchor", self.cbAnchor)

        self.chkLoopUntilHide = QCheckBox("Loop until hidden")
        self.chkLoopUntilHide.setChecked(bool(getattr(step, "loop_until_hide", False)))
        formLayout1.addRow("", self.chkLoopUntilHide)
        
        self.spTimeout = QSpinBox()
        self.spTimeout.setRange(0, 999999)
        self.spTimeout.setValue(_ival(getattr(step, "timeout_ms", 0), 0))
        self.spTimeout.setSuffix(" ms")
        formLayout1.addRow("Timeout", self.spTimeout)
        
        self.spThreshold = QDoubleSpinBox()
        self.spThreshold.setRange(0.1, 1.0)
        self.spThreshold.setSingleStep(0.01)
        self.spThreshold.setValue(_fval(getattr(step, "threshold", 0.85), 0.85))
        formLayout1.addRow("Confidence Threshold", self.spThreshold)
        self.spMinConf = QDoubleSpinBox()
        self.spMinConf.setRange(0.1, 1.0)
        self.spMinConf.setSingleStep(0.01)
        self.spMinConf.setValue(_fval(getattr(step, "min_confidence", getattr(step, "threshold", 0.85) or 0.85), 0.85))
        formLayout1.addRow("Min Confidence", self.spMinConf)

        tabWidget.addTab(basicTab, "Basic")

        # --- 탭 2: 고급 설정 ---
        advTab = QWidget()
        formLayout2 = QFormLayout(advTab)

        # Offsets / timing
        self.spOffsetX = QSpinBox(); self.spOffsetX.setRange(-5000, 5000); self.spOffsetX.setValue(_ival(getattr(step, "click_offset_x", 0), 0))
        self.spOffsetY = QSpinBox(); self.spOffsetY.setRange(-5000, 5000); self.spOffsetY.setValue(_ival(getattr(step, "click_offset_y", 0), 0))
        offRow = QHBoxLayout()
        offRow.addWidget(QLabel("Offset X")); offRow.addWidget(self.spOffsetX)
        offRow.addWidget(QLabel("Offset Y")); offRow.addWidget(self.spOffsetY)
        formLayout2.addRow(offRow)

        self.cbClickBtn = QComboBox()
        self.cbClickBtn.addItems(["left", "right", "middle", "double"])
        idx = self.cbClickBtn.findText(step.click_btn)
        if idx >= 0: self.cbClickBtn.setCurrentIndex(idx)
        formLayout2.addRow("Mouse Button", self.cbClickBtn)

        self.spPreDelay = QSpinBox()
        self.spPreDelay.setRange(0, 999999)
        self.spPreDelay.setSingleStep(100)
        self.spPreDelay.setValue(_ival(getattr(step, "pre_delay_ms", 0), 0))
        self.spPreDelay.setSuffix(" ms")
        formLayout2.addRow("Pre-delay", self.spPreDelay)
        self.spPreMoveSleep = QSpinBox(); self.spPreMoveSleep.setRange(0, 600000); self.spPreMoveSleep.setValue(_ival(getattr(step, "pre_move_sleep_ms", 30), 30)); self.spPreMoveSleep.setSuffix(" ms")
        self.spPressDur = QSpinBox(); self.spPressDur.setRange(0, 600000); self.spPressDur.setValue(_ival(getattr(step, "press_duration_ms", 70), 70)); self.spPressDur.setSuffix(" ms")
        self.spPostSleep = QSpinBox(); self.spPostSleep.setRange(0, 600000); self.spPostSleep.setValue(_ival(getattr(step, "post_click_sleep_ms", 0), 0)); self.spPostSleep.setSuffix(" ms")
        formLayout2.addRow("Pre-move Sleep", self.spPreMoveSleep)
        formLayout2.addRow("Hold Duration", self.spPressDur)
        formLayout2.addRow("Post-click Sleep", self.spPostSleep)
        self.spTplCache = QSpinBox(); self.spTplCache.setRange(0, 10000); self.spTplCache.setValue(_ival(getattr(step, "tpl_cache_limit", 128), 128))
        formLayout2.addRow("Template Cache Limit", self.spTplCache)

        tabWidget.addTab(advTab, "Advanced")

        # --- 탭 3: 매칭 설정 ---
        matchingTab = QWidget()
        formLayout3 = QFormLayout(matchingTab)

        self.cbQuality = QComboBox()
        self.cbQuality.addItem("Performance", "performance")
        self.cbQuality.addItem("Normal", "normal")
        self.cbQuality.addItem("High Accuracy", "high")
        self.cbQuality.addItem("Reset", "reset")
        quality = str(getattr(step, "match_quality", "normal") or "normal").lower()
        idx_quality = self.cbQuality.findData(quality)
        if idx_quality < 0:
            idx_quality = self.cbQuality.findData("normal")
        if idx_quality >= 0:
            self.cbQuality.setCurrentIndex(idx_quality)
        self._initial_quality = self.cbQuality.currentData() or "normal"
        self._last_quality_selection = self._initial_quality

        self.chkGray = QCheckBox("Use grayscale")
        self.chkGray.setChecked(step.pre_gray)
        self.spBlur = QSpinBox()
        self.spBlur.setRange(0, 20)
        self.spBlur.setValue(_ival(getattr(step, "pre_blur_ksize", 0), 0))
        self.chkClahe = QCheckBox("CLAHE")
        self.chkClahe.setChecked(bool(getattr(step, "pre_clahe", False)))
        self.chkEdge = QCheckBox("Edge Enhance")
        self.chkEdge.setChecked(bool(getattr(step, "pre_edge", False)))
        self.chkSharpen = QCheckBox("Sharpen")
        self.chkSharpen.setChecked(bool(getattr(step, "pre_sharpen", False)))
        self.chkMatchColor = QCheckBox("Color Match")
        self.chkMatchColor.setChecked(bool(getattr(step, "match_color", False)))
        self.spColorTol = QSpinBox(); self.spColorTol.setRange(0, 255); self.spColorTol.setValue(_ival(getattr(step, "color_match_tolerance", 10), 10))
        self.chkAlphaMask = QCheckBox("Use PNG Alpha Mask")
        self.chkAlphaMask.setChecked(bool(getattr(step, "alpha_mask_enable", True)))
        self.chkAutoFgMask = QCheckBox("Auto Foreground Mask (No Alpha)")
        self.chkAutoFgMask.setChecked(bool(getattr(step, "auto_fg_mask_enable", False)))
        self.cbAutoFgPreset = QComboBox()
        self.cbAutoFgPreset.addItem("Custom", "custom")
        self.cbAutoFgPreset.addItem("Stable", "stable")
        self.cbAutoFgPreset.addItem("Accurate", "accurate")
        self.cbAutoFgPreset.addItem("Aggressive", "aggressive")
        self.cbAutoFgPreset.setToolTip(
            "Stable: safer on noisy backgrounds\n"
            "Accurate: balanced default\n"
            "Aggressive: strongest foreground separation"
        )
        self.btnSuggestAutoFg = QPushButton("Suggest")
        self.btnSuggestAutoFg.setToolTip("Suggest preset from current template image")
        self.btnSuggestAutoFg.setMaximumWidth(96)
        self.lblAutoFgPresetHint = QLabel("")
        self.lblAutoFgPresetHint.setWordWrap(True)
        self.lblAutoFgPresetHint.setStyleSheet("color: #888; font-size: 11px;")
        self.lblAutoFgSuggestInfo = QLabel("")
        self.lblAutoFgSuggestInfo.setWordWrap(True)
        self.lblAutoFgSuggestInfo.setStyleSheet("color: #5aa; font-size: 11px;")
        self.spAutoFgPct = QDoubleSpinBox(); self.spAutoFgPct.setRange(50.0, 95.0); self.spAutoFgPct.setSingleStep(1.0); self.spAutoFgPct.setValue(_fval(getattr(step, "auto_fg_mask_bg_percentile", 70.0), 70.0, 50.0, 95.0))
        self.spAutoFgScale = QDoubleSpinBox(); self.spAutoFgScale.setRange(0.1, 2.0); self.spAutoFgScale.setSingleStep(0.05); self.spAutoFgScale.setValue(_fval(getattr(step, "auto_fg_mask_dynamic_scale", 0.6), 0.6, 0.1, 2.0))
        self.spAutoFgMinDist = QDoubleSpinBox(); self.spAutoFgMinDist.setRange(1.0, 255.0); self.spAutoFgMinDist.setSingleStep(1.0); self.spAutoFgMinDist.setValue(_fval(getattr(step, "auto_fg_mask_min_distance", 12.0), 12.0, 1.0, 255.0))
        self.spAutoFgStdLow = QDoubleSpinBox(); self.spAutoFgStdLow.setRange(0.0, 128.0); self.spAutoFgStdLow.setSingleStep(0.5); self.spAutoFgStdLow.setValue(_fval(getattr(step, "auto_fg_suggest_std_low", 18.0), 18.0, 0.0, 128.0))
        self.spAutoFgStdHigh = QDoubleSpinBox(); self.spAutoFgStdHigh.setRange(0.0, 128.0); self.spAutoFgStdHigh.setSingleStep(0.5); self.spAutoFgStdHigh.setValue(_fval(getattr(step, "auto_fg_suggest_std_high", 42.0), 42.0, 0.0, 128.0))
        self.spAutoFgEdgeLow = QDoubleSpinBox(); self.spAutoFgEdgeLow.setRange(0.0, 1.0); self.spAutoFgEdgeLow.setDecimals(3); self.spAutoFgEdgeLow.setSingleStep(0.005); self.spAutoFgEdgeLow.setValue(_fval(getattr(step, "auto_fg_suggest_edge_low", 0.07), 0.07, 0.0, 1.0))
        self.spAutoFgEdgeHigh = QDoubleSpinBox(); self.spAutoFgEdgeHigh.setRange(0.0, 1.0); self.spAutoFgEdgeHigh.setDecimals(3); self.spAutoFgEdgeHigh.setSingleStep(0.005); self.spAutoFgEdgeHigh.setValue(_fval(getattr(step, "auto_fg_suggest_edge_high", 0.20), 0.20, 0.0, 1.0))
        self._auto_fg_preset_initing = True
        self._auto_fg_preset_applying = False
        preset_key = self._detect_auto_fg_preset()
        idx_preset = self.cbAutoFgPreset.findData(preset_key)
        if idx_preset < 0:
            idx_preset = self.cbAutoFgPreset.findData("custom")
        if idx_preset >= 0:
            self.cbAutoFgPreset.setCurrentIndex(idx_preset)
        self._auto_fg_preset_initing = False
        self.chkColorBgRobust = QCheckBox("High Quality Color Robust Fallback")
        self.chkColorBgRobust.setChecked(bool(getattr(step, "hq_color_bg_robust", False)))
        self.spPoll = QSpinBox(); self.spPoll.setRange(1, 10000); self.spPoll.setValue(_ival(getattr(step, "poll_ms", 100), 100)); self.spPoll.setSuffix(" ms")
        self.spTopK = QSpinBox(); self.spTopK.setRange(1, 20); self.spTopK.setValue(_ival(getattr(step, "top_k", 1), 1))
        self.chkFindAll = QCheckBox("Find All Targets")
        self.chkFindAll.setChecked(bool(getattr(step, "find_all_targets", False)))
        self.chkHoldUntil = QCheckBox("Hold Until Next Image")
        self.chkHoldUntil.setChecked(bool(getattr(step, "hold_until_next", False)))
        self.spHoldTimeout = QSpinBox(); self.spHoldTimeout.setRange(0, 600000); self.spHoldTimeout.setValue(_ival(getattr(step, "hold_timeout_ms", 5000), 5000)); self.spHoldTimeout.setSuffix(" ms")
        self.spHoldReclick = QSpinBox(); self.spHoldReclick.setRange(0, 600000); self.spHoldReclick.setValue(_ival(getattr(step, "hold_reclick_interval_ms", 500), 500)); self.spHoldReclick.setSuffix(" ms")
        self.chkHoldReacquire = QCheckBox("Reacquire Each Time")
        self.chkHoldReacquire.setChecked(bool(getattr(step, "hold_reacquire_each_time", False)))
        self.spHoldRelease = QSpinBox(); self.spHoldRelease.setRange(1, 1000); self.spHoldRelease.setValue(_ival(getattr(step, "hold_release_consecutive", 1), 1)); self.spHoldRelease.setSuffix(" ms")
        self.spBudget = QSpinBox(); self.spBudget.setRange(0, 600000); self.spBudget.setValue(_ival(getattr(step, "budget_ms", 0), 0)); self.spBudget.setSuffix(" ms")
        formLayout3.addRow("Quality Preset", self.cbQuality)
        formLayout3.addRow(self.chkGray)
        formLayout3.addRow("Blur Kernel Size", self.spBlur)
        formLayout3.addRow(self.chkClahe)
        formLayout3.addRow(self.chkEdge)
        formLayout3.addRow(self.chkSharpen)
        formLayout3.addRow(self.chkMatchColor)
        formLayout3.addRow("Color Tolerance", self.spColorTol)
        formLayout3.addRow(self.chkAlphaMask)
        formLayout3.addRow(self.chkAutoFgMask)
        autoFgPresetRow = QWidget()
        autoFgPresetLayout = QHBoxLayout(autoFgPresetRow)
        autoFgPresetLayout.setContentsMargins(0, 0, 0, 0)
        autoFgPresetLayout.addWidget(self.cbAutoFgPreset)
        autoFgPresetLayout.addWidget(self.btnSuggestAutoFg)
        formLayout3.addRow("Auto FG Preset", autoFgPresetRow)
        formLayout3.addRow("", self.lblAutoFgPresetHint)
        formLayout3.addRow("", self.lblAutoFgSuggestInfo)
        formLayout3.addRow("Auto FG BG Percentile", self.spAutoFgPct)
        formLayout3.addRow("Auto FG Dynamic Scale", self.spAutoFgScale)
        formLayout3.addRow("Auto FG Min Distance", self.spAutoFgMinDist)
        formLayout3.addRow("Suggest Std Low", self.spAutoFgStdLow)
        formLayout3.addRow("Suggest Std High", self.spAutoFgStdHigh)
        formLayout3.addRow("Suggest Edge Low", self.spAutoFgEdgeLow)
        formLayout3.addRow("Suggest Edge High", self.spAutoFgEdgeHigh)
        formLayout3.addRow(self.chkColorBgRobust)
        formLayout3.addRow("Poll Interval", self.spPoll)
        formLayout3.addRow("Top K", self.spTopK)
        formLayout3.addRow(self.chkFindAll)
        formLayout3.addRow(self.chkHoldUntil)
        formLayout3.addRow("Hold Timeout", self.spHoldTimeout)
        formLayout3.addRow("Hold Reclick Interval", self.spHoldReclick)
        formLayout3.addRow(self.chkHoldReacquire)
        formLayout3.addRow("Hold Release Consecutive", self.spHoldRelease)
        formLayout3.addRow("Budget (ms)", self.spBudget)

        # ROI
        self.chkSearchRoi = QCheckBox("Limit Search ROI")
        self.chkSearchRoi.setChecked(bool(getattr(step, "search_roi_enabled", False)))
        self.spRoiX = QSpinBox(); self.spRoiX.setRange(-99999, 99999); self.spRoiX.setValue(_ival(getattr(step, "search_roi_left", 0), 0))
        self.spRoiY = QSpinBox(); self.spRoiY.setRange(-99999, 99999); self.spRoiY.setValue(_ival(getattr(step, "search_roi_top", 0), 0))
        self.spRoiW = QSpinBox(); self.spRoiW.setRange(0, 99999); self.spRoiW.setValue(_ival(getattr(step, "search_roi_width", 0), 0))
        self.spRoiH = QSpinBox(); self.spRoiH.setRange(0, 99999); self.spRoiH.setValue(_ival(getattr(step, "search_roi_height", 0), 0))
        formLayout3.addRow(self.chkSearchRoi)
        formLayout3.addRow("ROI Left", self.spRoiX)
        formLayout3.addRow("ROI Top", self.spRoiY)
        formLayout3.addRow("ROI Width", self.spRoiW)
        formLayout3.addRow("ROI Height", self.spRoiH)

        # Multi-scale / rotation
        self._max_scales_default = _ival(getattr(step, "max_scales", 0), 0)
        self._max_rotations_default = _ival(getattr(step, "max_rotations", 0), 0)
        self.chkEnableScale = QCheckBox("Enable Multi-Scale")
        self.chkEnableScale.setChecked(self._max_scales_default > 0)
        self.chkEnableRot = QCheckBox("Enable Rotation")
        self.chkEnableRot.setChecked(self._max_rotations_default > 0)
        self.spMsMin = QDoubleSpinBox(); self.spMsMin.setRange(0.1, 5.0); self.spMsMin.setSingleStep(0.01); self.spMsMin.setValue(_fval(getattr(step, "ms_min_scale", 0.9), 0.9))
        self.spMsMax = QDoubleSpinBox(); self.spMsMax.setRange(0.1, 5.0); self.spMsMax.setSingleStep(0.01); self.spMsMax.setValue(_fval(getattr(step, "ms_max_scale", 1.1), 1.1))
        self.spMsStep = QDoubleSpinBox(); self.spMsStep.setRange(0.01, 2.0); self.spMsStep.setSingleStep(0.01); self.spMsStep.setValue(_fval(getattr(step, "ms_step", 1.05), 1.05))
        self.spRotMin = QDoubleSpinBox(); self.spRotMin.setRange(-180, 180); self.spRotMin.setSingleStep(1.0); self.spRotMin.setValue(_fval(getattr(step, "rot_min_deg", -10.0), -10.0))
        self.spRotMax = QDoubleSpinBox(); self.spRotMax.setRange(-180, 180); self.spRotMax.setSingleStep(1.0); self.spRotMax.setValue(_fval(getattr(step, "rot_max_deg", 10.0), 10.0))
        self.spRotStep = QDoubleSpinBox(); self.spRotStep.setRange(0.1, 90.0); self.spRotStep.setSingleStep(0.1); self.spRotStep.setValue(_fval(getattr(step, "rot_step_deg", 5.0), 5.0))
        formLayout3.addRow(self.chkEnableScale)
        formLayout3.addRow(self.chkEnableRot)
        formLayout3.addRow("MS Min Scale", self.spMsMin)
        formLayout3.addRow("MS Max Scale", self.spMsMax)
        formLayout3.addRow("MS Step", self.spMsStep)
        formLayout3.addRow("Rot Min", self.spRotMin)
        formLayout3.addRow("Rot Max", self.spRotMax)
        formLayout3.addRow("Rot Step", self.spRotStep)

        self.chkFeatFallback = QCheckBox("Enable Feature Fallback (ORB)")
        self.chkFeatFallback.setChecked(bool(getattr(step, "feat_fallback_enable", False)))
        self._preset_reset_state = (
            self.chkEnableScale.isChecked(),
            self.chkEnableRot.isChecked(),
            self.chkFeatFallback.isChecked(),
        )
        self._last_custom_state = self._preset_reset_state
        self.spFeatN = QSpinBox(); self.spFeatN.setRange(100, 10000); self.spFeatN.setValue(_ival(getattr(step, "feat_nfeatures", 500), 500))
        self.spFeatRatio = QDoubleSpinBox(); self.spFeatRatio.setRange(0.1, 0.99); self.spFeatRatio.setSingleStep(0.01); self.spFeatRatio.setValue(_fval(getattr(step, "feat_match_ratio", 0.75), 0.75))
        self.spFeatRansac = QDoubleSpinBox(); self.spFeatRansac.setRange(0.1, 20.0); self.spFeatRansac.setSingleStep(0.1); self.spFeatRansac.setValue(_fval(getattr(step, "feat_ransac_reproj_thresh", 3.0), 3.0))
        formLayout3.addRow(self.chkFeatFallback)
        formLayout3.addRow("ORB NFeatures", self.spFeatN)
        formLayout3.addRow("ORB Match Ratio", self.spFeatRatio)
        formLayout3.addRow("ORB RANSAC Thresh", self.spFeatRansac)
        
        self.btnTest = QPushButton("Test Match on Screen")
        self.lblTest = QLabel("Result: -")
        formLayout3.addRow(self.btnTest, self.lblTest)
        
        tabWidget.addTab(matchingTab, "Matching")

        # Buttons
        btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btnBox.accepted.connect(self.accept)
        btnBox.rejected.connect(self.reject)
        mainLayout.addWidget(btnBox)

        self._quality_initing = True
        self._preset_applying = False
        self.btnCapture.clicked.connect(self._on_capture)
        self.btnLoad.clicked.connect(self._on_load)
        self.btnTest.clicked.connect(self._on_test_match)
        self.cbQuality.currentIndexChanged.connect(self._on_quality_changed)
        self.chkEnableScale.stateChanged.connect(self._on_matching_toggle_changed)
        self.chkEnableRot.stateChanged.connect(self._on_matching_toggle_changed)
        self.chkFeatFallback.stateChanged.connect(self._on_matching_toggle_changed)
        self.cbAutoFgPreset.currentIndexChanged.connect(self._on_auto_fg_preset_changed)
        self.spAutoFgPct.valueChanged.connect(self._on_auto_fg_tune_changed)
        self.spAutoFgScale.valueChanged.connect(self._on_auto_fg_tune_changed)
        self.spAutoFgMinDist.valueChanged.connect(self._on_auto_fg_tune_changed)
        self.spAutoFgStdLow.valueChanged.connect(self._on_auto_fg_suggest_threshold_changed)
        self.spAutoFgStdHigh.valueChanged.connect(self._on_auto_fg_suggest_threshold_changed)
        self.spAutoFgEdgeLow.valueChanged.connect(self._on_auto_fg_suggest_threshold_changed)
        self.spAutoFgEdgeHigh.valueChanged.connect(self._on_auto_fg_suggest_threshold_changed)
        self.btnSuggestAutoFg.clicked.connect(self._on_suggest_auto_fg_preset)
        self._update_auto_fg_preset_hint()
        self._quality_initing = False

    def _normalize_quality(self, quality: str) -> str:
        q = str(quality or "").lower()
        return q.replace(" ", "_").replace("-", "_")

    def _apply_quality_preset(self, quality: str) -> None:
        q = self._normalize_quality(quality)
        if q in ("reset",):
            self._preset_applying = True
            try:
                scale_on, rot_on, feat_on = self._preset_reset_state
            except Exception:
                scale_on, rot_on, feat_on = False, False, False
            self.chkEnableScale.setChecked(scale_on)
            self.chkEnableRot.setChecked(rot_on)
            self.chkFeatFallback.setChecked(feat_on)
            self._preset_applying = False
            target_quality = self._initial_quality or self._last_quality_selection or "normal"
            idx = self.cbQuality.findData(target_quality)
            if idx >= 0:
                self._quality_initing = True
                self.cbQuality.setCurrentIndex(idx)
                self._quality_initing = False
            self._last_quality_selection = target_quality
            return
        if q in ("high", "high_accuracy", "accuracy", "hq"):
            self._preset_applying = True
            self.chkEnableScale.setChecked(True)
            self.chkEnableRot.setChecked(True)
            self.chkFeatFallback.setChecked(True)
            self._preset_applying = False
            return
        if q in ("performance", "perf"):
            self._preset_applying = True
            self.chkEnableScale.setChecked(False)
            self.chkEnableRot.setChecked(False)
            self.chkFeatFallback.setChecked(False)
            self._preset_applying = False
            return
        if q in ("normal", "default"):
            try:
                scale_on, rot_on, feat_on = self._last_custom_state
            except Exception:
                scale_on, rot_on, feat_on = False, False, False
            self._preset_applying = True
            self.chkEnableScale.setChecked(scale_on)
            self.chkEnableRot.setChecked(rot_on)
            self.chkFeatFallback.setChecked(feat_on)
            self._preset_applying = False

    def _on_quality_changed(self):
        if getattr(self, "_quality_initing", False):
            return
        quality = self.cbQuality.currentData() or self.cbQuality.currentText()
        q = self._normalize_quality(quality)
        if q != "reset":
            self._last_quality_selection = q
        self._apply_quality_preset(q)

    def _on_matching_toggle_changed(self):
        if getattr(self, "_preset_applying", False):
            return
        self._last_custom_state = (
            self.chkEnableScale.isChecked(),
            self.chkEnableRot.isChecked(),
            self.chkFeatFallback.isChecked(),
        )

    def _auto_fg_presets(self) -> dict:
        return {
            "stable": (80.0, 0.9, 18.0),
            "accurate": (70.0, 0.6, 12.0),
            "aggressive": (60.0, 0.35, 6.0),
        }

    def _auto_fg_preset_descriptions(self) -> dict:
        return {
            "custom": "Custom values tuned manually for this template.",
            "stable": "Stable: conservative mask. Better when background is noisy.",
            "accurate": "Accurate: balanced mask for typical UI buttons/icons.",
            "aggressive": "Aggressive: strongest separation for complex/edge-rich templates.",
        }

    def _update_auto_fg_preset_hint(self) -> None:
        key = str(self.cbAutoFgPreset.currentData() or "custom").lower()
        desc = self._auto_fg_preset_descriptions().get(key, self._auto_fg_preset_descriptions()["custom"])
        self.lblAutoFgPresetHint.setText(desc)

    def _detect_auto_fg_preset(self) -> str:
        current = (
            float(self.spAutoFgPct.value()),
            float(self.spAutoFgScale.value()),
            float(self.spAutoFgMinDist.value()),
        )
        for key, vals in self._auto_fg_presets().items():
            if all(abs(float(a) - float(b)) <= 0.05 for a, b in zip(current, vals)):
                return key
        return "custom"

    def _apply_auto_fg_preset(self, preset_key: str) -> None:
        vals = self._auto_fg_presets().get(str(preset_key or "").lower())
        if not vals:
            return
        self._auto_fg_preset_applying = True
        self.spAutoFgPct.setValue(float(vals[0]))
        self.spAutoFgScale.setValue(float(vals[1]))
        self.spAutoFgMinDist.setValue(float(vals[2]))
        self._auto_fg_preset_applying = False
        self.chkAutoFgMask.setChecked(True)

    def _on_auto_fg_preset_changed(self):
        if getattr(self, "_auto_fg_preset_initing", False):
            return
        key = self.cbAutoFgPreset.currentData() or "custom"
        key = str(key).lower()
        if key == "custom":
            self._update_auto_fg_preset_hint()
            self.lblAutoFgSuggestInfo.setText("")
            return
        self._apply_auto_fg_preset(key)
        self._update_auto_fg_preset_hint()
        self.lblAutoFgSuggestInfo.setText("")

    def _on_auto_fg_tune_changed(self):
        if getattr(self, "_auto_fg_preset_initing", False):
            return
        if getattr(self, "_auto_fg_preset_applying", False):
            return
        key = self._detect_auto_fg_preset()
        idx = self.cbAutoFgPreset.findData(key)
        if idx < 0:
            idx = self.cbAutoFgPreset.findData("custom")
        if idx >= 0 and self.cbAutoFgPreset.currentIndex() != idx:
            self._auto_fg_preset_initing = True
            self.cbAutoFgPreset.setCurrentIndex(idx)
            self._auto_fg_preset_initing = False
        self._update_auto_fg_preset_hint()
        self.lblAutoFgSuggestInfo.setText("")

    def _on_auto_fg_suggest_threshold_changed(self):
        self.lblAutoFgSuggestInfo.setText("")

    def _get_auto_fg_suggest_thresholds(self) -> tuple[float, float, float, float]:
        try:
            std_low = float(self.spAutoFgStdLow.value())
            std_high = float(self.spAutoFgStdHigh.value())
            edge_low = float(self.spAutoFgEdgeLow.value())
            edge_high = float(self.spAutoFgEdgeHigh.value())
        except Exception:
            return 18.0, 42.0, 0.07, 0.20
        std_low = max(0.0, min(128.0, std_low))
        std_high = max(0.0, min(128.0, std_high))
        edge_low = max(0.0, min(1.0, edge_low))
        edge_high = max(0.0, min(1.0, edge_high))
        if std_low > std_high:
            std_low, std_high = std_high, std_low
        if edge_low > edge_high:
            edge_low, edge_high = edge_high, edge_low
        return std_low, std_high, edge_low, edge_high

    def _auto_fg_suggestion_confidence(
        self,
        key: str,
        std: float,
        edge_density: float,
        std_low: float,
        std_high: float,
        edge_low: float,
        edge_high: float,
    ) -> int:
        try:
            k = str(key or "").lower()
            if k == "stable":
                d_std = max(0.0, (float(std_low) - float(std)) / max(float(std_low), 1e-6))
                d_edge = max(0.0, (float(edge_low) - float(edge_density)) / max(float(edge_low), 1e-6))
                conf = 60.0 + 35.0 * min(d_std, d_edge)
            elif k == "aggressive":
                d_std = max(0.0, (float(std) - float(std_high)) / max(float(std_high), 1e-6))
                d_edge = max(0.0, (float(edge_density) - float(edge_high)) / max(float(edge_high), 1e-6))
                conf = 60.0 + 35.0 * max(d_std, d_edge)
            else:
                std_center = 0.5 * (float(std_low) + float(std_high))
                edge_center = 0.5 * (float(edge_low) + float(edge_high))
                std_half = max(1.0, 0.5 * abs(float(std_high) - float(std_low)))
                edge_half = max(0.01, 0.5 * abs(float(edge_high) - float(edge_low)))
                c_std = max(0.0, 1.0 - abs(float(std) - std_center) / std_half)
                c_edge = max(0.0, 1.0 - abs(float(edge_density) - edge_center) / edge_half)
                conf = 58.0 + 32.0 * min(c_std, c_edge)
            conf = max(55.0, min(95.0, conf))
            return int(round(conf))
        except Exception:
            return 60

    def _recommend_auto_fg_preset_details(self, tpl_bgr: np.ndarray | None) -> tuple[str, int, float, float]:
        if tpl_bgr is None or tpl_bgr.size == 0:
            return "accurate", 55, 0.0, 0.0
        try:
            gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
            std = float(np.std(gray))
            edges = cv2.Canny(gray, 60, 160)
            edge_density = float(np.mean(edges > 0))
            std_low, std_high, edge_low, edge_high = self._get_auto_fg_suggest_thresholds()
            if std < std_low and edge_density < edge_low:
                key = "stable"
            elif std > std_high or edge_density > edge_high:
                key = "aggressive"
            else:
                key = "accurate"
            conf = self._auto_fg_suggestion_confidence(
                key,
                std,
                edge_density,
                std_low,
                std_high,
                edge_low,
                edge_high,
            )
            return key, conf, std, edge_density
        except Exception:
            return "accurate", 55, 0.0, 0.0

    def _recommend_auto_fg_preset_for_template(self, tpl_bgr: np.ndarray | None) -> str:
        key, _conf, _std, _edge = self._recommend_auto_fg_preset_details(tpl_bgr)
        return key

    def _on_suggest_auto_fg_preset(self):
        tpl = getattr(self._step, "_tpl_bgr", None)
        if tpl is None:
            try:
                tpl = self._step.ensure_tpl()
            except Exception:
                tpl = None
        if tpl is None:
            self.lblAutoFgSuggestInfo.setText("Suggest: load or capture template first.")
            return
        key, conf, std, edge_density = self._recommend_auto_fg_preset_details(tpl)
        idx = self.cbAutoFgPreset.findData(key)
        if idx < 0:
            idx = self.cbAutoFgPreset.findData("accurate")
        if idx >= 0:
            self.cbAutoFgPreset.setCurrentIndex(idx)
        else:
            self._apply_auto_fg_preset("accurate")
            self._update_auto_fg_preset_hint()
        self.lblAutoFgSuggestInfo.setText(
            f"Suggest: {key.capitalize()} (confidence {int(conf)}%) | "
            f"std={std:.1f}, edge={edge_density:.3f}"
        )

    def _on_capture(self):
        # Don't hide self, just overlay ROI selector
        rect, crop, _ = ROISelector.select_from_screen(self)
        if crop is not None:
            self._step.png_bytes = encode_png_bytes(crop)
            self._step._tpl_bgr = crop
            self._step._tpl_mask = None
            self._step._tpl_cache = {} # Clear cache
            self.lblAutoFgSuggestInfo.setText("")
            pm = cvimg_to_qpixmap(crop)
            self.lblPreview.setPixmap(pm.scaled(200, 150, Qt.KeepAspectRatio))

    def _on_load(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load Image", "", "Images (*.png *.jpg *.bmp)")
        if fname:
            with open(fname, "rb") as f:
                data = f.read()
            self._step.png_bytes = data
            tpl_bgr, tpl_mask = decode_png_with_mask(data)
            self._step._tpl_bgr = tpl_bgr
            self._step._tpl_mask = tpl_mask
            self._step._tpl_cache = {} # Clear cache
            self.lblAutoFgSuggestInfo.setText("")
            if self._step._tpl_bgr is not None:
                pm = cvimg_to_qpixmap(self._step._tpl_bgr)
                if pm: self.lblPreview.setPixmap(pm.scaled(200, 150, Qt.KeepAspectRatio))

    def _on_test_match(self):
        try:
            with mss.mss() as sct:
                mon = sct.monitors[0]
                frame = np.array(sct.grab(mon), dtype=np.uint8)[:, :, :3].copy()
            
            fake = StepData(**asdict(self._step))
            quality = self.cbQuality.currentData() or self.cbQuality.currentText().lower()
            fake.match_quality = quality
            fake.threshold = self.spThreshold.value()
            fake.min_confidence = self.spMinConf.value()
            fake.pre_gray = self.chkGray.isChecked()
            fake.pre_blur_ksize = int(self.spBlur.value())
            fake.pre_clahe = self.chkClahe.isChecked()
            fake.pre_edge = self.chkEdge.isChecked()
            fake.pre_sharpen = self.chkSharpen.isChecked()
            fake.match_color = self.chkMatchColor.isChecked()
            fake.color_match_tolerance = self.spColorTol.value()
            fake.alpha_mask_enable = self.chkAlphaMask.isChecked()
            fake.auto_fg_mask_enable = self.chkAutoFgMask.isChecked()
            fake.auto_fg_mask_bg_percentile = self.spAutoFgPct.value()
            fake.auto_fg_mask_dynamic_scale = self.spAutoFgScale.value()
            fake.auto_fg_mask_min_distance = self.spAutoFgMinDist.value()
            fake.auto_fg_suggest_std_low = self.spAutoFgStdLow.value()
            fake.auto_fg_suggest_std_high = self.spAutoFgStdHigh.value()
            fake.auto_fg_suggest_edge_low = self.spAutoFgEdgeLow.value()
            fake.auto_fg_suggest_edge_high = self.spAutoFgEdgeHigh.value()
            fake.hq_color_bg_robust = self.chkColorBgRobust.isChecked()
            fake.top_k = self.spTopK.value()
            fake.budget_ms = self.spBudget.value()
            fake.tpl_cache_limit = self.spTplCache.value()
            fake.search_roi_enabled = self.chkSearchRoi.isChecked()
            fake.search_roi_left = self.spRoiX.value()
            fake.search_roi_top = self.spRoiY.value()
            fake.search_roi_width = self.spRoiW.value()
            fake.search_roi_height = self.spRoiH.value()
            fake.ms_min_scale = self.spMsMin.value()
            fake.ms_max_scale = self.spMsMax.value()
            fake.ms_step = self.spMsStep.value()
            fake.rot_min_deg = self.spRotMin.value()
            fake.rot_max_deg = self.spRotMax.value()
            fake.rot_step_deg = self.spRotStep.value()
            fake.max_scales = max(1, self._max_scales_default) if self.chkEnableScale.isChecked() else 0
            fake.max_rotations = max(1, self._max_rotations_default) if self.chkEnableRot.isChecked() else 0
            fake.feat_fallback_enable = self.chkFeatFallback.isChecked()
            fake.feat_nfeatures = self.spFeatN.value()
            fake.feat_match_ratio = self.spFeatRatio.value()
            fake.feat_ransac_reproj_thresh = self.spFeatRansac.value()
            
            m = Matcher()
            mr = m.find_best_optimized(frame, fake)
            
            if mr and mr.ok:
                self.lblTest.setText(f"OK: conf={mr.score:.3f} at ({int(mr.x)},{int(mr.y)})")
            else:
                self.lblTest.setText("No match")
        except Exception as e:
            self.lblTest.setText(f"Error: {e}")

    def accept(self):
        self._step.name = self.edName.text()
        self._step.timeout_ms = self.spTimeout.value()
        self._step.threshold = self.spThreshold.value()
        self._step.min_confidence = self.spMinConf.value()
        quality = self.cbQuality.currentData() or self.cbQuality.currentText().lower()
        self._step.match_quality = quality
        self._step.pre_delay_ms = self.spPreDelay.value()
        self._step.pre_gray = self.chkGray.isChecked()
        self._step.pre_blur_ksize = self.spBlur.value()
        self._step.pre_clahe = self.chkClahe.isChecked()
        self._step.pre_edge = self.chkEdge.isChecked()
        self._step.pre_sharpen = self.chkSharpen.isChecked()
        self._step.match_color = self.chkMatchColor.isChecked()
        self._step.color_match_tolerance = self.spColorTol.value()
        self._step.alpha_mask_enable = self.chkAlphaMask.isChecked()
        self._step.auto_fg_mask_enable = self.chkAutoFgMask.isChecked()
        self._step.auto_fg_mask_bg_percentile = self.spAutoFgPct.value()
        self._step.auto_fg_mask_dynamic_scale = self.spAutoFgScale.value()
        self._step.auto_fg_mask_min_distance = self.spAutoFgMinDist.value()
        self._step.auto_fg_suggest_std_low = self.spAutoFgStdLow.value()
        self._step.auto_fg_suggest_std_high = self.spAutoFgStdHigh.value()
        self._step.auto_fg_suggest_edge_low = self.spAutoFgEdgeLow.value()
        self._step.auto_fg_suggest_edge_high = self.spAutoFgEdgeHigh.value()
        self._step.hq_color_bg_robust = self.chkColorBgRobust.isChecked()
        self._step.poll_ms = self.spPoll.value()
        self._step.top_k = self.spTopK.value()
        self._step.search_roi_enabled = self.chkSearchRoi.isChecked()
        self._step.search_roi_left = self.spRoiX.value()
        self._step.search_roi_top = self.spRoiY.value()
        self._step.search_roi_width = self.spRoiW.value()
        self._step.search_roi_height = self.spRoiH.value()
        self._step.ms_min_scale = self.spMsMin.value()
        self._step.ms_max_scale = self.spMsMax.value()
        self._step.ms_step = self.spMsStep.value()
        self._step.rot_min_deg = self.spRotMin.value()
        self._step.rot_max_deg = self.spRotMax.value()
        self._step.rot_step_deg = self.spRotStep.value()
        self._step.max_scales = max(1, self._max_scales_default) if self.chkEnableScale.isChecked() else 0
        self._step.max_rotations = max(1, self._max_rotations_default) if self.chkEnableRot.isChecked() else 0
        self._step.feat_fallback_enable = self.chkFeatFallback.isChecked()
        self._step.feat_nfeatures = self.spFeatN.value()
        self._step.feat_match_ratio = self.spFeatRatio.value()
        self._step.feat_ransac_reproj_thresh = self.spFeatRansac.value()
        self._step.tpl_cache_limit = self.spTplCache.value()
        self._step.jitter = self.spJitter.value()
        self._step.click_offset_x = self.spOffsetX.value()
        self._step.click_offset_y = self.spOffsetY.value()
        self._step.pre_move_sleep_ms = self.spPreMoveSleep.value()
        self._step.press_duration_ms = self.spPressDur.value()
        self._step.post_click_sleep_ms = self.spPostSleep.value()
        self._step.find_all_targets = self.chkFindAll.isChecked()
        self._step.hold_until_next = self.chkHoldUntil.isChecked()
        self._step.hold_timeout_ms = self.spHoldTimeout.value()
        self._step.hold_reclick_interval_ms = self.spHoldReclick.value()
        self._step.hold_reacquire_each_time = self.chkHoldReacquire.isChecked()
        self._step.hold_release_consecutive = self.spHoldRelease.value()
        self._step.budget_ms = self.spBudget.value()
        self._step.click_anchor = self.cbAnchor.currentText()
        self._step.loop_until_hide = self.chkLoopUntilHide.isChecked()

        # action mapping
        act_idx = self.cbAction.currentIndex()
        if act_idx == 0:
            self._step.image_action = "click"
            self._step.click_double = False
        elif act_idx == 1:
            self._step.image_action = "click"
            self._step.click_double = True
        elif act_idx == 2:
            self._step.image_action = "move"
            self._step.click_double = False
        else:
            self._step.image_action = "none"
            self._step.click_double = False

        self._step.click_btn = self.cbClickBtn.currentText()
        super().accept()

    def get_step_data(self):
        return self._step

class NotImageDialog(BaseDialog):
    def __init__(self, step: StepData | None, all_steps: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Step")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModal)

        self._step = step
        self._all_steps = all_steps
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._legacy_settings = QSettings(LEGACY_SETTINGS_ORG, LEGACY_SETTINGS_APP)
        self._migrate_recent_paths()
        self.undo_stack = UndoStack()
        self._key_recording = False
        # Jump If summary label placeholder to avoid attribute errors before UI build
        self.lblJumpSummary = QLabel("조건을 설정해주세요.")
        self.lblOcrJumpSummary = QLabel("조건을 설정해주세요.")
        
        # 임시 ROI 저장을 위한 변수
        if step and step.type == 'screenshot_roi':
            self._screenshot_roi = (step.screenshot_roi_x, step.screenshot_roi_y, step.screenshot_roi_w, step.screenshot_roi_h)
        else:
            self._screenshot_roi = (0,0,0,0)
            
        if step and step.type == 'ocr_check_text':
            self._ocr_roi = (step.ocr_roi_x, step.ocr_roi_y, step.ocr_roi_w, step.ocr_roi_h)
        else:
            self._ocr_roi = (0,0,0,0)
        if step and step.type == 'ocr_store':
            self._ocr_store_roi = (step.ocr_roi_x, step.ocr_roi_y, step.ocr_roi_w, step.ocr_roi_h)
        else:
            self._ocr_store_roi = (0,0,0,0)
        if step and step.type == 'ocr_jump_if':
            self._ocr_jump_roi = (step.ocr_roi_x, step.ocr_roi_y, step.ocr_roi_w, step.ocr_roi_h)
        else:
            self._ocr_jump_roi = (0,0,0,0)

        layout = QVBoxLayout(self)
        # Undo/Redo buttons
        undo_row = QHBoxLayout()
        self.btnUndo = QPushButton("Undo")
        self.btnRedo = QPushButton("Redo")
        self.btnUndo.clicked.connect(self._on_undo)
        self.btnRedo.clicked.connect(self._on_redo)
        self._update_undo_buttons()
        undo_row.addWidget(self.btnUndo)
        undo_row.addWidget(self.btnRedo)
        layout.addLayout(undo_row)
        
        # Type Selection
        typeLayout = QHBoxLayout()
        typeLayout.addWidget(QLabel("Action Type:"))
        self.cbType = QComboBox()
        self.cbType.addItems([
            "text", "key", "key_down", "key_up", "key_hold", "keyboard",
            "mouse", "click_point", "drag", "scroll", 
            "wait",
            "screen_check", "pixel_check", "start_loop", "end_loop",
            "compare_images",
            "screenshot_roi", "ocr_check_text", "ocr_store", "ocr_jump_if",
            "file_action", "load_data_file",
            "jump_if",
            "run_macro",
            "comment"
        ])
        typeLayout.addWidget(self.cbType)
        layout.addLayout(typeLayout)

        # 초기 타입 선택 및 가시성 설정
        self.cbType.currentTextChanged.connect(self._refresh_visibility)
        if step:
            self._select_step_type(step.type)
        else:
            self.cbType.setCurrentIndex(0)

        # Common Fields
        form = QFormLayout()
        self.edName = QLineEdit(step.name if step else "")
        form.addRow("Name:", self.edName)
        self.spPreDelay = QSpinBox()
        self.spPreDelay.setRange(0, 999999)
        self.spPreDelay.setValue(step.pre_delay_ms if step else 0)
        self.spPreDelay.setSuffix(" ms")
        form.addRow("Pre-delay:", self.spPreDelay)
        self.lblMouseMode = QLabel("Mouse Mode:")
        self.cbMouseMode = QComboBox()
        self.cbMouseMode.addItems(["click_point", "drag", "scroll"])
        mouse_mode = "click_point"
        if step and step.type == "mouse":
            mouse_mode = getattr(step, "mouse_mode", "") or "click_point"
        idx = self.cbMouseMode.findText(mouse_mode)
        if idx >= 0:
            self.cbMouseMode.setCurrentIndex(idx)
        self.cbMouseMode.currentTextChanged.connect(self._refresh_visibility)
        form.addRow(self.lblMouseMode, self.cbMouseMode)
        self.lblMouseMode.setVisible(False)
        self.cbMouseMode.setVisible(False)
        self.lblScreenCheckMode = QLabel("Screen Check Mode:")
        self.cbScreenCheckMode = QComboBox()
        self.cbScreenCheckMode.addItems(["pixel_check", "ocr_check_text"])
        screen_mode = "pixel_check"
        if step and step.type == "screen_check":
            screen_mode = getattr(step, "screen_check_mode", "") or "pixel_check"
        idx = self.cbScreenCheckMode.findText(screen_mode)
        if idx >= 0:
            self.cbScreenCheckMode.setCurrentIndex(idx)
        self.cbScreenCheckMode.currentTextChanged.connect(self._refresh_visibility)
        form.addRow(self.lblScreenCheckMode, self.cbScreenCheckMode)
        self.lblScreenCheckMode.setVisible(False)
        self.cbScreenCheckMode.setVisible(False)
        self.lblFileActionMode = QLabel("File Action Mode:")
        self.cbFileActionMode = QComboBox()
        self.cbFileActionMode.addItems(["load_data_file", "run_macro"])
        file_mode = "load_data_file"
        if step and step.type == "file_action":
            file_mode = getattr(step, "file_action_mode", "") or "load_data_file"
        idx = self.cbFileActionMode.findText(file_mode)
        if idx >= 0:
            self.cbFileActionMode.setCurrentIndex(idx)
        self.cbFileActionMode.currentTextChanged.connect(self._refresh_visibility)
        form.addRow(self.lblFileActionMode, self.cbFileActionMode)
        self.lblFileActionMode.setVisible(False)
        self.cbFileActionMode.setVisible(False)
        layout.addLayout(form)

        # Dynamic Content Area
        self.contentWidget = QWidget()
        self.contentLayout = QVBoxLayout(self.contentWidget)
        layout.addWidget(self.contentWidget)
        
        # Setup specific groups (temporarily keep old layout order)
        self._init_input_widgets()
        self._init_vision_widgets()
        self._init_logic_widgets()
        self._setup_temporary_layout()
        # Ensure main grouped UI is built
        self._init_groups()
        self._refresh_visibility()
        self._update_key_record_ui()
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ---- Legacy stubs (structure split was postponed) ----
    def _init_input_widgets(self):
        """Placeholder for input widgets initialization (compatibility)."""
        return

    def _init_vision_widgets(self):
        """Placeholder for vision widgets initialization (compatibility)."""
        return

    def _init_logic_widgets(self):
        """Placeholder for logic widgets initialization (compatibility)."""
        return

    def _setup_temporary_layout(self):
        """Placeholder to keep old layout intact (compatibility)."""
        return

    def _select_step_type(self, step_type: str | None) -> None:
        if not step_type:
            self.cbType.setCurrentIndex(0)
            return
        # Legacy alias: old "action" wrapper maps to the unified keyboard entry.
        if step_type == "action":
            step_type = "keyboard"
        idx = self.cbType.findText(step_type)
        if idx >= 0:
            self.cbType.setCurrentIndex(idx)
            return
        label = f"{step_type} (legacy)"
        self.cbType.addItem(label, step_type)
        legacy_idx = self.cbType.findText(label)
        if legacy_idx >= 0:
            self.cbType.setItemData(legacy_idx, "Legacy step (compatibility).", Qt.ToolTipRole)
            self.cbType.setCurrentIndex(legacy_idx)

    def _migrate_recent_paths(self) -> None:
        for key in ("last_macro_path", "last_data_file_path"):
            cur = self._settings.value(key, "")
            if cur:
                continue
            try:
                legacy = self._legacy_settings.value(key, "")
            except Exception:
                legacy = ""
            if legacy:
                try:
                    self._settings.setValue(key, legacy)
                except Exception as e:
                    self._warn_once("migrate_recent_paths_write", f"Recent path migration write failed for '{key}': {e}")

    def _get_recent_path(self, key: str) -> str:
        try:
            val = self._settings.value(key, "")
        except Exception:
            return ""
        if val:
            return str(val)
        # Compatibility fallback for old namespace.
        try:
            legacy = self._legacy_settings.value(key, "")
        except Exception:
            legacy = ""
        if legacy:
            try:
                self._settings.setValue(key, legacy)
            except Exception as e:
                self._warn_once("get_recent_path_writeback", f"Recent path write-back failed for '{key}': {e}")
            return str(legacy)
        return ""

    def _store_recent_path(self, key: str, path: str) -> None:
        if not path:
            return
        try:
            self._settings.setValue(key, path)
        except Exception as e:
            self._warn_once("store_recent_path", f"Failed to store recent path for '{key}': {e}")

    def _default_macro_path(self) -> str:
        if self._step:
            path = getattr(self._step, "target_macro_path", "") or ""
            if path:
                return path
        return self._get_recent_path("last_macro_path")

    def _default_data_file_path(self) -> str:
        if self._step:
            path = getattr(self._step, "data_file_path", "") or ""
            if path:
                return path
        return self._get_recent_path("last_data_file_path")

    def _init_groups(self):
        # Key Group
        self.groupKey = QGroupBox("Keyboard")
        keyLayout = QFormLayout(self.groupKey)
        self.lblKeyMode = QLabel("Mode:")
        self.cbKeyMode = QComboBox()
        self.cbKeyMode.addItems(["text", "key", "key_down", "key_up", "key_hold"])
        self.cbKeyMode.currentTextChanged.connect(self._refresh_visibility)
        mode = "text"
        if self._step:
            if self._step.type == "keyboard":
                mode = getattr(self._step, "keyboard_mode", "") or "text"
            elif self._step.type in ["text", "key", "key_down", "key_up", "key_hold"]:
                mode = self._step.type
        idx = self.cbKeyMode.findText(mode)
        if idx >= 0:
            self.cbKeyMode.setCurrentIndex(idx)
        keyLayout.addRow(self.lblKeyMode, self.cbKeyMode)
        self.edKey = QLineEdit(self._step.key_string if self._step else "")
        keyRow = QWidget()
        keyRowLayout = QHBoxLayout(keyRow)
        keyRowLayout.setContentsMargins(0, 0, 0, 0)
        keyRowLayout.setSpacing(6)
        keyRowLayout.addWidget(self.edKey, 1)
        self.btnKeyRecord = QPushButton("REC")
        self.btnKeyRecord.setCheckable(True)
        self.btnKeyRecord.setFixedWidth(52)
        self.btnKeyRecord.setToolTip("특수키를 눌러 Key String에 자동 입력")
        self.btnKeyRecord.toggled.connect(self._on_toggle_key_record)
        keyRowLayout.addWidget(self.btnKeyRecord)
        keyLayout.addRow("Key String:", keyRow)
        self.lblKeyHint = QLabel("#=random A-Z, @=random a-z, ?=random 0-9, {seq}=increment")
        self.lblKeyHint.setStyleSheet("color:#888; font-size:10px;")
        self.lblKeyHint.setWordWrap(True)
        keyLayout.addRow(self.lblKeyHint)
        self.contentLayout.addWidget(self.groupKey)
        
        # Click Group
        self.groupClick = QGroupBox("Mouse Click")
        clickLayout = QFormLayout(self.groupClick)
        self.spClickX = QSpinBox(); self.spClickX.setRange(-9999, 9999)
        self.spClickY = QSpinBox(); self.spClickY.setRange(-9999, 9999)
        if self._step:
            self.spClickX.setValue(self._step.click_x or 0)
            self.spClickY.setValue(self._step.click_y or 0)
        clickLayout.addRow("X:", self.spClickX)
        clickLayout.addRow("Y:", self.spClickY)
        self.btnPickClick = QPushButton("Pick Point")
        self.btnPickClick.clicked.connect(self._on_pick_click)
        clickLayout.addRow(self.btnPickClick)
        self.contentLayout.addWidget(self.groupClick)

        # Drag Group
        self.groupDrag = QGroupBox("Mouse Drag")
        dragLayout = QFormLayout(self.groupDrag)
        self.spDragFromX = QSpinBox(); self.spDragFromX.setRange(-99999, 99999)
        self.spDragFromY = QSpinBox(); self.spDragFromY.setRange(-99999, 99999)
        self.spDragToX = QSpinBox(); self.spDragToX.setRange(-99999, 99999)
        self.spDragToY = QSpinBox(); self.spDragToY.setRange(-99999, 99999)
        self.spDragDuration = QSpinBox(); self.spDragDuration.setRange(0, 600000); self.spDragDuration.setSuffix(" ms")
        if self._step:
            self.spDragFromX.setValue(self._step.drag_from_x or 0)
            self.spDragFromY.setValue(self._step.drag_from_y or 0)
            self.spDragToX.setValue(self._step.drag_to_x or 0)
            self.spDragToY.setValue(self._step.drag_to_y or 0)
            self.spDragDuration.setValue(self._step.drag_duration_ms or 0)
        else:
            self.spDragDuration.setValue(500)
        dragLayout.addRow("From X:", self.spDragFromX); dragLayout.addRow("From Y:", self.spDragFromY)
        dragLayout.addRow("To X:", self.spDragToX); dragLayout.addRow("To Y:", self.spDragToY)
        dragLayout.addRow("Duration:", self.spDragDuration)
        btnPickFrom = QPushButton("Pick From")
        btnPickTo = QPushButton("Pick To")
        btnPickFrom.clicked.connect(self._on_pick_drag_from)
        btnPickTo.clicked.connect(self._on_pick_drag_to)
        dragBtnRow = QHBoxLayout(); dragBtnRow.addWidget(btnPickFrom); dragBtnRow.addWidget(btnPickTo)
        dragLayout.addRow(dragBtnRow)
        self.contentLayout.addWidget(self.groupDrag)

        # Scroll Group
        self.groupScroll = QGroupBox("Scroll")
        scrollLayout = QFormLayout(self.groupScroll)
        self.spScrollDx = QSpinBox(); self.spScrollDx.setRange(-10000, 10000)
        self.spScrollDy = QSpinBox(); self.spScrollDy.setRange(-10000, 10000)
        self.spScrollTimes = QSpinBox(); self.spScrollTimes.setRange(1, 1000)
        self.spScrollInterval = QSpinBox(); self.spScrollInterval.setRange(0, 600000); self.spScrollInterval.setSuffix(" ms")
        if self._step:
            self.spScrollDx.setValue(self._step.scroll_dx or 0)
            self.spScrollDy.setValue(self._step.scroll_dy or 0)
            self.spScrollTimes.setValue(self._step.scroll_times or 1)
            self.spScrollInterval.setValue(self._step.scroll_interval_ms or 0)
        scrollLayout.addRow("Delta X:", self.spScrollDx)
        scrollLayout.addRow("Delta Y:", self.spScrollDy)
        scrollLayout.addRow("Times:", self.spScrollTimes)
        scrollLayout.addRow("Interval:", self.spScrollInterval)
        self.contentLayout.addWidget(self.groupScroll)

        # Pixel Check Group
        self.groupPixel = QGroupBox("Pixel Check")
        pxLayout = QFormLayout(self.groupPixel)
        self.spPixelX = QSpinBox(); self.spPixelX.setRange(-99999, 99999)
        self.spPixelY = QSpinBox(); self.spPixelY.setRange(-99999, 99999)
        self.edPixelHex = QLineEdit(self._step.pixel_color_hex if self._step else "")
        self.edPixelHex.setPlaceholderText("#RRGGBB")
        self.spPixelTol = QSpinBox(); self.spPixelTol.setRange(0, 255)
        self.spPixelTol.setValue(self._step.pixel_color_tolerance if self._step else 0)
        self.cbPixelGoto = QComboBox()
        self.cbPixelGoto.addItem("(None)", None)
        for s in self._all_steps:
            self.cbPixelGoto.addItem(f"[{s.type}] {s.name}", s.id)
        if self._step and self._step.pixel_success_goto_id:
            idx = self.cbPixelGoto.findData(self._step.pixel_success_goto_id)
            if idx >= 0: self.cbPixelGoto.setCurrentIndex(idx)
        if self._step:
            self.spPixelX.setValue(self._step.pixel_x or 0)
            self.spPixelY.setValue(self._step.pixel_y or 0)
        pxLayout.addRow("X:", self.spPixelX)
        pxLayout.addRow("Y:", self.spPixelY)
        pxLayout.addRow("Color:", self.edPixelHex)
        pxLayout.addRow("Tolerance:", self.spPixelTol)
        pxLayout.addRow("On Match Goto:", self.cbPixelGoto)
        self.contentLayout.addWidget(self.groupPixel)

        # Loop Group (start/end)
        self.groupLoop = QGroupBox("Loop Control")
        loopLayout = QFormLayout(self.groupLoop)
        self.spLoopCount = QSpinBox(); self.spLoopCount.setRange(0, 999999); self.spLoopCount.setSpecialValueText("Infinite")
        self.cbLoopStartRef = QComboBox()
        self.cbLoopStartRef.addItem("(None)", None)
        for s in self._all_steps:
            if s.type == "start_loop":
                self.cbLoopStartRef.addItem(f"{s.name} ({s.id})", s.id)
        if self._step:
            if self._step.type == "start_loop":
                self.spLoopCount.setValue(self._step.loop_count or 0)
            if self._step.type == "end_loop" and self._step.start_loop_id:
                idx = self.cbLoopStartRef.findData(self._step.start_loop_id)
                if idx >= 0: self.cbLoopStartRef.setCurrentIndex(idx)
        loopLayout.addRow("Repeat Count (0=inf):", self.spLoopCount)
        loopLayout.addRow("Loop Start ID (for end_loop):", self.cbLoopStartRef)
        self.contentLayout.addWidget(self.groupLoop)

        # Screenshot ROI Group
        self.groupShot = QGroupBox("Screenshot ROI")
        shotLayout = QFormLayout(self.groupShot)
        self.edShotPath = QLineEdit(self._step.screenshot_save_path if self._step else "")
        self.btnShotBrowse = QPushButton("Browse...")
        self.btnShotBrowse.clicked.connect(lambda: self._browse_file(self.edShotPath, save=True))
        shotPathRow = QHBoxLayout(); shotPathRow.addWidget(self.edShotPath); shotPathRow.addWidget(self.btnShotBrowse)
        self.btnPickShotRoi = QPushButton("Pick Region")
        self.btnPickShotRoi.clicked.connect(self._on_pick_shot_roi)
        self.edShotRoiDisplay = QLineEdit()
        self.edShotRoiDisplay.setReadOnly(True)
        if self._step and self._step.screenshot_roi_w and self._step.screenshot_roi_h:
            self.edShotRoiDisplay.setText(f"{self._step.screenshot_roi_x},{self._step.screenshot_roi_y} {self._step.screenshot_roi_w}x{self._step.screenshot_roi_h}")
        shotRoiRow = QHBoxLayout(); shotRoiRow.addWidget(self.edShotRoiDisplay); shotRoiRow.addWidget(self.btnPickShotRoi)
        shotLayout.addRow("Save Path:", shotPathRow)
        shotLayout.addRow("Region:", shotRoiRow)
        self.contentLayout.addWidget(self.groupShot)

        # Comment (simple text)
        self.groupComment = QGroupBox("Comment")
        commentLayout = QFormLayout(self.groupComment)
        self.edComment = QLineEdit(getattr(self._step, "comment", "") if self._step else "")
        commentLayout.addRow("Text:", self.edComment)
        self.contentLayout.addWidget(self.groupComment)

        # OCR Store Group
        self.groupOcrStore = QGroupBox("OCR: Read & Store Number")
        ocrsLayout = QFormLayout(self.groupOcrStore)
        self.edOcrStoreVar = QLineEdit()
        if self._step and self._step.type == "ocr_store":
            self.edOcrStoreVar.setText(getattr(self._step, "ocr_store_var", "") or getattr(self._step, "var_name", ""))
        ocrsLayout.addRow("Variable Name:", self.edOcrStoreVar)

        self.spOcrStoreX = QSpinBox(); self.spOcrStoreX.setRange(-99999, 99999)
        self.spOcrStoreY = QSpinBox(); self.spOcrStoreY.setRange(-99999, 99999)
        self.spOcrStoreW = QSpinBox(); self.spOcrStoreW.setRange(0, 99999)
        self.spOcrStoreH = QSpinBox(); self.spOcrStoreH.setRange(0, 99999)
        if self._step and self._step.type == "ocr_store":
            self.spOcrStoreX.setValue(getattr(self._step, "ocr_roi_x", 0))
            self.spOcrStoreY.setValue(getattr(self._step, "ocr_roi_y", 0))
            self.spOcrStoreW.setValue(getattr(self._step, "ocr_roi_w", 0))
            self.spOcrStoreH.setValue(getattr(self._step, "ocr_roi_h", 0))
        if self._ocr_store_roi and any(self._ocr_store_roi):
            self.spOcrStoreX.setValue(self._ocr_store_roi[0])
            self.spOcrStoreY.setValue(self._ocr_store_roi[1])
            self.spOcrStoreW.setValue(self._ocr_store_roi[2])
            self.spOcrStoreH.setValue(self._ocr_store_roi[3])
        roiRow = QHBoxLayout()
        self.btnPickOcrStore = QPushButton("Select Area")
        self.btnPickOcrStore.clicked.connect(self._on_pick_ocr_store_roi)
        roiRow.addWidget(self.btnPickOcrStore)
        self.edOcrStoreRoiDisplay = QLineEdit()
        self.edOcrStoreRoiDisplay.setReadOnly(True)
        if self._ocr_store_roi and any(self._ocr_store_roi):
            self.edOcrStoreRoiDisplay.setText(f"{self._ocr_store_roi[0]},{self._ocr_store_roi[1]} {self._ocr_store_roi[2]}x{self._ocr_store_roi[3]}")
        roiRow.addWidget(self.edOcrStoreRoiDisplay)
        ocrsLayout.addRow("ROI X:", self.spOcrStoreX)
        ocrsLayout.addRow("ROI Y:", self.spOcrStoreY)
        ocrsLayout.addRow("ROI W:", self.spOcrStoreW)
        ocrsLayout.addRow("ROI H:", self.spOcrStoreH)
        ocrsLayout.addRow("ROI Select:", roiRow)

        self.chkOcrStoreInvert = QCheckBox("Invert Colors")
        self.chkOcrStoreHighContrast = QCheckBox("High Contrast (Threshold)")
        if self._step and self._step.type == "ocr_store":
            if getattr(self._step, "ocr_invert", False):
                self.chkOcrStoreInvert.setChecked(True)
            mode = getattr(self._step, "ocr_preprocess_mode", "otsu") or "otsu"
            if mode != "none":
                self.chkOcrStoreHighContrast.setChecked(True)
        ocrsLayout.addRow(self.chkOcrStoreInvert)
        ocrsLayout.addRow(self.chkOcrStoreHighContrast)

        self.btnTestOcrStore = QPushButton("Test Reading")
        self.btnTestOcrStore.clicked.connect(self._on_test_ocr_store)
        self.lblTestOcrResult = QLabel("")
        ocrsLayout.addRow(self.btnTestOcrStore, self.lblTestOcrResult)

        self.contentLayout.addWidget(self.groupOcrStore)

        # Run Macro Group
        self.groupRunMacro = QGroupBox("Run Macro (Sub-script)")
        runLayout = QFormLayout(self.groupRunMacro)
        self.edRunMacroPath = QLineEdit(self._default_macro_path())
        self.edRunMacroPath.setReadOnly(True)
        self.btnBrowseRunMacro = QPushButton("Browse...")
        self.btnBrowseRunMacro.clicked.connect(self._on_browse_run_macro)
        pathRow = QHBoxLayout()
        pathRow.addWidget(self.edRunMacroPath, 1)
        pathRow.addWidget(self.btnBrowseRunMacro)
        runLayout.addRow("Macro File:", pathRow)
        if self._step and self._step.type == "run_macro":
            self.edRunMacroPath.setText(getattr(self._step, "target_macro_path", "") or "")
        elif self._step and self._step.type == "file_action":
            if getattr(self._step, "file_action_mode", "") == "run_macro":
                self.edRunMacroPath.setText(getattr(self._step, "target_macro_path", "") or "")
        if not self.edRunMacroPath.text().strip():
            self.edRunMacroPath.setText(self._default_macro_path())
        self.contentLayout.addWidget(self.groupRunMacro)

        # Wait Group
        self.groupWait = QGroupBox("Wait")
        waitLayout = QFormLayout(self.groupWait)
        self.spWaitMs = QSpinBox()
        self.spWaitMs.setRange(0, 3_600_000)
        self.spWaitMs.setSuffix(" ms")
        self.spWaitMs.setValue(int(getattr(self._step, "wait_ms", 0) or 0) if self._step else 0)
        waitLayout.addRow("Duration:", self.spWaitMs)
        self.contentLayout.addWidget(self.groupWait)

        # Compare Images Group
        self.groupCompare = QGroupBox("Compare Images")
        cmpLayout = QFormLayout(self.groupCompare)
        self.edCompareImageA = QLineEdit("")
        self.btnCompareImageABrowse = QPushButton("Browse...")
        self.btnCompareImageABrowse.clicked.connect(self._on_browse_compare_image_a)
        rowA = QHBoxLayout()
        rowA.addWidget(self.edCompareImageA)
        rowA.addWidget(self.btnCompareImageABrowse)
        cmpLayout.addRow("Image A:", rowA)

        self.edCompareImageB = QLineEdit("")
        self.btnCompareImageBBrowse = QPushButton("Browse...")
        self.btnCompareImageBBrowse.clicked.connect(self._on_browse_compare_image_b)
        rowB = QHBoxLayout()
        rowB.addWidget(self.edCompareImageB)
        rowB.addWidget(self.btnCompareImageBBrowse)
        cmpLayout.addRow("Image B:", rowB)

        self.cbCompareMode = QComboBox()
        self.cbCompareMode.addItem("MSE", "mse")
        self.cbCompareMode.addItem("SSIM", "ssim")
        self.cbCompareMode.addItem("Hash", "hash")
        cmpLayout.addRow("Mode:", self.cbCompareMode)

        self.spCompareThreshold = QDoubleSpinBox()
        self.spCompareThreshold.setRange(0.0, 1_000_000_000.0)
        self.spCompareThreshold.setDecimals(6)
        self.spCompareThreshold.setSingleStep(0.01)
        cmpLayout.addRow("Threshold:", self.spCompareThreshold)

        self.spCompareRoiX = QSpinBox(); self.spCompareRoiX.setRange(-99999, 99999)
        self.spCompareRoiY = QSpinBox(); self.spCompareRoiY.setRange(-99999, 99999)
        self.spCompareRoiW = QSpinBox(); self.spCompareRoiW.setRange(0, 99999)
        self.spCompareRoiH = QSpinBox(); self.spCompareRoiH.setRange(0, 99999)
        cmpLayout.addRow("ROI X:", self.spCompareRoiX)
        cmpLayout.addRow("ROI Y:", self.spCompareRoiY)
        cmpLayout.addRow("ROI W:", self.spCompareRoiW)
        cmpLayout.addRow("ROI H:", self.spCompareRoiH)

        self.cbCompareMatchGoto = QComboBox()
        self.cbCompareMatchGoto.addItem("(None)", None)
        self.cbCompareFailGoto = QComboBox()
        self.cbCompareFailGoto.addItem("(None)", None)
        for s in self._all_steps:
            label = f"[{s.type}] {s.name}"
            self.cbCompareMatchGoto.addItem(label, s.id)
            self.cbCompareFailGoto.addItem(label, s.id)
        cmpLayout.addRow("On Match Goto:", self.cbCompareMatchGoto)
        cmpLayout.addRow("On Fail Goto:", self.cbCompareFailGoto)

        if self._step and self._step.type == "compare_images":
            self.edCompareImageA.setText(getattr(self._step, "image_a_path", "") or "")
            self.edCompareImageB.setText(getattr(self._step, "image_b_path", "") or "")
            mode = str(getattr(self._step, "compare_mode", "mse") or "mse").lower()
            idx = self.cbCompareMode.findData(mode)
            if idx >= 0:
                self.cbCompareMode.setCurrentIndex(idx)
            self.spCompareThreshold.setValue(float(getattr(self._step, "compare_threshold", 0.0) or 0.0))
            self.spCompareRoiX.setValue(int(getattr(self._step, "compare_roi_x", 0) or 0))
            self.spCompareRoiY.setValue(int(getattr(self._step, "compare_roi_y", 0) or 0))
            self.spCompareRoiW.setValue(int(getattr(self._step, "compare_roi_w", 0) or 0))
            self.spCompareRoiH.setValue(int(getattr(self._step, "compare_roi_h", 0) or 0))
            idx = self.cbCompareMatchGoto.findData(getattr(self._step, "on_match_goto_id", None))
            if idx >= 0:
                self.cbCompareMatchGoto.setCurrentIndex(idx)
            idx = self.cbCompareFailGoto.findData(getattr(self._step, "branch_on_fail_goto_id", None))
            if idx >= 0:
                self.cbCompareFailGoto.setCurrentIndex(idx)
        if not self.edCompareImageA.text().strip():
            self.edCompareImageA.setText(self._get_recent_path("last_compare_image_a_path"))
        if not self.edCompareImageB.text().strip():
            self.edCompareImageB.setText(self._get_recent_path("last_compare_image_b_path"))
        self.contentLayout.addWidget(self.groupCompare)

        # Jump If Group (Conditional Branching) - sentence style + summary
        self.groupJumpIf = QGroupBox("Logic: Jump If")
        jumpLayout = QVBoxLayout(self.groupJumpIf)

        jumpRow = QHBoxLayout()
        jumpRow.addWidget(QLabel("만약 (If)"))

        self.edJumpVar = QComboBox()
        self.edJumpVar.setEditable(True)
        self.edJumpVar.setInsertPolicy(QComboBox.NoInsert)
        self.edJumpVar.lineEdit().setPlaceholderText("e.g., current_hp")
        self._populate_variable_suggestions()
        jumpRow.addWidget(self.edJumpVar)

        self.btnJumpHelp = QPushButton("?")
        self.btnJumpHelp.setFixedWidth(28)
        self.btnJumpHelp.setToolTip("변수는 OCR 저장 스텝에서 읽어온 값입니다.")
        self.btnJumpHelp.clicked.connect(self._show_jump_help)
        jumpRow.addWidget(self.btnJumpHelp)

        self.cbJumpOp = QComboBox()
        for text, val in [
            ("초과 (>)", ">"),
            ("미만 (<)", "<"),
            ("같음 (==)", "=="),
            ("다름 (!=)", "!="),
            ("이상 (>=)", ">="),
            ("이하 (<=)", "<="),
        ]:
            self.cbJumpOp.addItem(text, val)
        jumpRow.addWidget(self.cbJumpOp)

        self.edJumpValue = QLineEdit()
        self.edJumpValue.setPlaceholderText("비교 값 (예: 500)")
        jumpRow.addWidget(self.edJumpValue)

        jumpRow.addWidget(QLabel("라면 (Then)"))
        self.cbJumpTarget = QComboBox()
        self.cbJumpTarget.addItem("(Select target step)", None)
        self._jump_idx_map = {}
        for idx, s in enumerate(self._all_steps):
            label = f"{idx+1}. {s.name}"
            self.cbJumpTarget.addItem(label, idx)
            self._jump_idx_map[s.id] = idx
        jumpRow.addWidget(self.cbJumpTarget)
        jumpRow.addWidget(QLabel("로 이동"))

        jumpLayout.addLayout(jumpRow)

        if self._step and self._step.type == "jump_if":
            if getattr(self._step, "condition_var", None):
                self.edJumpVar.setCurrentText(str(getattr(self._step, "condition_var")))
            op_val = getattr(self._step, "condition_operator", None) or getattr(self._step, "condition_op", None)
            if op_val:
                idx = self.cbJumpOp.findData(str(op_val))
                if idx >= 0:
                    self.cbJumpOp.setCurrentIndex(idx)
                else:
                    self.cbJumpOp.setCurrentText(str(op_val))
            if getattr(self._step, "condition_value", None) is not None:
                self.edJumpValue.setText(str(getattr(self._step, "condition_value")))
            sel_idx = None
            tgt_id = getattr(self._step, "target_true_id", None)
            if getattr(self._step, "target_true_index", None) is not None:
                sel_idx = getattr(self._step, "target_true_index")
            elif tgt_id:
                sel_idx = self._jump_idx_map.get(tgt_id)
            if sel_idx is not None:
                target_idx = self.cbJumpTarget.findData(sel_idx)
                if target_idx >= 0:
                    self.cbJumpTarget.setCurrentIndex(target_idx)

        self.lblJumpSummary.setText("조건을 설정해주세요.")
        self.lblJumpSummary.setStyleSheet("color:#5aa;")
        jumpLayout.addWidget(self.lblJumpSummary)

        hint = QLabel("변수 이름은 OCR 저장 스텝에서 읽어온 값과 동일해야 합니다.")
        hint.setStyleSheet("color:#888; font-size:10px;")
        jumpLayout.addWidget(hint)

        self.edJumpVar.currentTextChanged.connect(self._update_jump_summary)
        self.cbJumpOp.currentIndexChanged.connect(self._update_jump_summary)
        self.edJumpValue.textChanged.connect(self._update_jump_summary)
        self.cbJumpTarget.currentIndexChanged.connect(self._update_jump_summary)
        self._update_jump_summary()

        self.contentLayout.addWidget(self.groupJumpIf)


        # Load Data Group
        self.groupLoadData = QGroupBox("Load Data File")
        ldLayout = QFormLayout(self.groupLoadData)
        self.edDataFilePath = QLineEdit(self._default_data_file_path())
        self.btnDataFileBrowse = QPushButton("Browse...")
        self.btnDataFileBrowse.clicked.connect(self._on_browse_data_file)
        dataPathRow = QHBoxLayout()
        dataPathRow.addWidget(self.edDataFilePath)
        dataPathRow.addWidget(self.btnDataFileBrowse)
        ldLayout.addRow("File Path:", dataPathRow)
        self.contentLayout.addWidget(self.groupLoadData)

        # OCR Group
        self.groupOcr = QGroupBox("OCR Check")
        ocrLayout = QFormLayout(self.groupOcr)
        self.edOcrExpected = QLineEdit(self._step.ocr_expected_text if self._step else "")
        self.edOcrExpected.setPlaceholderText("Expected text (empty = any text)")
        self.edOcrWhitelist = QLineEdit(self._step.ocr_whitelist if self._step else "")
        self.edOcrWhitelist.setPlaceholderText("Optional allowed characters")
        self.cbOcrPreprocess = QComboBox()
        self.cbOcrPreprocess.addItems(["none", "thresh", "blur"])
        if self._step:
            idx = self.cbOcrPreprocess.findText(self._step.ocr_preprocess_mode or "none")
            if idx >= 0: self.cbOcrPreprocess.setCurrentIndex(idx)
        self.spOcrScale = QDoubleSpinBox()
        self.spOcrScale.setRange(1.0, 10.0)
        self.spOcrScale.setSingleStep(0.1)
        self.spOcrScale.setValue(float(getattr(self._step, "ocr_scale", 2.0) or 2.0) if self._step else 2.0)
        self.chkOcrInvert = QCheckBox("Invert Colors")
        if self._step and getattr(self._step, "ocr_invert", False):
            self.chkOcrInvert.setChecked(True)
        self.spOcrTargetHeight = QSpinBox(); self.spOcrTargetHeight.setRange(0, 5000)
        self.spOcrTargetHeight.setValue(self._step.ocr_target_height if self._step else 0)
        self.edOcrLang = QLineEdit(self._step.ocr_lang if self._step else "eng")
        self.edOcrLang.setPlaceholderText("e.g. eng, kor (requires tesseract lang pack)")
        self.chkOcrDyn = QCheckBox("Use dynamic data in expected text")
        if self._step and getattr(self._step, "ocr_use_dynamic_data", False):
            self.chkOcrDyn.setChecked(True)
        self.btnPickOcrRoi = QPushButton("Pick OCR Region")
        self.btnPickOcrRoi.clicked.connect(self._on_pick_ocr_roi)
        self.edOcrRoiDisplay = QLineEdit()
        self.edOcrRoiDisplay.setReadOnly(True)
        if self._ocr_roi and any(self._ocr_roi):
            self.edOcrRoiDisplay.setText(f"{self._ocr_roi[0]},{self._ocr_roi[1]} {self._ocr_roi[2]}x{self._ocr_roi[3]}")
        roiLayout = QHBoxLayout()
        roiLayout.addWidget(self.edOcrRoiDisplay)
        roiLayout.addWidget(self.btnPickOcrRoi)
        self.cbOcrGoto = QComboBox()
        self.cbOcrGoto.addItem("(None)", None)
        for s in self._all_steps:
            self.cbOcrGoto.addItem(f"[{s.type}] {s.name}", s.id)
        if self._step and getattr(self._step, "on_match_goto_id", None):
            idx = self.cbOcrGoto.findData(self._step.on_match_goto_id)
            if idx >= 0:
                self.cbOcrGoto.setCurrentIndex(idx)

        ocrLayout.addRow("Expected Text:", self.edOcrExpected)
        ocrLayout.addRow("Whitelist:", self.edOcrWhitelist)
        ocrLayout.addRow("Preprocess:", self.cbOcrPreprocess)
        ocrLayout.addRow("Scale:", self.spOcrScale)
        ocrLayout.addRow(self.chkOcrInvert)
        ocrLayout.addRow("Target Height:", self.spOcrTargetHeight)
        ocrLayout.addRow("Language:", self.edOcrLang)
        ocrLayout.addRow(self.chkOcrDyn)
        ocrLayout.addRow("ROI:", roiLayout)
        ocrLayout.addRow("On Match Goto:", self.cbOcrGoto)
        self.lblOcrNote = QLabel("OCR 체크는 성공 시 'On Match Goto'로만 이동합니다. 조건 분기는 'OCR Jump If'를 사용하세요.")
        self.lblOcrNote.setStyleSheet("color:#888; font-size:10px;")
        self.lblOcrNote.setWordWrap(True)
        ocrLayout.addRow(self.lblOcrNote)
        self.contentLayout.addWidget(self.groupOcr)

        # OCR Jump If Group
        self.groupOcrJump = QGroupBox("OCR Jump If")
        ocrJumpLayout = QVBoxLayout(self.groupOcrJump)
        ocrJumpForm = QFormLayout()
        self.cbOcrJumpPreprocess = QComboBox()
        self.cbOcrJumpPreprocess.addItems(["none", "thresh", "blur"])
        if self._step and self._step.type == "ocr_jump_if":
            idx = self.cbOcrJumpPreprocess.findText(self._step.ocr_preprocess_mode or "none")
            if idx >= 0:
                self.cbOcrJumpPreprocess.setCurrentIndex(idx)
        self.spOcrJumpScale = QDoubleSpinBox()
        self.spOcrJumpScale.setRange(1.0, 10.0)
        self.spOcrJumpScale.setSingleStep(0.1)
        self.spOcrJumpScale.setValue(float(getattr(self._step, "ocr_scale", 2.0) or 2.0) if self._step else 2.0)
        self.chkOcrJumpInvert = QCheckBox("Invert Colors")
        if self._step and getattr(self._step, "ocr_invert", False):
            self.chkOcrJumpInvert.setChecked(True)
        self.edOcrJumpLang = QLineEdit(self._step.ocr_lang if self._step else "eng")
        self.edOcrJumpLang.setPlaceholderText("e.g. eng, kor (requires tesseract lang pack)")
        self.btnPickOcrJumpRoi = QPushButton("Pick OCR Region")
        self.btnPickOcrJumpRoi.clicked.connect(self._on_pick_ocr_jump_roi)
        self.edOcrJumpRoiDisplay = QLineEdit()
        self.edOcrJumpRoiDisplay.setReadOnly(True)
        if self._ocr_jump_roi and any(self._ocr_jump_roi):
            self.edOcrJumpRoiDisplay.setText(
                f"{self._ocr_jump_roi[0]},{self._ocr_jump_roi[1]} {self._ocr_jump_roi[2]}x{self._ocr_jump_roi[3]}"
            )
        ocrJumpRoiLayout = QHBoxLayout()
        ocrJumpRoiLayout.addWidget(self.edOcrJumpRoiDisplay)
        ocrJumpRoiLayout.addWidget(self.btnPickOcrJumpRoi)
        ocrJumpForm.addRow("Preprocess:", self.cbOcrJumpPreprocess)
        ocrJumpForm.addRow("Scale:", self.spOcrJumpScale)
        ocrJumpForm.addRow(self.chkOcrJumpInvert)
        ocrJumpForm.addRow("Language:", self.edOcrJumpLang)
        ocrJumpForm.addRow("ROI:", ocrJumpRoiLayout)
        ocrJumpLayout.addLayout(ocrJumpForm)

        ocrJumpRow = QHBoxLayout()
        ocrJumpRow.addWidget(QLabel("OCR 값"))
        self.cbOcrJumpOp = QComboBox()
        for text, val in [
            ("초과 (>)", ">"),
            ("미만 (<)", "<"),
            ("같음 (==)", "=="),
            ("다름 (!=)", "!="),
            ("이상 (>=)", ">="),
            ("이하 (<=)", "<="),
        ]:
            self.cbOcrJumpOp.addItem(text, val)
        ocrJumpRow.addWidget(self.cbOcrJumpOp)
        self.edOcrJumpValue = QLineEdit()
        self.edOcrJumpValue.setPlaceholderText("비교 값 (예: 500)")
        ocrJumpRow.addWidget(self.edOcrJumpValue)
        self.cbOcrJumpTarget = QComboBox()
        self.cbOcrJumpTarget.addItem("(Select target step)", None)
        self._ocr_jump_idx_map = {}
        for idx, st in enumerate(self._all_steps):
            label = f"[{idx}] {st.name} ({st.type})"
            self.cbOcrJumpTarget.addItem(label, idx)
            self._ocr_jump_idx_map[getattr(st, "id", None)] = idx
        ocrJumpRow.addWidget(self.cbOcrJumpTarget)
        ocrJumpLayout.addLayout(ocrJumpRow)

        if self._step and self._step.type == "ocr_jump_if":
            op_val = getattr(self._step, "condition_operator", None)
            if op_val:
                idx = self.cbOcrJumpOp.findData(str(op_val))
                if idx >= 0:
                    self.cbOcrJumpOp.setCurrentIndex(idx)
                else:
                    self.cbOcrJumpOp.setCurrentText(str(op_val))
            if getattr(self._step, "condition_value", None) is not None:
                self.edOcrJumpValue.setText(str(getattr(self._step, "condition_value")))
            tgt_id = getattr(self._step, "target_true_id", None)
            sel_idx = getattr(self._step, "target_true_index", None)
            if sel_idx is None and tgt_id:
                sel_idx = self._ocr_jump_idx_map.get(tgt_id)
            if sel_idx is not None:
                target_idx = self.cbOcrJumpTarget.findData(sel_idx)
                if target_idx >= 0:
                    self.cbOcrJumpTarget.setCurrentIndex(target_idx)

        self.lblOcrJumpSummary.setText("조건을 설정해주세요.")
        self.lblOcrJumpSummary.setStyleSheet("color:#5aa;")
        ocrJumpLayout.addWidget(self.lblOcrJumpSummary)

        self.cbOcrJumpOp.currentIndexChanged.connect(self._update_ocr_jump_summary)
        self.edOcrJumpValue.textChanged.connect(self._update_ocr_jump_summary)
        self.cbOcrJumpTarget.currentIndexChanged.connect(self._update_ocr_jump_summary)
        self._update_ocr_jump_summary()
        self.contentLayout.addWidget(self.groupOcrJump)

        # Add other groups as needed...

    def _refresh_visibility(self):
        required = (
            "groupKey", "groupClick", "groupDrag", "groupScroll", "groupPixel",
            "groupLoop", "groupShot", "groupComment", "groupLoadData", "groupOcr",
            "groupOcrJump", "groupOcrStore", "groupJumpIf", "groupRunMacro",
            "groupWait", "groupCompare",
        )
        for name in required:
            if not hasattr(self, name):
                return
        t = self.cbType.currentText()
        if hasattr(self, "cbMouseMode"):
            self.cbMouseMode.setVisible(False)
            self.lblMouseMode.setVisible(False)
        if hasattr(self, "cbScreenCheckMode"):
            self.cbScreenCheckMode.setVisible(False)
            self.lblScreenCheckMode.setVisible(False)
        if hasattr(self, "cbFileActionMode"):
            self.cbFileActionMode.setVisible(False)
            self.lblFileActionMode.setVisible(False)
        # 1) Hide all first
        for grp in [
            self.groupKey, self.groupClick, self.groupDrag, self.groupScroll,
            self.groupPixel, self.groupLoop, self.groupShot, self.groupComment,
            self.groupLoadData, self.groupOcr, self.groupOcrJump, self.groupOcrStore,
            self.groupJumpIf, self.groupRunMacro, self.groupWait, self.groupCompare,
        ]:
            grp.setVisible(False)

        # 2) Show only the selected group
        if t in ["text", "key", "key_down", "key_up", "key_hold", "keyboard"]:
            self.groupKey.setVisible(True)
            if hasattr(self, "cbKeyMode"):
                is_keyboard = t == "keyboard"
                self.cbKeyMode.setVisible(is_keyboard)
                self.lblKeyMode.setVisible(is_keyboard)
        elif t == "mouse":
            if hasattr(self, "cbMouseMode"):
                self.cbMouseMode.setVisible(True)
                self.lblMouseMode.setVisible(True)
                mode = self.cbMouseMode.currentText() or "click_point"
            else:
                mode = "click_point"
            if mode == "drag":
                self.groupDrag.setVisible(True)
            elif mode == "scroll":
                self.groupScroll.setVisible(True)
            else:
                self.groupClick.setVisible(True)
        elif t == "screen_check":
            if hasattr(self, "cbScreenCheckMode"):
                self.cbScreenCheckMode.setVisible(True)
                self.lblScreenCheckMode.setVisible(True)
                mode = self.cbScreenCheckMode.currentText() or "pixel_check"
            else:
                mode = "pixel_check"
            if mode == "ocr_check_text":
                self.groupOcr.setVisible(True)
            else:
                self.groupPixel.setVisible(True)
        elif t == "file_action":
            if hasattr(self, "cbFileActionMode"):
                self.cbFileActionMode.setVisible(True)
                self.lblFileActionMode.setVisible(True)
                mode = self.cbFileActionMode.currentText() or "load_data_file"
            else:
                mode = "load_data_file"
            if mode == "run_macro":
                self.groupRunMacro.setVisible(True)
                if not self.edRunMacroPath.text().strip():
                    self.edRunMacroPath.setText(self._default_macro_path())
            else:
                self.groupLoadData.setVisible(True)
                if not self.edDataFilePath.text().strip():
                    self.edDataFilePath.setText(self._default_data_file_path())
        elif t == "click_point":
            self.groupClick.setVisible(True)
        elif t == "drag":
            self.groupDrag.setVisible(True)
        elif t == "scroll":
            self.groupScroll.setVisible(True)
        elif t == "wait":
            self.groupWait.setVisible(True)
        elif t == "pixel_check":
            self.groupPixel.setVisible(True)
        elif t in ["start_loop", "end_loop"]:
            self.groupLoop.setVisible(True)
        elif t == "compare_images":
            self.groupCompare.setVisible(True)
        elif t == "screenshot_roi":
            self.groupShot.setVisible(True)
        elif t == "comment":
            self.groupComment.setVisible(True)
        elif t == "load_data_file":
            self.groupLoadData.setVisible(True)
            if not self.edDataFilePath.text().strip():
                self.edDataFilePath.setText(self._default_data_file_path())
        elif t == "ocr_check_text":
            self.groupOcr.setVisible(True)
        elif t == "ocr_jump_if":
            self.groupOcrJump.setVisible(True)
            self._update_ocr_jump_summary()
        elif t == "ocr_store":
            self.groupOcrStore.setVisible(True)
        elif t == "jump_if":
            self.groupJumpIf.setVisible(True)
            self._populate_variable_suggestions()
        elif t == "run_macro":
            self.groupRunMacro.setVisible(True)
            if not self.edRunMacroPath.text().strip():
                self.edRunMacroPath.setText(self._default_macro_path())
        self._update_key_record_ui()

    def _current_key_capture_mode(self) -> str:
        t = str(self.cbType.currentText() or "").lower()
        if t == "keyboard":
            return str(self.cbKeyMode.currentText() or "text").lower()
        return t

    def _can_record_key_name(self) -> bool:
        return self._current_key_capture_mode() in {"key", "key_down", "key_up", "key_hold"}

    def _set_key_recording(self, enabled: bool) -> None:
        active = bool(enabled) and self._can_record_key_name()
        if active == self._key_recording:
            if hasattr(self, "btnKeyRecord") and bool(self.btnKeyRecord.isChecked()) != active:
                self.btnKeyRecord.blockSignals(True)
                self.btnKeyRecord.setChecked(active)
                self.btnKeyRecord.blockSignals(False)
            return
        self._key_recording = active
        app = QApplication.instance()
        if app:
            try:
                if active:
                    app.installEventFilter(self)
                else:
                    app.removeEventFilter(self)
            except Exception:
                pass
        if hasattr(self, "btnKeyRecord"):
            self.btnKeyRecord.blockSignals(True)
            self.btnKeyRecord.setChecked(active)
            self.btnKeyRecord.setText("REC..." if active else "REC")
            self.btnKeyRecord.setStyleSheet("color:#ff7b7b; font-weight:600;" if active else "")
            self.btnKeyRecord.blockSignals(False)

    def _on_toggle_key_record(self, checked: bool) -> None:
        self._set_key_recording(bool(checked))

    def _update_key_record_ui(self) -> None:
        if not hasattr(self, "btnKeyRecord"):
            return
        allowed = (not self.groupKey.isHidden()) and self._can_record_key_name()
        self.btnKeyRecord.setEnabled(allowed)
        if not allowed:
            self._set_key_recording(False)

    def _capture_recorded_key(self, event) -> bool:
        key = int(event.key())
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return True
        key_map = {
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Tab: "tab",
            Qt.Key_Backtab: "tab",
            Qt.Key_Escape: "esc",
            Qt.Key_Space: "space",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_Insert: "insert",
            Qt.Key_PageUp: "pageup",
            Qt.Key_PageDown: "pagedown",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
        }
        key_name = key_map.get(key)
        if key_name is None and Qt.Key_F1 <= key <= Qt.Key_F24:
            key_name = f"f{(key - Qt.Key_F1) + 1}"
        if key_name is None:
            text = str(event.text() or "").strip()
            if text:
                key_name = text.lower()
        if not key_name:
            return False
        self.edKey.setText(key_name)
        self._set_key_recording(False)
        self.edKey.setFocus()
        return True

    def eventFilter(self, obj, event):
        if self._key_recording and event is not None and event.type() == QEvent.KeyPress:
            if self._capture_recorded_key(event):
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self._set_key_recording(False)
        super().closeEvent(event)

    def _populate_variable_suggestions(self):
        """Populate Jump If variable suggestions from OCR store steps + system vars."""
        base_vars = ["loop_index", "loop_count"]
        seen = set()
        suggestions = []
        for v in base_vars:
            if v not in seen:
                seen.add(v)
                suggestions.append(v)

        for step in getattr(self, "_all_steps", []):
            stype = getattr(step, "type", None) or (step.get("type") if isinstance(step, dict) else None)
            if not stype or str(stype).lower() != "ocr_store":
                continue
            var = getattr(step, "ocr_store_var", None)
            if var is None and isinstance(step, dict):
                var = step.get("ocr_store_var") or step.get("var_name") or step.get("var")
            if var:
                var = str(var)
                if var not in seen:
                    seen.add(var)
                    suggestions.append(var)

        self.edJumpVar.blockSignals(True)
        self.edJumpVar.clear()
        for v in suggestions:
            self.edJumpVar.addItem(v)
        self.edJumpVar.blockSignals(False)

    def _update_jump_summary(self):
        """Update Jump If summary label."""
        if not hasattr(self, "lblJumpSummary"):
            return
        var = self.edJumpVar.currentText().strip()
        op_text = self.cbJumpOp.currentText()
        op_val = self.cbJumpOp.currentData()
        val = self.edJumpValue.text().strip()
        target = self.cbJumpTarget.currentText().strip()
        if var and op_val and val and target:
            self.lblJumpSummary.setText(
                f"요약: 만약 '{var}' {op_text} {val}이면, '{target}' 스텝으로 건너뜁니다."
            )
        else:
            self.lblJumpSummary.setText("조건을 설정해주세요.")

    def _update_ocr_jump_summary(self):
        if not hasattr(self, "lblOcrJumpSummary"):
            return
        op_text = self.cbOcrJumpOp.currentText()
        val = self.edOcrJumpValue.text().strip()
        target = self.cbOcrJumpTarget.currentText().strip()
        if val and target and target != "(Select target step)":
            self.lblOcrJumpSummary.setText(f"OCR 값이 {op_text} {val} 이면 {target}로 점프합니다.")
        else:
            self.lblOcrJumpSummary.setText("조건을 설정해주세요.")

    def _on_undo(self):
        self.undo_stack.undo()
        self._update_undo_buttons()

    def _on_redo(self):
        self.undo_stack.redo()
        self._update_undo_buttons()

    def _update_undo_buttons(self):
        self.btnUndo.setEnabled(self.undo_stack.can_undo())
        self.btnRedo.setEnabled(self.undo_stack.can_redo())

    def _show_jump_help(self):
        QMessageBox.information(
            self,
            "Jump If 도움말",
            "변수는 OCR 저장 스텝에서 읽어온 값입니다.\n예: hp, mp, count 등."
        )

    def _on_pick_click(self):
        self.hide()
        try:
            pt = safe_select_point()
            if pt:
                self.spClickX.setValue(pt.x())
                self.spClickY.setValue(pt.y())
        finally:
            self._robust_restore_self()

    def _on_pick_ocr_roi(self):
        self.hide()
        try:
            rect, _, _ = ROISelector.select_from_screen()
            if rect and not rect.isNull():
                self._ocr_roi = (rect.x(), rect.y(), rect.width(), rect.height())
                self.edOcrRoiDisplay.setText(f"{rect.x()},{rect.y()} {rect.width()}x{rect.height()}")
        finally:
            self._robust_restore_self()

    def _on_pick_ocr_jump_roi(self):
        self.hide()
        try:
            rect, _, _ = ROISelector.select_from_screen()
            if rect and not rect.isNull():
                self._ocr_jump_roi = (rect.x(), rect.y(), rect.width(), rect.height())
                self.edOcrJumpRoiDisplay.setText(f"{rect.x()},{rect.y()} {rect.width()}x{rect.height()}")
        finally:
            self._robust_restore_self()

    def _on_pick_drag_from(self):
        self.hide()
        try:
            pt = safe_select_point()
            if pt:
                self.spDragFromX.setValue(pt.x())
                self.spDragFromY.setValue(pt.y())
        finally:
            self._robust_restore_self()

    def _on_pick_drag_to(self):
        self.hide()
        try:
            pt = safe_select_point()
            if pt:
                self.spDragToX.setValue(pt.x())
                self.spDragToY.setValue(pt.y())
        finally:
            self._robust_restore_self()

    def _on_pick_shot_roi(self):
        self.hide()
        try:
            rect, _, _ = ROISelector.select_from_screen()
            if rect and not rect.isNull():
                self._screenshot_roi = (rect.x(), rect.y(), rect.width(), rect.height())
                self.edShotRoiDisplay.setText(f"{rect.x()},{rect.y()} {rect.width()}x{rect.height()}")
        finally:
            self._robust_restore_self()

    def _on_pick_ocr_store_roi(self):
        self.hide()
        try:
            rect, _, _ = ROISelector.select_from_screen()
            if rect and not rect.isNull():
                self._ocr_store_roi = (rect.x(), rect.y(), rect.width(), rect.height())
                self.edOcrStoreRoiDisplay.setText(f"{rect.x()},{rect.y()} {rect.width()}x{rect.height()}")
                self.spOcrStoreX.setValue(rect.x())
                self.spOcrStoreY.setValue(rect.y())
                self.spOcrStoreW.setValue(rect.width())
                self.spOcrStoreH.setValue(rect.height())
        finally:
            self._robust_restore_self()

    def _on_test_ocr_store(self):
        try:
            x, y, w, h = (self.spOcrStoreX.value(), self.spOcrStoreY.value(), self.spOcrStoreW.value(), self.spOcrStoreH.value())
            if (w <= 0 or h <= 0) and self._ocr_store_roi and any(self._ocr_store_roi):
                x, y, w, h = self._ocr_store_roi
                self.spOcrStoreX.setValue(x); self.spOcrStoreY.setValue(y); self.spOcrStoreW.setValue(w); self.spOcrStoreH.setValue(h)
            if w <= 0 or h <= 0:
                QMessageBox.warning(self, "OCR Test", "ROI is not set.")
                return
            region = {"left": x, "top": y, "width": w, "height": h}
            with mss.mss() as sct:
                raw = sct.grab(region)
                img_bgra = np.array(raw)
                if img_bgra.shape[-1] == 4:
                    img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
                else:
                    img_bgr = img_bgra
            ip = ImageProcessor(
                scale_factor=2.0,
                invert=self.chkOcrStoreInvert.isChecked(),
                threshold_mode="otsu" if self.chkOcrStoreHighContrast.isChecked() else "none",
            )
            val = ip.extract_number(img_bgr, psm_mode=6)
            if val is None:
                QMessageBox.information(self, "OCR Test", "Result: Failed (no number detected)")
            else:
                QMessageBox.information(self, "OCR Test", f"Result: {val}")
        except Exception as e:
            QMessageBox.critical(self, "OCR Test Error", str(e))

    def _browse_file(
        self,
        line_edit: QLineEdit,
        save: bool = False,
        key: str | None = None,
        file_filter: str = "All Files (*)",
    ) -> None:
        start_dir = ""
        current_path = line_edit.text().strip()
        if current_path:
            start_dir = os.path.dirname(current_path)
        elif key:
            last_path = self._get_recent_path(key)
            if last_path:
                start_dir = os.path.dirname(last_path)
        if save:
            fname, _ = QFileDialog.getSaveFileName(self, "Select File", start_dir, file_filter)
        else:
            fname, _ = QFileDialog.getOpenFileName(self, "Select File", start_dir, file_filter)
        if fname:
            line_edit.setText(fname)
            if key:
                self._store_recent_path(key, fname)

    def _on_browse_data_file(self) -> None:
        self._browse_file(
            self.edDataFilePath,
            save=False,
            key="last_data_file_path",
            file_filter="CSV Files (*.csv);;All Files (*)",
        )

    def _on_browse_compare_image_a(self) -> None:
        self._browse_file(
            self.edCompareImageA,
            save=False,
            key="last_compare_image_a_path",
            file_filter="Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )

    def _on_browse_compare_image_b(self) -> None:
        self._browse_file(
            self.edCompareImageB,
            save=False,
            key="last_compare_image_b_path",
            file_filter="Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )

    def _on_browse_run_macro(self):
        start_dir = ""
        current_path = self.edRunMacroPath.text().strip()
        if current_path:
            start_dir = os.path.dirname(current_path)
        else:
            last_path = self._get_recent_path("last_macro_path")
            if last_path:
                start_dir = os.path.dirname(last_path)
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select Macro File",
            start_dir,
            "GameBot Files (*.json *.macro);;All Files (*)",
        )
        if fname:
            self.edRunMacroPath.setText(fname)
            self._store_recent_path("last_macro_path", fname)

    def result_step(self) -> StepData | None:
        # Build step from UI fields regardless of dialog result
        self._step = self._step or StepData(id=str(uuid.uuid4())[:8], name="", type="")
        s = self._step
        s.type = self.cbType.currentData() or self.cbType.currentText()
        s.name = self.edName.text().strip() or s.type
        s.pre_delay_ms = self.spPreDelay.value()
        
        if s.type in ["text", "key", "key_down", "key_up", "key_hold", "keyboard"]:
            s.key_string = self.edKey.text()
            if s.type == "keyboard":
                s.keyboard_mode = self.cbKeyMode.currentText()
        elif s.type == "mouse":
            s.mouse_mode = self.cbMouseMode.currentText() or "click_point"
            if s.mouse_mode == "drag":
                s.drag_from_x = self.spDragFromX.value()
                s.drag_from_y = self.spDragFromY.value()
                s.drag_to_x = self.spDragToX.value()
                s.drag_to_y = self.spDragToY.value()
                s.drag_duration_ms = self.spDragDuration.value()
            elif s.mouse_mode == "scroll":
                s.scroll_dx = self.spScrollDx.value()
                s.scroll_dy = self.spScrollDy.value()
                s.scroll_times = self.spScrollTimes.value()
                s.scroll_interval_ms = self.spScrollInterval.value()
            else:
                s.click_x = self.spClickX.value()
                s.click_y = self.spClickY.value()
        elif s.type == "screen_check":
            s.screen_check_mode = self.cbScreenCheckMode.currentText() or "pixel_check"
            if s.screen_check_mode == "ocr_check_text":
                s.ocr_expected_text = self.edOcrExpected.text()
                s.ocr_whitelist = self.edOcrWhitelist.text()
                s.ocr_preprocess_mode = self.cbOcrPreprocess.currentText()
                s.ocr_scale = float(self.spOcrScale.value())
                s.ocr_invert = self.chkOcrInvert.isChecked()
                s.ocr_target_height = self.spOcrTargetHeight.value()
                s.ocr_lang = self.edOcrLang.text() or "eng"
                s.ocr_use_dynamic_data = self.chkOcrDyn.isChecked()
                s.on_match_goto_id = self.cbOcrGoto.currentData()
                if self._ocr_roi:
                    s.ocr_roi_x, s.ocr_roi_y, s.ocr_roi_w, s.ocr_roi_h = self._ocr_roi
            else:
                s.pixel_x = self.spPixelX.value()
                s.pixel_y = self.spPixelY.value()
                s.pixel_color_hex = self.edPixelHex.text().strip()
                s.pixel_color_tolerance = self.spPixelTol.value()
                s.pixel_success_goto_id = self.cbPixelGoto.currentData()
        elif s.type == "file_action":
            s.file_action_mode = self.cbFileActionMode.currentText() or "load_data_file"
            if s.file_action_mode == "run_macro":
                s.target_macro_path = self.edRunMacroPath.text().strip()
                self._store_recent_path("last_macro_path", s.target_macro_path)
            else:
                s.data_file_path = self.edDataFilePath.text().strip()
                self._store_recent_path("last_data_file_path", s.data_file_path)
        elif s.type == "click_point":
            s.click_x = self.spClickX.value()
            s.click_y = self.spClickY.value()
        elif s.type == "drag":
            s.drag_from_x = self.spDragFromX.value()
            s.drag_from_y = self.spDragFromY.value()
            s.drag_to_x = self.spDragToX.value()
            s.drag_to_y = self.spDragToY.value()
            s.drag_duration_ms = self.spDragDuration.value()
        elif s.type == "scroll":
            s.scroll_dx = self.spScrollDx.value()
            s.scroll_dy = self.spScrollDy.value()
            s.scroll_times = self.spScrollTimes.value()
            s.scroll_interval_ms = self.spScrollInterval.value()
        elif s.type == "wait":
            s.wait_ms = self.spWaitMs.value()
        elif s.type == "pixel_check":
            s.pixel_x = self.spPixelX.value()
            s.pixel_y = self.spPixelY.value()
            s.pixel_color_hex = self.edPixelHex.text().strip()
            s.pixel_color_tolerance = self.spPixelTol.value()
            s.pixel_success_goto_id = self.cbPixelGoto.currentData()
        elif s.type == "start_loop":
            s.loop_count = self.spLoopCount.value()
        elif s.type == "end_loop":
            s.start_loop_id = self.cbLoopStartRef.currentData()
        elif s.type == "screenshot_roi":
            s.screenshot_save_path = self.edShotPath.text().strip()
            if self.edShotRoiDisplay.text():
                s.screenshot_roi_x = self._screenshot_roi[0]
                s.screenshot_roi_y = self._screenshot_roi[1]
                s.screenshot_roi_w = self._screenshot_roi[2]
                s.screenshot_roi_h = self._screenshot_roi[3]
        elif s.type == "compare_images":
            s.image_a_path = self.edCompareImageA.text().strip()
            s.image_b_path = self.edCompareImageB.text().strip()
            s.compare_mode = self.cbCompareMode.currentData() or self.cbCompareMode.currentText().lower()
            s.compare_threshold = float(self.spCompareThreshold.value())
            s.compare_roi_x = self.spCompareRoiX.value()
            s.compare_roi_y = self.spCompareRoiY.value()
            s.compare_roi_w = self.spCompareRoiW.value()
            s.compare_roi_h = self.spCompareRoiH.value()
            s.on_match_goto_id = self.cbCompareMatchGoto.currentData()
            s.branch_on_fail_goto_id = self.cbCompareFailGoto.currentData()
            self._store_recent_path("last_compare_image_a_path", s.image_a_path)
            self._store_recent_path("last_compare_image_b_path", s.image_b_path)
        elif s.type == "load_data_file":
            s.data_file_path = self.edDataFilePath.text().strip()
            self._store_recent_path("last_data_file_path", s.data_file_path)
        elif s.type == "ocr_check_text":
            s.ocr_expected_text = self.edOcrExpected.text()
            s.ocr_whitelist = self.edOcrWhitelist.text()
            s.ocr_preprocess_mode = self.cbOcrPreprocess.currentText()
            s.ocr_scale = float(self.spOcrScale.value())
            s.ocr_invert = self.chkOcrInvert.isChecked()
            s.ocr_target_height = self.spOcrTargetHeight.value()
            s.ocr_lang = self.edOcrLang.text() or "eng"
            s.ocr_use_dynamic_data = self.chkOcrDyn.isChecked()
            s.on_match_goto_id = self.cbOcrGoto.currentData()
            if self._ocr_roi:
                s.ocr_roi_x, s.ocr_roi_y, s.ocr_roi_w, s.ocr_roi_h = self._ocr_roi
        elif s.type == "ocr_jump_if":
            s.ocr_expected_text = ""
            s.ocr_whitelist = None
            s.ocr_preprocess_mode = self.cbOcrJumpPreprocess.currentText()
            s.ocr_scale = float(self.spOcrJumpScale.value())
            s.ocr_invert = self.chkOcrJumpInvert.isChecked()
            s.ocr_target_height = 0
            s.ocr_lang = self.edOcrJumpLang.text() or "eng"
            s.ocr_use_dynamic_data = False
            s.condition_var = None
            if self._ocr_jump_roi:
                s.ocr_roi_x, s.ocr_roi_y, s.ocr_roi_w, s.ocr_roi_h = self._ocr_jump_roi
            s.condition_operator = self.cbOcrJumpOp.currentData() or self.cbOcrJumpOp.currentText()
            val_txt = self.edOcrJumpValue.text().strip()
            try:
                s.condition_value = float(val_txt.replace("%", "")) if val_txt else ""
            except Exception:
                s.condition_value = val_txt
            target_idx = self.cbOcrJumpTarget.currentData()
            if target_idx is None:
                s.target_true_id = None
                s.target_true_index = None
            else:
                s.target_true_index = int(target_idx)
                if 0 <= int(target_idx) < len(self._all_steps):
                    s.target_true_id = getattr(self._all_steps[int(target_idx)], "id", None)
        elif s.type == "comment":
            setattr(s, "comment", self.edComment.text())
        elif s.type == "ocr_store":
            s.ocr_store_var = self.edOcrStoreVar.text().strip() or getattr(s, "ocr_store_var", "")
            s.ocr_invert = self.chkOcrStoreInvert.isChecked()
            s.ocr_preprocess_mode = "otsu" if self.chkOcrStoreHighContrast.isChecked() else "none"
            s.ocr_roi_x = self.spOcrStoreX.value()
            s.ocr_roi_y = self.spOcrStoreY.value()
            s.ocr_roi_w = self.spOcrStoreW.value()
            s.ocr_roi_h = self.spOcrStoreH.value()
            if self._ocr_store_roi:
                s.ocr_roi_x, s.ocr_roi_y, s.ocr_roi_w, s.ocr_roi_h = self._ocr_store_roi
        elif s.type == "jump_if":
            s.condition_var = self.edJumpVar.currentText().strip()
            s.condition_operator = self.cbJumpOp.currentData() or self.cbJumpOp.currentText()
            val_txt = self.edJumpValue.text().strip()
            try:
                s.condition_value = float(val_txt.replace("%", "")) if val_txt else ""
            except Exception:
                s.condition_value = val_txt
            target_idx = self.cbJumpTarget.currentData()
            if target_idx is None:
                s.target_true_id = None
                s.target_true_index = None
            else:
                s.target_true_index = int(target_idx)
                if 0 <= int(target_idx) < len(self._all_steps):
                    s.target_true_id = getattr(self._all_steps[int(target_idx)], "id", None)
        elif s.type == "run_macro":
            s.target_macro_path = self.edRunMacroPath.text().strip()
            self._store_recent_path("last_macro_path", s.target_macro_path)
            
        return s

    def get_step_data(self) -> StepData | None:
        return self.result_step()

class TargetDialog(QDialog):
    def __init__(self, all_steps: list, step_defaults: StepData, target_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Branch Target")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._all_steps = all_steps
        self._step_defaults = step_defaults
        self._target_data = target_data or {}
        self._png_bytes = self._target_data.get('png_bytes')

        form = QFormLayout(self)
        self.edName = QLineEdit(self._target_data.get('name', ''))
        form.addRow("Target Name:", self.edName)

        self.lblPreview = QLabel("No Image")
        self.lblPreview.setAlignment(Qt.AlignCenter)
        self.lblPreview.setFixedSize(128, 128)
        self.lblPreview.setStyleSheet("border: 1px solid gray;")
        if self._png_bytes:
            pm = cvimg_to_qpixmap(decode_png_bytes(self._png_bytes))
            if pm: self.lblPreview.setPixmap(pm.scaled(128, 128, Qt.KeepAspectRatio))
        form.addRow("Template:", self.lblPreview)

        btnLayout = QHBoxLayout()
        self.btnCapture = QPushButton("Capture")
        self.btnCapture.clicked.connect(self._on_capture)
        btnLayout.addWidget(self.btnCapture)
        form.addRow("", btnLayout)

        self.cbGoto = QComboBox()
        self.cbGoto.addItem("Next Step (Default)", None)
        for s in self._all_steps:
            self.cbGoto.addItem(f"[{s.id}] {s.name}", s.id)
        
        goto_id = self._target_data.get('goto_id')
        idx = self.cbGoto.findData(goto_id)
        if idx >= 0: self.cbGoto.setCurrentIndex(idx)
        form.addRow("On Success, Go To:", self.cbGoto)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _on_capture(self):
        # Don't hide self, just overlay ROI selector
        rect, crop, _ = ROISelector.select_from_screen(self)
        if crop is not None:
            self._png_bytes = encode_png_bytes(crop)
            pm = cvimg_to_qpixmap(crop)
            self.lblPreview.setPixmap(pm.scaled(128, 128, Qt.KeepAspectRatio))

    def get_result(self) -> dict | None:
        if self.result() != QDialog.Accepted: return None
        d = self._target_data.copy()
        d['id'] = d.get('id') or str(uuid.uuid4())[:8]
        d['name'] = self.edName.text().strip()
        d['goto_id'] = self.cbGoto.currentData()
        d['png_bytes'] = self._png_bytes
        return d

class BranchStepDialog(QDialog):
    COL_NAME = 0
    COL_GOTO = 1
    COL_IMAGE = 2

    def __init__(self, step: StepData, all_steps: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Branch Step")
        self.resize(820, 640)

        self._step = step
        self._all_steps = [s for s in all_steps if s.id != step.id]
        self._targets = list(step.conditional_targets)

        layout = QVBoxLayout(self)

        # Header (common)
        form = QFormLayout()
        self.edName = QLineEdit(self._step.name)
        form.addRow("Step Name:", self.edName)
        self.spTimeout = QSpinBox()
        self.spTimeout.setRange(0, 999999)
        self.spTimeout.setValue(int(self._step.timeout_ms))
        self.spTimeout.setSuffix(" ms")
        form.addRow("Total Timeout:", self.spTimeout)

        # True/False target selection (common)
        self.cbBranchTrue = QComboBox()
        self.cbBranchTrue.addItem("Next Step (Default)", None)
        self.cbBranchFalse = QComboBox()
        self.cbBranchFalse.addItem("Next Step (Default)", None)
        for s in self._all_steps:
            label = f"[{s.id}] {s.name}"
            self.cbBranchTrue.addItem(label, s.id)
            self.cbBranchFalse.addItem(label, s.id)
        idx_t = self.cbBranchTrue.findData(getattr(self._step, "target_true_id", None) or getattr(self._step, "branch_true_goto_id", None))
        if idx_t >= 0:
            self.cbBranchTrue.setCurrentIndex(idx_t)
        idx_f = self.cbBranchFalse.findData(getattr(self._step, "target_false_id", None) or getattr(self._step, "branch_false_goto_id", None))
        if idx_f >= 0:
            self.cbBranchFalse.setCurrentIndex(idx_f)
        form.addRow("If TRUE, Go To:", self.cbBranchTrue)
        form.addRow("If FALSE, Go To:", self.cbBranchFalse)
        layout.addLayout(form)

        # Tabs: Image / Variable
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- Tab 1: Image Match (existing UI) ---
        imgTab = QWidget()
        imgLayout = QVBoxLayout(imgTab)

        self.tblTargets = QTableWidget()
        self.tblTargets.setColumnCount(3)
        self.tblTargets.setHorizontalHeaderLabels(["Name", "Go To", "Image"])
        self.tblTargets.horizontalHeader().setSectionResizeMode(self.COL_IMAGE, QHeaderView.Stretch)
        self.tblTargets.verticalHeader().setDefaultSectionSize(96)
        self.tblTargets.setIconSize(QSize(96, 96))
        self.tblTargets.setSelectionBehavior(QTableWidget.SelectRows)
        self.tblTargets.setSelectionMode(QTableWidget.SingleSelection)
        self.tblTargets.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tblTargets.customContextMenuRequested.connect(self._show_target_menu)
        self.tblTargets.cellDoubleClicked.connect(lambda r, c: self._on_edit())
        imgLayout.addWidget(self.tblTargets)

        btnLayout = QHBoxLayout()
        btnAdd = QPushButton("Add Target")
        btnEdit = QPushButton("Edit Target")
        btnDel = QPushButton("Delete Target")
        btnLayout.addWidget(btnAdd)
        btnLayout.addWidget(btnEdit)
        btnLayout.addWidget(btnDel)
        imgLayout.addLayout(btnLayout)

        btnAdd.clicked.connect(self._on_add)
        btnEdit.clicked.connect(self._on_edit)
        btnDel.clicked.connect(self._on_del)

        self.tabs.addTab(imgTab, "Image Match")

        # --- Tab 2: Variable Logic ---
        varTab = QWidget()
        varLayout = QVBoxLayout(varTab)

        # Source selector
        srcRow = QHBoxLayout()
        self.rbVarSourceOcr = QRadioButton("화면 글자 읽기 (OCR)")
        self.rbVarSourceVar = QRadioButton("저장된 변수 사용")
        self.rbVarSourceOcr.setChecked(True)
        self.rbVarSourceVar.setChecked(False)
        self.rbVarSourceVar.toggled.connect(lambda checked: self._branch_source_changed(checked, 0))
        self.rbVarSourceOcr.toggled.connect(lambda checked: self._branch_source_changed(checked, 1))
        srcRow.addWidget(self.rbVarSourceOcr)
        srcRow.addWidget(self.rbVarSourceVar)
        varLayout.addLayout(srcRow)

        # Stacked content for source
        self.branchSourceStack = QStackedWidget()

        # Page 1: variable
        pageVar = QWidget()
        pvLayout = QHBoxLayout(pageVar)
        pvLayout.addWidget(QLabel("변수"))
        self.cbVarName = QComboBox()
        self.cbVarName.setEditable(True)
        self.cbVarName.setInsertPolicy(QComboBox.NoInsert)
        self._populate_branch_variables()
        pvLayout.addWidget(self.cbVarName)
        pvLayout.addStretch()
        self.branchSourceStack.addWidget(pageVar)

        # Page 2: OCR
        pageOcr = QWidget()
        poLayout = QGridLayout(pageOcr)
        poLayout.addWidget(QLabel("ROI X"), 0, 0)
        self.spVarOcrX = QSpinBox(); self.spVarOcrX.setRange(0, 99999)
        poLayout.addWidget(self.spVarOcrX, 0, 1)
        poLayout.addWidget(QLabel("ROI Y"), 0, 2)
        self.spVarOcrY = QSpinBox(); self.spVarOcrY.setRange(0, 99999)
        poLayout.addWidget(self.spVarOcrY, 0, 3)
        poLayout.addWidget(QLabel("ROI W"), 1, 0)
        self.spVarOcrW = QSpinBox(); self.spVarOcrW.setRange(0, 99999)
        poLayout.addWidget(self.spVarOcrW, 1, 1)
        poLayout.addWidget(QLabel("ROI H"), 1, 2)
        self.spVarOcrH = QSpinBox(); self.spVarOcrH.setRange(0, 99999)
        poLayout.addWidget(self.spVarOcrH, 1, 3)
        self.btnPickVarOcr = QPushButton("Pick")
        self.btnPickVarOcr.clicked.connect(self._on_pick_branch_ocr)
        poLayout.addWidget(self.btnPickVarOcr, 0, 4, 2, 1)
        self.chkVarOcrInvert = QCheckBox("Invert")
        self.chkVarOcrThresh = QCheckBox("High Contrast")
        poLayout.addWidget(self.chkVarOcrInvert, 2, 0, 1, 2)
        poLayout.addWidget(self.chkVarOcrThresh, 2, 2, 1, 2)
        self.branchSourceStack.addWidget(pageOcr)
        # OCR save option
        poLayout.addWidget(QLabel("값 저장"), 3, 0)
        self.chkSaveToVar = QCheckBox("Also save value to variable")
        self.chkSaveToVar.toggled.connect(lambda checked: self.edSaveVarName.setEnabled(checked))
        poLayout.addWidget(self.chkSaveToVar, 3, 1, 1, 2)
        self.edSaveVarName = QLineEdit()
        self.edSaveVarName.setPlaceholderText("var_name")
        self.edSaveVarName.setEnabled(False)
        poLayout.addWidget(self.edSaveVarName, 3, 3, 1, 2)

        varLayout.addWidget(self.branchSourceStack)

        # Sentence builder (shared)
        row = QHBoxLayout()
        row.addWidget(QLabel("만약 (If)"))
        self.lblSourceName = QLabel("변수")
        row.addWidget(self.lblSourceName)
        self.cbVarOp = QComboBox()
        for text, val in [
            ("초과 (>)", ">"),
            ("미만 (<)", "<"),
            ("같음 (==)", "=="),
            ("다름 (!=)", "!="),
            ("이상 (>=)", ">="),
            ("이하 (<=)", "<="),
        ]:
            self.cbVarOp.addItem(text, val)
        row.addWidget(self.cbVarOp)
        self.edVarValue = QLineEdit()
        self.edVarValue.setPlaceholderText("비교 값 (예: 500)")
        row.addWidget(self.edVarValue)
        row.addWidget(QLabel("이면"))
        varLayout.addLayout(row)

        self.lblVarSummary = QLabel("조건을 설정해주세요.")
        self.lblVarSummary.setStyleSheet("color:#5aa;")
        varLayout.addWidget(self.lblVarSummary)

        self.cbVarName.currentTextChanged.connect(self._update_var_summary)
        self.cbVarOp.currentIndexChanged.connect(self._update_var_summary)
        self.edVarValue.textChanged.connect(self._update_var_summary)
        self.rbVarSourceVar.toggled.connect(self._update_var_summary)
        self.rbVarSourceOcr.toggled.connect(self._update_var_summary)
        # default stack to OCR view when opened
        self._branch_source_changed(True, 1)

        # Restore variable settings
        if getattr(self._step, "branch_mode", "image") == "variable":
            src = getattr(self._step, "branch_value_source", "variable") or "variable"
            if src == "ocr":
                self.rbVarSourceOcr.setChecked(True)
                self.branchSourceStack.setCurrentIndex(1)
                self.spVarOcrX.setValue(getattr(self._step, "ocr_roi_x", 0))
                self.spVarOcrY.setValue(getattr(self._step, "ocr_roi_y", 0))
                self.spVarOcrW.setValue(getattr(self._step, "ocr_roi_w", 0))
                self.spVarOcrH.setValue(getattr(self._step, "ocr_roi_h", 0))
                self.chkVarOcrInvert.setChecked(bool(getattr(self._step, "ocr_invert", False)))
                self.chkVarOcrThresh.setChecked(bool(getattr(self._step, "ocr_preprocess_mode", "") == "otsu"))
                self.chkSaveToVar.setChecked(bool(getattr(self._step, "ocr_save_enabled", False)))
                self.edSaveVarName.setText(getattr(self._step, "ocr_save_var", "") or "")
                self.edSaveVarName.setEnabled(self.chkSaveToVar.isChecked())
                self.lblSourceName.setText("화면 글자")
            else:
                self.rbVarSourceVar.setChecked(True)
                self.branchSourceStack.setCurrentIndex(0)
                self.lblSourceName.setText("변수")
            if getattr(self._step, "branch_var", None):
                self.cbVarName.setCurrentText(str(getattr(self._step, "branch_var")))
            op_val = getattr(self._step, "branch_op", None)
            if op_val:
                idx = self.cbVarOp.findData(str(op_val))
                if idx >= 0:
                    self.cbVarOp.setCurrentIndex(idx)
                else:
                    self.cbVarOp.setCurrentText(str(op_val))
            if getattr(self._step, "branch_value", None) is not None:
                self.edVarValue.setText(str(getattr(self._step, "branch_value")))
            self.tabs.setCurrentIndex(1)
        self._update_var_summary()

        self.tabs.addTab(varTab, "Variable Logic")

        # Fail Action
        formFail = QFormLayout()
        self.cbFailGoto = QComboBox()
        self.cbFailGoto.addItem("Next Step (Default)", None)
        for s in self._all_steps:
            self.cbFailGoto.addItem(f"[{s.id}] {s.name}", s.id)
        idx = self.cbFailGoto.findData(getattr(self._step, "branch_on_fail_goto_id", None))
        if idx >= 0:
            self.cbFailGoto.setCurrentIndex(idx)
        formFail.addRow("On Fail, Go To:", self.cbFailGoto)
        layout.addLayout(formFail)

        # Dialog Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._refresh_list_from_targets()

    def _warn_once(self, key: str, msg: str):
        warned = getattr(self, "_warned_once_keys", None)
        if warned is None:
            warned = set()
            self._warned_once_keys = warned
        if key in warned:
            return
        warned.add(key)
        warn(msg)

    def _populate_branch_variables(self):
        base = ["loop_index", "loop_count"]
        seen = set(base)
        self.cbVarName.blockSignals(True)
        self.cbVarName.clear()
        for v in base:
            self.cbVarName.addItem(v)
        for s in self._all_steps:
            stype = getattr(s, "type", None)
            if stype and str(stype).lower() == "ocr_store":
                var = getattr(s, "ocr_store_var", None)
                if var and var not in seen:
                    seen.add(var)
                    self.cbVarName.addItem(str(var))
        self.cbVarName.blockSignals(False)

    def _update_var_summary(self):
        op_text = self.cbVarOp.currentText()
        val = self.edVarValue.text().strip()
        if self.rbVarSourceOcr.isChecked():
            src_label = "화면 글자"
        else:
            src_label = self.cbVarName.currentText().strip() or "변수"
        self.lblSourceName.setText(src_label)
        if src_label and op_text and val:
            self.lblVarSummary.setText(f"요약: 만약 '{src_label}' {op_text} {val}이면 TRUE로 이동, 아니면 FALSE로 이동.")
        else:
            self.lblVarSummary.setText("조건을 설정해주세요.")

    def _branch_source_changed(self, checked: bool, idx: int):
        """Switch variable/ocr source stack and label."""
        if not checked:
            return
        self.branchSourceStack.setCurrentIndex(idx)
        self.lblSourceName.setText("화면 글자" if idx == 1 else "변수")
        # Toggle save field enabled state when switching source
        self.edSaveVarName.setEnabled(self.chkSaveToVar.isChecked())
        self._update_var_summary()

    def _on_pick_branch_ocr(self):
        """Pick ROI for OCR-based branch."""
        try:
            self.hide()
            rect, _, _ = ROISelector.select_from_screen()
            if rect and not rect.isNull():
                self.spVarOcrX.setValue(rect.x())
                self.spVarOcrY.setValue(rect.y())
                self.spVarOcrW.setValue(rect.width())
                self.spVarOcrH.setValue(rect.height())
        finally:
            self._robust_restore_self()

    def _sort_targets(self, ascending: bool = True):
        try:
            self._targets.sort(key=lambda t: str(t.get("name", "")).lower(), reverse=not ascending)
            self._refresh_list_from_targets()
        except Exception as e:
            self._warn_once("sort_targets", f"Branch target sorting failed: {e}")

    def _refresh_list_from_targets(self):
        self.tblTargets.setRowCount(0)
        for t in self._targets:
            row = self.tblTargets.rowCount()
            self.tblTargets.insertRow(row)
            self.tblTargets.setItem(row, self.COL_NAME, QTableWidgetItem(str(t.get('name', ''))))
            goto_id = t.get('goto_id')
            goto_name = "Next Step"
            if goto_id:
                for s in self._all_steps:
                    if s.id == goto_id:
                        goto_name = s.name
                        break
            self.tblTargets.setItem(row, self.COL_GOTO, QTableWidgetItem(goto_name))
            if t.get('png_bytes'):
                pm = cvimg_to_qpixmap(decode_png_bytes(t['png_bytes']))
                lbl = QLabel()
                if pm:
                    row_h = max(64, self.tblTargets.verticalHeader().defaultSectionSize() - 4)
                    lbl.setPixmap(pm.scaled(row_h, row_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                lbl.setAlignment(Qt.AlignCenter)
                self.tblTargets.setCellWidget(row, self.COL_IMAGE, lbl)
            else:
                self.tblTargets.setItem(row, self.COL_IMAGE, QTableWidgetItem("No Image"))

    def _on_add(self):
        default_target = {
            "id": str(uuid.uuid4())[:8],
            "name": f"Target {len(self._targets)+1}",
            "goto_id": None,
            "png_bytes": None,
            "threshold": 0.85,
        }
        dlg = TargetDialog(self._all_steps, self._step, default_target, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            new_target = dlg.get_result()
            if new_target:
                self._targets.append(new_target)
                self._refresh_list_from_targets()

    def _on_edit(self):
        row = self.tblTargets.currentRow()
        if row < 0: return
        current_target = self._targets[row]
        dlg = TargetDialog(self._all_steps, self._step, current_target, self)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_result()
            if updated:
                self._targets[row] = updated
                self._refresh_list_from_targets()

    def _on_del(self):
        row = self.tblTargets.currentRow()
        if row < 0: return
        del self._targets[row]
        self._refresh_list_from_targets()

    def accept(self):
        self._step.name = self.edName.text().strip()
        self._step.timeout_ms = self.spTimeout.value()
        self._step.branch_on_fail_goto_id = self.cbFailGoto.currentData()
        # true/false goto
        true_id = self.cbBranchTrue.currentData()
        false_id = self.cbBranchFalse.currentData()
        self._step.branch_true_goto_id = true_id
        self._step.branch_false_goto_id = false_id
        self._step.target_true_id = true_id
        self._step.target_false_id = false_id
        # mode-specific
        if self.tabs.currentIndex() == 0:
            self._step.branch_mode = "image"
            self._step.conditional_targets = self._targets
        else:
            self._step.branch_mode = "variable"
            self._step.branch_var = self.cbVarName.currentText().strip()
            self._step.branch_op = self.cbVarOp.currentData() or self.cbVarOp.currentText()
            val_txt = self.edVarValue.text().strip()
            try:
                self._step.branch_value = float(val_txt) if val_txt else ""
            except Exception:
                self._step.branch_value = val_txt
            if self.rbVarSourceOcr.isChecked():
                self._step.branch_value_source = "ocr"
                self._step.ocr_roi_x = self.spVarOcrX.value()
                self._step.ocr_roi_y = self.spVarOcrY.value()
                self._step.ocr_roi_w = self.spVarOcrW.value()
                self._step.ocr_roi_h = self.spVarOcrH.value()
                self._step.ocr_invert = self.chkVarOcrInvert.isChecked()
                self._step.ocr_preprocess_mode = "otsu" if self.chkVarOcrThresh.isChecked() else "none"
                self._step.ocr_save_enabled = self.chkSaveToVar.isChecked()
                self._step.ocr_save_var = self.edSaveVarName.text().strip()
            else:
                self._step.branch_value_source = "variable"
                self._step.ocr_save_enabled = False
                self._step.ocr_save_var = None
        super().accept()

    def _on_rename(self):
        row = self.tblTargets.currentRow()
        if row < 0: return
        old = str(self._targets[row].get('name', ''))
        new_text, ok = QInputDialog.getText(self, "Rename Target", "Enter new name:", text=old)
        if not ok: return
        name = str(new_text).strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Name cannot be empty.")
            return
        self._targets[row]['name'] = name
        self._refresh_list_from_targets()

    def _move_selected(self, delta: int):
        row = self.tblTargets.currentRow()
        if row < 0: return
        new_row = row + int(delta)
        if not (0 <= new_row < len(self._targets)): return
        self._targets[row], self._targets[new_row] = self._targets[new_row], self._targets[row]
        self._refresh_list_from_targets()
        try:
            self.tblTargets.setCurrentCell(new_row, 0)
        except Exception as e:
            self._warn_once("move_selected_focus", f"Failed to move branch target selection focus: {e}")

    def get_step_data(self):
        return self._step

    def _show_target_menu(self, pos):
        it = self.tblTargets.itemAt(pos)
        if it is None:
            return
        menu = QMenu(self)
        aRename = menu.addAction("Rename")
        aUp = menu.addAction("Move Up")
        aDown = menu.addAction("Move Down")
        aRename.triggered.connect(self._on_rename)
        aUp.triggered.connect(lambda: self._move_selected(-1))
        aDown.triggered.connect(lambda: self._move_selected(1))
        menu.exec_(self.tblTargets.viewport().mapToGlobal(pos))

class RecordingSettingsDialog(QDialog):
    def __init__(self, parent, vals, perf_recording: bool = False, perf_level: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Recording Settings")
        self.setFixedWidth(450)

        (typed_gap_ms, click_merge_ms, click_radius_px,
         scroll_flush_ms, scroll_scale_dx, scroll_scale_dy) = vals

        form = QFormLayout(self)

        perf_group = QGroupBox("Recording Performance")
        perf_layout = QFormLayout()
        perf_layout.setContentsMargins(10, 14, 10, 10)
        perf_layout.setVerticalSpacing(8)
        self.chkPerfRecording = QCheckBox("High Performance Recording")
        self.chkPerfRecording.setChecked(bool(perf_recording))
        self.cbPerfLevel = QComboBox()
        self.cbPerfLevel.addItem("Performance Level 1", 1)
        self.cbPerfLevel.addItem("Performance Level 2", 2)
        self.cbPerfLevel.addItem("Performance Level 3", 3)
        self.cbPerfLevel.setMinimumHeight(30)
        self.cbPerfLevel.setStyleSheet("padding: 4px 6px;")
        idx = self.cbPerfLevel.findData(int(perf_level))
        if idx >= 0:
            self.cbPerfLevel.setCurrentIndex(idx)
        perf_layout.addRow(self.chkPerfRecording)
        perf_layout.addRow("Performance Level", self.cbPerfLevel)
        perf_group.setLayout(perf_layout)
        form.addRow(perf_group)

        self.lblPerfNote = QLabel("재생(Playback) 성능 설정은 Settings 탭에서 조정합니다.")
        self.lblPerfNote.setStyleSheet("color: #888; font-size: 11px;")
        self.lblPerfNote.setWordWrap(True)
        form.addRow(self.lblPerfNote)

        self.lblPerfHelp = QLabel(
            "이 창의 프리셋은 녹화 이벤트 합치기/플러시 기준만 바꿉니다.\n"
            "고성능 녹화/레벨은 녹화 수집 속도(버퍼/이동 필터)에만 영향합니다."
        )
        self.lblPerfHelp.setStyleSheet("color: #888; font-size: 11px;")
        self.lblPerfHelp.setWordWrap(True)
        form.addRow(self.lblPerfHelp)

        self.spTypedGap = QSpinBox()
        self.spTypedGap.setRange(50, 5000)
        self.spTypedGap.setValue(int(typed_gap_ms))
        self.spTypedGap.setSuffix(" ms")
        
        self.spClickMerge = QSpinBox()
        self.spClickMerge.setRange(50, 5000)
        self.spClickMerge.setValue(int(click_merge_ms))
        self.spClickMerge.setSuffix(" ms")
        
        self.spClickRadius = QSpinBox()
        self.spClickRadius.setRange(0, 50)
        self.spClickRadius.setValue(int(click_radius_px))
        self.spClickRadius.setSuffix(" px")
        
        self.spScrollFlush = QSpinBox()
        self.spScrollFlush.setRange(50, 5000)
        self.spScrollFlush.setValue(int(scroll_flush_ms))
        self.spScrollFlush.setSuffix(" ms")
        
        self.dScrollDx = QDoubleSpinBox()
        self.dScrollDx.setRange(0.1, 1000.0)
        self.dScrollDx.setValue(float(scroll_scale_dx))
        
        self.dScrollDy = QDoubleSpinBox()
        self.dScrollDy.setRange(0.1, 1000.0)
        self.dScrollDy.setValue(float(scroll_scale_dy))

        form.addRow("Typing Gap", self.spTypedGap)
        form.addRow("Click Merge Time", self.spClickMerge)
        form.addRow("Click Merge Radius", self.spClickRadius)
        form.addRow("Scroll Flush Time", self.spScrollFlush)
        form.addRow("Scroll Scale X", self.dScrollDx)
        form.addRow("Scroll Scale Y", self.dScrollDy)
        
        presetGroup = QGroupBox("Presets")
        presetLayout = QHBoxLayout()
        btnPresetPerf = QPushButton("Performance")
        btnPresetNormal = QPushButton("Normal")
        presetLayout.addWidget(btnPresetPerf)
        presetLayout.addWidget(btnPresetNormal)
        presetGroup.setLayout(presetLayout)
        
        form.addRow(presetGroup)

        self.lblSummary = QLabel()
        self.lblSummary.setWordWrap(True)
        self.lblSummary.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow(self.lblSummary)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        form.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        btnPresetPerf.clicked.connect(lambda: self._apply_preset("perf"))
        btnPresetNormal.clicked.connect(lambda: self._apply_preset("normal"))
        self.spTypedGap.valueChanged.connect(self._update_summary)
        self.spClickMerge.valueChanged.connect(self._update_summary)
        self.spClickRadius.valueChanged.connect(self._update_summary)
        self.spScrollFlush.valueChanged.connect(self._update_summary)
        self.dScrollDx.valueChanged.connect(self._update_summary)
        self.dScrollDy.valueChanged.connect(self._update_summary)
        self.chkPerfRecording.toggled.connect(self._update_summary)
        self.cbPerfLevel.currentIndexChanged.connect(self._update_summary)
        self._update_summary()

    def _warn_once(self, key: str, msg: str):
        warned = getattr(self, "_warned_once_keys", None)
        if warned is None:
            warned = set()
            self._warned_once_keys = warned
        if key in warned:
            return
        warned.add(key)
        warn(msg)

    def values(self):
        return (self.spTypedGap.value(), self.spClickMerge.value(), self.spClickRadius.value(),
                self.spScrollFlush.value(), self.dScrollDx.value(), self.dScrollDy.value())

    def perf_values(self):
        level = self.cbPerfLevel.currentData()
        if level is None:
            try:
                level = int(self.cbPerfLevel.currentText().strip()[-1])
            except Exception:
                level = 1
        return (bool(self.chkPerfRecording.isChecked()), int(level or 1))

    def _summary_text(self) -> str:
        perf_on = "ON" if self.chkPerfRecording.isChecked() else "OFF"
        perf_level = self.cbPerfLevel.currentData() or 1
        return (
            "현재: "
            f"입력 간격={self.spTypedGap.value()} ms, "
            f"클릭 합치기={self.spClickMerge.value()} ms, "
            f"클릭 반경={self.spClickRadius.value()} px, "
            f"스크롤 플러시={self.spScrollFlush.value()} ms, "
            f"스크롤 스케일=({self.dScrollDx.value():.1f},{self.dScrollDy.value():.1f}), "
            f"고성능 녹화={perf_on}, 레벨={perf_level}"
        )

    def _update_summary(self):
        try:
            self.lblSummary.setText(self._summary_text())
        except Exception as e:
            self._warn_once("recording_settings_summary", f"Recording settings summary update failed: {e}")

    def _apply_preset(self, preset_name):
        if preset_name == "perf":
            self.spTypedGap.setValue(250)
            self.spClickMerge.setValue(150)
            self.spClickRadius.setValue(5)
            self.spScrollFlush.setValue(100)
        elif preset_name == "normal":
            self.spTypedGap.setValue(500)
            self.spClickMerge.setValue(350)
            self.spClickRadius.setValue(3)
            self.spScrollFlush.setValue(180)
        self._update_summary()

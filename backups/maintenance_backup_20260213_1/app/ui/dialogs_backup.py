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
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QGridLayout, QApplication, QShortcut
)
from PyQt5.QtCore import Qt, QTimer, QEventLoop, QSettings, QSize
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence

from ..core.models import StepData
from ..utils.common import (
    cvimg_to_qpixmap, encode_png_bytes, decode_png_bytes, 
    hk_normalize, hk_pretty, err
)
from ..utils.matcher import Matcher
from .selectors import ROISelector, safe_select_point

class BaseDialog(QDialog):
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
            except Exception:
                pass
            try:
                self.setEnabled(True)
            except Exception:
                pass
            # 3) 최전면으로 띄우기
            self.show()
            self.raise_()
            self.activateWindow()
            try:
                QApplication.setActiveWindow(self)
            except Exception:
                pass
            # 4) 모달/포커스 다시 띄우기
            try:
                self.setWindowModality(Qt.WindowModal)
            except Exception:
                pass
            # 5) 이벤트 루프 처리 및 UI 반영
            try:
                QApplication.processEvents(QEventLoop.AllEvents, 50)
            except Exception:
                pass
            # 6) 타이머를 이용해 한 번 더 확실하게 띄우기
            try:
                QTimer.singleShot(0, self.raise_)
                QTimer.singleShot(0, self.activateWindow)
            except Exception:
                pass
        except Exception:
            pass

class ImageStepDialog(BaseDialog):
    def __init__(self, step: StepData, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Step")
        self.resize(650, 700)
        self._step = step

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
        self.cbAction.addItems(["Click", "Move Only", "None (Just Find)"])
        # TODO: Map step action to combo index if needed, currently just default
        formLayout1.addRow("Action", self.cbAction)
        
        self.spTimeout = QSpinBox()
        self.spTimeout.setRange(0, 999999)
        self.spTimeout.setValue(int(step.timeout_ms))
        self.spTimeout.setSuffix(" ms")
        formLayout1.addRow("Timeout", self.spTimeout)
        
        self.spThreshold = QDoubleSpinBox()
        self.spThreshold.setRange(0.1, 1.0)
        self.spThreshold.setSingleStep(0.01)
        self.spThreshold.setValue(step.threshold)
        formLayout1.addRow("Confidence Threshold", self.spThreshold)

        tabWidget.addTab(basicTab, "Basic")

        # --- 탭 2: 고급 설정 ---
        advTab = QWidget()
        formLayout2 = QFormLayout(advTab)
        
        self.cbClickBtn = QComboBox()
        self.cbClickBtn.addItems(["left", "right", "middle", "double"])
        idx = self.cbClickBtn.findText(step.click_btn)
        if idx >= 0: self.cbClickBtn.setCurrentIndex(idx)
        formLayout2.addRow("Mouse Button", self.cbClickBtn)
        
        self.spClickOffset = QSpinBox()
        self.spClickOffset.setRange(-9999, 9999)
        # TODO: Add offset X/Y fields if needed, simplified for now
        
        self.spPreDelay = QSpinBox()
        self.spPreDelay.setRange(0, 999999)
        self.spPreDelay.setSingleStep(100)
        self.spPreDelay.setValue(step.pre_delay_ms)
        self.spPreDelay.setSuffix(" ms")
        formLayout2.addRow("Pre-delay", self.spPreDelay)

        tabWidget.addTab(advTab, "Advanced")

        # --- 탭 3: 매칭 설정 ---
        matchingTab = QWidget()
        formLayout3 = QFormLayout(matchingTab)

        self.chkGray = QCheckBox("Use grayscale")
        self.chkGray.setChecked(step.pre_gray)
        self.spBlur = QSpinBox()
        self.spBlur.setRange(0, 20)
        self.spBlur.setValue(int(step.pre_blur_ksize))
        
        formLayout3.addRow(self.chkGray)
        formLayout3.addRow("Blur Kernel Size", self.spBlur)
        
        self.btnTest = QPushButton("Test Match on Screen")
        self.lblTest = QLabel("Result: -")
        formLayout3.addRow(self.btnTest, self.lblTest)
        
        tabWidget.addTab(matchingTab, "Matching")

        # Buttons
        btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btnBox.accepted.connect(self.accept)
        btnBox.rejected.connect(self.reject)
        mainLayout.addWidget(btnBox)

        self.btnCapture.clicked.connect(self._on_capture)
        self.btnLoad.clicked.connect(self._on_load)
        self.btnTest.clicked.connect(self._on_test_match)

    def _on_capture(self):
        # Don't hide self, just overlay ROI selector
        rect, crop, _ = ROISelector.select_from_screen(self)
        if crop is not None:
            self._step.png_bytes = encode_png_bytes(crop)
            self._step._tpl_bgr = crop
            self._step._tpl_cache = {} # Clear cache
            pm = cvimg_to_qpixmap(crop)
            self.lblPreview.setPixmap(pm.scaled(200, 150, Qt.KeepAspectRatio))

    def _on_load(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load Image", "", "Images (*.png *.jpg *.bmp)")
        if fname:
            with open(fname, "rb") as f:
                data = f.read()
            self._step.png_bytes = data
            self._step._tpl_bgr = decode_png_bytes(data)
            self._step._tpl_cache = {} # Clear cache
            pm = cvimg_to_qpixmap(self._step._tpl_bgr)
            if pm: self.lblPreview.setPixmap(pm.scaled(200, 150, Qt.KeepAspectRatio))

    def _on_test_match(self):
        try:
            with mss.mss() as sct:
                mon = sct.monitors[0]
                frame = np.array(sct.grab(mon), dtype=np.uint8)[:, :, :3].copy()
            
            fake = StepData(**asdict(self._step))
            fake.pre_gray = self.chkGray.isChecked()
            fake.pre_blur_ksize = int(self.spBlur.value())
            
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
        self._step.pre_delay_ms = self.spPreDelay.value()
        self._step.pre_gray = self.chkGray.isChecked()
        self._step.pre_blur_ksize = self.spBlur.value()
        self._step.click_btn = self.cbClickBtn.currentText()
        super().accept()

class NotImageDialog(BaseDialog):
    def __init__(self, step: StepData | None, all_steps: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Step")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModal)

        self._step = step
        self._all_steps = all_steps
        
        # 임시 ROI 저장을 위한 변수
        if step and step.type == 'screenshot_roi':
            self._screenshot_roi = (step.screenshot_roi_x, step.screenshot_roi_y, step.screenshot_roi_w, step.screenshot_roi_h)
        else:
            self._screenshot_roi = (0,0,0,0)
            
        if step and step.type == 'ocr_check_text':
            self._ocr_roi = (step.ocr_roi_x, step.ocr_roi_y, step.ocr_roi_w, step.ocr_roi_h)
        else:
            self._ocr_roi = (0,0,0,0)

        layout = QVBoxLayout(self)
        
        # Type Selection
        typeLayout = QHBoxLayout()
        typeLayout.addWidget(QLabel("Action Type:"))
        self.cbType = QComboBox()
        self.cbType.addItems([
            "text", "key", "key_down", "key_up", "key_hold", 
            "click_point", "drag", "scroll", 
            "pixel_check", "start_loop", "end_loop",
            "screenshot_roi", "ocr_check_text", "load_data_file",
            "comment"
        ])
        typeLayout.addWidget(self.cbType)
        layout.addLayout(typeLayout)

        # Common Fields
        form = QFormLayout()
        self.edName = QLineEdit(step.name if step else "")
        form.addRow("Name:", self.edName)
        self.spPreDelay = QSpinBox()
        self.spPreDelay.setRange(0, 999999)
        self.spPreDelay.setValue(step.pre_delay_ms if step else 0)
        self.spPreDelay.setSuffix(" ms")
        form.addRow("Pre-delay:", self.spPreDelay)
        layout.addLayout(form)

        # Dynamic Content Area
        self.contentWidget = QWidget()
        self.contentLayout = QVBoxLayout(self.contentWidget)
        layout.addWidget(self.contentWidget)
        
        # Setup specific groups (simplified for brevity, full implementation would add all fields)
        self._init_groups()
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.cbType.currentTextChanged.connect(self._refresh_visibility)
        if step:
            idx = self.cbType.findText(step.type)
            if idx >= 0: self.cbType.setCurrentIndex(idx)
        else:
            # 기본 액션: text 선택
            self.cbType.setCurrentIndex(0)
        self._refresh_visibility()

    def _init_groups(self):
        # Key Group
        self.groupKey = QGroupBox("Keyboard")
        keyLayout = QFormLayout(self.groupKey)
        self.edKey = QLineEdit(self._step.key_string if self._step else "")
        keyLayout.addRow("Key String:", self.edKey)
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
        
        # Load Data Group
        self.groupLoadData = QGroupBox("Load Data File")
        ldLayout = QFormLayout(self.groupLoadData)
        self.edDataFilePath = QLineEdit(self._step.data_file_path if self._step else "")
        ldLayout.addRow("File Path:", self.edDataFilePath)
        self.contentLayout.addWidget(self.groupLoadData)

        # Add other groups as needed...

    def _refresh_visibility(self):
        t = self.cbType.currentText()
        self.groupKey.setVisible(t in ["text", "key", "key_down", "key_up", "key_hold"])
        self.groupClick.setVisible(t == "click_point")
        self.groupLoadData.setVisible(t == "load_data_file")
        # Handle other visibilities...

    def _on_pick_click(self):
        self.hide()
        try:
            pt = safe_select_point()
            if pt:
                self.spClickX.setValue(pt.x())
                self.spClickY.setValue(pt.y())
        finally:
            self._robust_restore_self()

    def result_step(self) -> StepData | None:
        if self.result() != QDialog.Accepted: return None
        s = self._step or StepData(id=str(uuid.uuid4())[:8], name="", type="")
        s.type = self.cbType.currentText()
        s.name = self.edName.text().strip() or s.type
        s.pre_delay_ms = self.spPreDelay.value()
        
        if s.type in ["text", "key", "key_down", "key_up", "key_hold"]:
            s.key_string = self.edKey.text()
        elif s.type == "click_point":
            s.click_x = self.spClickX.value()
            s.click_y = self.spClickY.value()
        elif s.type == "load_data_file":
            s.data_file_path = self.edDataFilePath.text().strip()
            
        return s

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
        self.resize(800, 600)

        self._step = step
        self._all_steps = [s for s in all_steps if s.id != step.id]
        self._targets = list(step.conditional_targets)
        
        layout = QVBoxLayout(self)
        
        # Header
        form = QFormLayout()
        self.edName = QLineEdit(self._step.name)
        form.addRow("Step Name:", self.edName)
        self.spTimeout = QSpinBox()
        self.spTimeout.setRange(0, 999999)
        self.spTimeout.setValue(int(self._step.timeout_ms))
        self.spTimeout.setSuffix(" ms")
        form.addRow("Total Timeout:", self.spTimeout)
        layout.addLayout(form)

        # Targets Table
        self.tblTargets = QTableWidget()
        self.tblTargets.setColumnCount(3)
        self.tblTargets.setHorizontalHeaderLabels(["Name", "Go To", "Image"])
        self.tblTargets.horizontalHeader().setSectionResizeMode(self.COL_IMAGE, QHeaderView.Stretch)
        # Make image cells taller and icons larger for better preview
        self.tblTargets.verticalHeader().setDefaultSectionSize(96)
        self.tblTargets.setIconSize(QSize(96, 96))
        self.tblTargets.setSelectionBehavior(QTableWidget.SelectRows)
        self.tblTargets.setSelectionMode(QTableWidget.SingleSelection)
        self.tblTargets.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tblTargets.customContextMenuRequested.connect(self._show_target_menu)
        self.tblTargets.cellDoubleClicked.connect(lambda r, c: self._on_edit())
        layout.addWidget(self.tblTargets)

        # Buttons
        btnLayout = QHBoxLayout()
        btnAdd = QPushButton("Add Target")
        btnEdit = QPushButton("Edit Target")
        btnDel = QPushButton("Delete Target")
        btnLayout.addWidget(btnAdd)
        btnLayout.addWidget(btnEdit)
        btnLayout.addWidget(btnDel)
        layout.addLayout(btnLayout)

        # Fail Action
        formFail = QFormLayout()
        self.cbFailGoto = QComboBox()
        self.cbFailGoto.addItem("Next Step (Default)", None)
        for s in self._all_steps:
            self.cbFailGoto.addItem(f"[{s.id}] {s.name}", s.id)
        idx = self.cbFailGoto.findData(self._step.branch_on_fail_goto_id)
        if idx >= 0: self.cbFailGoto.setCurrentIndex(idx)
        formFail.addRow("On Fail, Go To:", self.cbFailGoto)
        layout.addLayout(formFail)

        # Dialog Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        btnAdd.clicked.connect(self._on_add)
        btnEdit.clicked.connect(self._on_edit)
        btnDel.clicked.connect(self._on_del)
        
        self._refresh_list_from_targets()

    def _refresh_list_from_targets(self):
        self.tblTargets.setRowCount(0)
        for t in self._targets:
            row = self.tblTargets.rowCount()
            self.tblTargets.insertRow(row)
            self.tblTargets.setItem(row, self.COL_NAME, QTableWidgetItem(str(t.get('name', ''))))
            
            goto_id = t.get('goto_id')
            goto_name = "Next Step"
            if goto_id:
                # Find name
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
        # 기본 이름/ID가 채워진 타깃 생성
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
        self._step.conditional_targets = self._targets
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
        except Exception:
            pass

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
    def __init__(self, parent, vals):
        super().__init__(parent)
        self.setWindowTitle("Recording Settings")
        self.setFixedWidth(450)

        (typed_gap_ms, click_merge_ms, click_radius_px,
         scroll_flush_ms, scroll_scale_dx, scroll_scale_dy) = vals

        form = QFormLayout(self)

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

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        form.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        btnPresetPerf.clicked.connect(lambda: self._apply_preset("perf"))
        btnPresetNormal.clicked.connect(lambda: self._apply_preset("normal"))

    def values(self):
        return (self.spTypedGap.value(), self.spClickMerge.value(), self.spClickRadius.value(),
                self.spScrollFlush.value(), self.dScrollDx.value(), self.dScrollDy.value())

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


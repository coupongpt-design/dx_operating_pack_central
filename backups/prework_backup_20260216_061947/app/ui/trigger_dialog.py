import os
import uuid
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QGroupBox, QFormLayout, QLineEdit, QComboBox, QSpinBox, 
    QFileDialog, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ..core.models import TriggerData, StepData
from .dialogs import ImageStepDialog
from ..utils.common import decode_png_bytes
from ..ui.styles import DarkTheme

class TriggerEditDialog(QDialog):
    def __init__(self, trigger: TriggerData, parent=None):
        super().__init__(parent)
        self.setWindowTitle("트리거 편집 (Edit Trigger)")
        self.resize(500, 400)
        self.setStyleSheet(DarkTheme.get_stylesheet())
        
        # Deep copy trigger or work on it directly?
        # Usually dialogs work on a copy or modify directly if accepted.
        # Here we assume 'trigger' is the object to modify.
        self.trigger = trigger
        
        # Ensure condition step exists
        if not self.trigger.condition_step:
            self.trigger.condition_step = StepData(id=str(uuid.uuid4())[:8], name="Condition", type="image_click")
            
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Name & Enable
        form_layout = QFormLayout()
        self.edt_name = QLineEdit(self.trigger.name)
        self.chk_enabled = QCheckBox("활성화 (Enabled)")
        self.chk_enabled.setChecked(self.trigger.enabled)
        form_layout.addRow("이름:", self.edt_name)
        form_layout.addRow("", self.chk_enabled)
        layout.addLayout(form_layout)
        
        # Condition Group
        grp_cond = QGroupBox("조건 (When)")
        cond_layout = QVBoxLayout(grp_cond)
        
        self.lbl_preview = QLabel("이미지 없음")
        self.lbl_preview.setMinimumHeight(120)
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background:#333; border:1px solid #555;")
        
        self.btn_edit_cond = QPushButton("조건 이미지/옵션 설정 (Edit Condition)")
        self.btn_edit_cond.clicked.connect(self._edit_condition)
        
        cond_layout.addWidget(self.lbl_preview)
        cond_layout.addWidget(self.btn_edit_cond)
        layout.addWidget(grp_cond)
        
        # Action Group
        grp_act = QGroupBox("행동 (Then)")
        act_layout = QFormLayout(grp_act)
        
        self.cmb_action = QComboBox()
        self.cmb_action.addItems(["run_macro", "stop", "notification"])
        self.cmb_action.setCurrentText(self.trigger.action_type)
        self.cmb_action.currentIndexChanged.connect(self._update_action_ui)
        
        self.btn_macro_file = QPushButton("매크로 파일 선택")
        self.btn_macro_file.clicked.connect(self._pick_macro_file)
        self.lbl_macro_file = QLabel(self.trigger.action_value if self.trigger.action_type == "run_macro" else "")
        self.edt_msg = QLineEdit(self.trigger.action_value if self.trigger.action_type == "notification" else "")
        
        act_layout.addRow("액션 타입:", self.cmb_action)
        act_layout.addRow("매크로:", self.btn_macro_file)
        act_layout.addRow("", self.lbl_macro_file)
        act_layout.addRow("메시지:", self.edt_msg)
        layout.addWidget(grp_act)
        
        # Settings
        grp_set = QGroupBox("설정")
        set_layout = QFormLayout(grp_set)
        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(100, 3600000)
        self.spin_cooldown.setValue(self.trigger.cooldown_ms)
        self.spin_cooldown.setSuffix(" ms")
        set_layout.addRow("쿨타임:", self.spin_cooldown)
        layout.addWidget(grp_set)
        
        # Buttons
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("확인")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)
        
        self._update_preview()
        self._update_action_ui()

    def _edit_condition(self):
        # Reuse ImageStepDialog!
        # We pass the condition_step to it.
        dlg = ImageStepDialog(self.trigger.condition_step, self)
        if dlg.exec_() == QDialog.Accepted:
            # The dialog updates the step object in place.
            self._update_preview()

    def _update_preview(self):
        s = self.trigger.condition_step
        if s.png_bytes:
            pm = decode_png_bytes(s.png_bytes)
            if pm is not None:
                import cv2
                rgb = cv2.cvtColor(pm, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                from PyQt5.QtGui import QImage
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                pix = QPixmap.fromImage(qimg)
                self.lbl_preview.setPixmap(pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio))
                self.lbl_preview.setText("")
            else:
                self.lbl_preview.setText("이미지 디코딩 실패")
        else:
            self.lbl_preview.setText("이미지 없음 (클릭하여 설정)")

    def _update_action_ui(self):
        act = self.cmb_action.currentText()
        is_macro = act == "run_macro"
        is_noti = act == "notification"
        
        self.btn_macro_file.setVisible(is_macro)
        self.lbl_macro_file.setVisible(is_macro)
        self.edt_msg.setVisible(is_noti)

    def _pick_macro_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "매크로 파일 선택", "", "Macro (*.macro)")
        if fname:
            self.lbl_macro_file.setText(fname)

    def accept(self):
        # Save values back to trigger object
        self.trigger.name = self.edt_name.text()
        self.trigger.enabled = self.chk_enabled.isChecked()
        self.trigger.action_type = self.cmb_action.currentText()
        
        if self.trigger.action_type == "run_macro":
            self.trigger.action_value = self.lbl_macro_file.text()
        elif self.trigger.action_type == "notification":
            self.trigger.action_value = self.edt_msg.text()
        else:
            self.trigger.action_value = ""
            
        self.trigger.cooldown_ms = self.spin_cooldown.value()
        
        super().accept()

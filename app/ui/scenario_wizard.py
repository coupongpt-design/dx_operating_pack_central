from __future__ import annotations

import copy
import uuid
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.scenario_wizard import (
    create_user_template_from_base,
    delete_user_template,
    get_template,
    is_user_template,
    list_templates,
    plan_template,
    summarize_steps,
    upsert_user_template,
)
from ..core.scenario_wizard_flow import (
    delete_step_with_lazy_repair,
    find_references_in_blueprint,
    validate_custom_flow_blueprint,
)
from ..io.data_loader import inspect_data_file


def _difficulty_label(raw: str | None) -> str:
    norm = str(raw or "").strip().lower()
    mapping = {
        "beginner": "초급",
        "intermediate": "중급",
        "advanced": "고급",
    }
    return mapping.get(norm, norm or "미정")


def _template_source_label(template: dict[str, Any]) -> str:
    return "사용자" if is_user_template(template) else "기본"


def _flow_step_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("step_uuid") or "").strip()


def _new_flow_step_id(existing_ids: set[str]) -> str:
    while True:
        cand = str(uuid.uuid4())[:8]
        if cand not in existing_ids:
            return cand


FLOW_REFERENCE_FIELDS = {
    "target_true_id",
    "target_false_id",
    "branch_on_fail_goto_id",
    "on_match_goto_id",
    "pixel_success_goto_id",
    "start_loop_id",
    "jump_to_step_id",
}

FLOW_STEP_SCHEMAS: dict[str, dict[str, Any]] = {
    "comment": {
        "label": "메모",
        "fields": [
            {"name": "comment", "label": "메모", "type": "multiline", "default": ""},
        ],
    },
    "wait": {
        "label": "대기",
        "fields": [
            {"name": "wait_ms", "label": "대기(ms)", "type": "int", "default": 300, "min": 0, "max": 3600000},
        ],
    },
    "click_point": {
        "label": "좌표 클릭",
        "fields": [
            {"name": "click_x", "label": "X", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {"name": "click_y", "label": "Y", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {
                "name": "click_btn",
                "label": "버튼",
                "type": "choice",
                "default": "left",
                "options": [("왼쪽", "left"), ("오른쪽", "right"), ("가운데", "middle")],
            },
            {"name": "click_double", "label": "더블 클릭", "type": "bool", "default": False},
        ],
    },
    "image_click": {
        "label": "이미지 찾고 클릭",
        "fields": [
            {"name": "anchor_image_path", "label": "앵커 이미지 경로", "type": "str", "default": ""},
            {"name": "threshold", "label": "매칭 임계값", "type": "float", "default": 0.85, "min": 0.1, "max": 1.0},
            {"name": "timeout_ms", "label": "타임아웃(ms)", "type": "int", "default": 5000, "min": 0, "max": 3600000},
            {"name": "poll_ms", "label": "폴링 간격(ms)", "type": "int", "default": 100, "min": 10, "max": 10000},
            {
                "name": "click_anchor",
                "label": "기준 앵커",
                "type": "choice",
                "default": "center",
                "options": [
                    ("center", "center"),
                    ("top-left", "top-left"),
                    ("top-right", "top-right"),
                    ("bottom-left", "bottom-left"),
                    ("bottom-right", "bottom-right"),
                ],
            },
            {"name": "click_offset_x", "label": "오프셋 X", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {"name": "click_offset_y", "label": "오프셋 Y", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {
                "name": "image_action",
                "label": "동작",
                "type": "choice",
                "default": "click",
                "options": [("click", "click"), ("move", "move"), ("none", "none")],
            },
            {"name": "on_match_goto_id", "label": "성공 시 이동 ID", "type": "str", "default": ""},
            {"name": "branch_on_fail_goto_id", "label": "실패 시 이동 ID", "type": "str", "default": ""},
        ],
    },
    "wait_for_image": {
        "label": "이미지 나올 때까지 대기",
        "fields": [
            {"name": "anchor_image_path", "label": "앵커 이미지 경로", "type": "str", "default": ""},
            {"name": "threshold", "label": "매칭 임계값", "type": "float", "default": 0.85, "min": 0.1, "max": 1.0},
            {"name": "timeout_ms", "label": "타임아웃(ms)", "type": "int", "default": 5000, "min": 0, "max": 3600000},
            {"name": "poll_ms", "label": "폴링 간격(ms)", "type": "int", "default": 100, "min": 10, "max": 10000},
            {"name": "on_match_goto_id", "label": "성공 시 이동 ID", "type": "str", "default": ""},
            {"name": "branch_on_fail_goto_id", "label": "실패 시 이동 ID", "type": "str", "default": ""},
        ],
    },
    "key": {
        "label": "단축키 실행",
        "fields": [
            {"name": "key_string", "label": "키 문자열", "type": "str", "default": "enter"},
        ],
    },
    "keyboard": {
        "label": "텍스트 입력",
        "fields": [
            {
                "name": "keyboard_mode",
                "label": "모드",
                "type": "choice",
                "default": "text",
                "options": [
                    ("text", "text"),
                    ("key", "key"),
                    ("key_down", "key_down"),
                    ("key_up", "key_up"),
                    ("key_hold", "key_hold"),
                ],
            },
            {"name": "key_string", "label": "문자열/키", "type": "str", "default": ""},
            {"name": "hold_ms", "label": "홀드(ms)", "type": "int", "default": 0, "min": 0, "max": 3600000},
        ],
    },
    "pixel_check": {
        "label": "픽셀 색상 검사",
        "fields": [
            {"name": "pixel_x", "label": "X", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {"name": "pixel_y", "label": "Y", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {"name": "pixel_color_hex", "label": "색상(HEX)", "type": "str", "default": "#FFFFFF"},
            {
                "name": "pixel_color_tolerance",
                "label": "허용 오차",
                "type": "int",
                "default": 10,
                "min": 0,
                "max": 255,
            },
            {"name": "pixel_success_goto_id", "label": "성공 시 이동 ID", "type": "str", "default": ""},
            {"name": "branch_on_fail_goto_id", "label": "실패 시 이동 ID", "type": "str", "default": ""},
        ],
    },
    "ocr_check_text": {
        "label": "OCR 텍스트 검사",
        "fields": [
            {"name": "ocr_roi_x", "label": "ROI X", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {"name": "ocr_roi_y", "label": "ROI Y", "type": "int", "default": 0, "min": -99999, "max": 99999},
            {"name": "ocr_roi_w", "label": "ROI W", "type": "int", "default": 200, "min": 1, "max": 99999},
            {"name": "ocr_roi_h", "label": "ROI H", "type": "int", "default": 80, "min": 1, "max": 99999},
            {"name": "ocr_expected_text", "label": "기대 텍스트", "type": "str", "default": ""},
            {"name": "ocr_lang", "label": "언어", "type": "str", "default": "eng"},
        ],
    },
    "jump_if": {
        "label": "조건 분기",
        "fields": [
            {"name": "condition_var", "label": "변수명", "type": "str", "default": "value"},
            {
                "name": "condition_operator",
                "label": "비교",
                "type": "choice",
                "default": "==",
                "options": [("==", "=="), ("!=", "!="), (">", ">"), (">=", ">="), ("<", "<"), ("<=", "<=")],
            },
            {"name": "condition_value", "label": "비교 값", "type": "str", "default": "0"},
            {"name": "target_true_id", "label": "참일 때 이동 ID", "type": "str", "default": ""},
            {"name": "target_false_id", "label": "거짓일 때 이동 ID", "type": "str", "default": ""},
        ],
    },
    "start_loop": {
        "label": "루프 시작",
        "fields": [
            {"name": "loop_count", "label": "반복 횟수(0=무한)", "type": "int", "default": 1, "min": 0, "max": 999999},
        ],
    },
    "end_loop": {
        "label": "루프 종료",
        "fields": [
            {"name": "start_loop_id", "label": "시작 루프 ID", "type": "str", "default": ""},
        ],
    },
}

FLOW_STEP_ORDER = [
    "comment",
    "wait",
    "click_point",
    "image_click",
    "wait_for_image",
    "key",
    "keyboard",
    "pixel_check",
    "ocr_check_text",
    "jump_if",
    "start_loop",
    "end_loop",
]


class FlowValidationDialog(QDialog):
    def __init__(self, errors: list[str], warnings: list[str], *, allow_save: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("흐름 검증 결과")
        self.resize(760, 520)
        self._confirmed_save = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QLabel(f"오류 {len(errors)}건, 경고 {len(warnings)}건")
        title.setWordWrap(True)
        if errors:
            title.setStyleSheet("color:#ff6666;")
        elif warnings:
            title.setStyleSheet("color:#f6c177;")
        else:
            title.setStyleSheet("color:#7bd88f;")
        root.addWidget(title)

        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        lines: list[str] = []
        if errors:
            lines.append("[오류]")
            lines.extend(f"- {msg}" for msg in errors)
            lines.append("")
        if warnings:
            lines.append("[경고]")
            lines.extend(f"- {msg}" for msg in warnings)
        if not lines:
            lines.append("검증 이슈가 없습니다.")
        detail.setPlainText("\n".join(lines))
        root.addWidget(detail, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)
        if allow_save and not errors:
            btn_save = QPushButton("경고 무시 후 저장" if warnings else "저장")
            btn_save.clicked.connect(self._confirm_save)
            btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _confirm_save(self):
        self._confirmed_save = True
        self.accept()

    def confirmed_save(self) -> bool:
        return self._confirmed_save


class FlowStepEditDialog(QDialog):
    def __init__(
        self,
        *,
        step: dict[str, Any] | None = None,
        existing_ids: set[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("스텝 편집")
        self.resize(520, 520)
        self._step = copy.deepcopy(step) if step else None
        self._existing_ids = set(existing_ids or set())
        self._param_widgets: dict[str, Any] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)
        self.edName = QLineEdit(str((self._step or {}).get("name") or ""))
        self.cbType = QComboBox()
        for step_type in FLOW_STEP_ORDER:
            label = str(FLOW_STEP_SCHEMAS.get(step_type, {}).get("label") or step_type)
            self.cbType.addItem(f"{label} ({step_type})", step_type)
        current_type = str((self._step or {}).get("type") or "comment")
        idx = self.cbType.findData(current_type)
        if idx < 0:
            idx = self.cbType.findData("comment")
        if idx >= 0:
            self.cbType.setCurrentIndex(idx)
        form.addRow("스텝 이름", self.edName)
        form.addRow("스텝 타입", self.cbType)
        root.addLayout(form)

        self.params_wrap = QWidget()
        self.params_form = QFormLayout(self.params_wrap)
        self.params_form.setSpacing(8)
        root.addWidget(self.params_wrap, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_ok = QPushButton("확인")
        btn_cancel = QPushButton("취소")
        btn_ok.clicked.connect(self._on_accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

        self.cbType.currentIndexChanged.connect(self._rebuild_params)
        self._rebuild_params()

    def _clear_params(self):
        while self.params_form.count():
            item = self.params_form.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._param_widgets.clear()

    def _create_field_widget(self, spec: dict[str, Any], value: Any):
        ftype = str(spec.get("type") or "str")
        if ftype == "int":
            spin = QSpinBox()
            spin.setRange(int(spec.get("min", -2147483648)), int(spec.get("max", 2147483647)))
            spin.setValue(int(value if value not in (None, "") else int(spec.get("default", 0))))
            return spin
        if ftype == "float":
            dspin = QDoubleSpinBox()
            dspin.setRange(float(spec.get("min", -1e12)), float(spec.get("max", 1e12)))
            dspin.setDecimals(4)
            dspin.setValue(float(value if value not in (None, "") else float(spec.get("default", 0.0))))
            return dspin
        if ftype == "bool":
            check = QCheckBox()
            check.setChecked(bool(value if value is not None else spec.get("default", False)))
            return check
        if ftype == "choice":
            combo = QComboBox()
            for option in spec.get("options", []):
                if isinstance(option, (list, tuple)) and len(option) >= 2:
                    combo.addItem(str(option[0]), option[1])
                elif isinstance(option, dict):
                    combo.addItem(str(option.get("label", option.get("value", ""))), option.get("value"))
                else:
                    combo.addItem(str(option), option)
            target = value if value not in (None, "") else spec.get("default")
            idx = combo.findData(target)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            return combo
        if ftype == "multiline":
            text = QPlainTextEdit(str(value if value is not None else spec.get("default", "")))
            text.setFixedHeight(90)
            return text
        return QLineEdit(str(value if value is not None else spec.get("default", "")))

    def _read_field_widget(self, widget: Any) -> Any:
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText().strip()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            data = widget.currentData()
            return data if data is not None else widget.currentText()
        return None

    def _rebuild_params(self):
        self._clear_params()
        step_type = str(self.cbType.currentData() or "comment")
        schema = FLOW_STEP_SCHEMAS.get(step_type, {})
        fields = schema.get("fields", [])
        src = self._step or {}
        for spec in fields:
            key = str(spec.get("name") or "")
            if not key:
                continue
            value = src.get(key, spec.get("default"))
            widget = self._create_field_widget(spec, value)
            label = str(spec.get("label") or key)
            self.params_form.addRow(label, widget)
            self._param_widgets[key] = widget

    def _on_accept(self):
        step_type = str(self.cbType.currentData() or "comment")
        name = self.edName.text().strip()
        if not name:
            label = str(FLOW_STEP_SCHEMAS.get(step_type, {}).get("label") or step_type)
            name = f"{label} 스텝"

        row = copy.deepcopy(self._step) if self._step else {}
        for schema in FLOW_STEP_SCHEMAS.values():
            for spec in schema.get("fields", []):
                row.pop(str(spec.get("name") or ""), None)

        sid = str(row.get("id") or row.get("step_uuid") or "").strip()
        if not sid:
            sid = _new_flow_step_id(self._existing_ids)

        row["id"] = sid
        row.pop("step_uuid", None)
        row["name"] = name
        row["type"] = step_type

        for key, widget in self._param_widgets.items():
            value = self._read_field_widget(widget)
            if key in FLOW_REFERENCE_FIELDS:
                value = str(value or "").strip() or None
            row[key] = value

        if step_type != "comment":
            row.pop("comment", None)

        self._step = row
        self.accept()

    def get_step(self) -> dict[str, Any]:
        return copy.deepcopy(self._step or {})


class CustomFlowEditorDialog(QDialog):
    def __init__(
        self,
        *,
        steps_blueprint: list[dict[str, Any]] | None = None,
        system_step_ids: set[str] | list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("커스텀 흐름 편집")
        self.resize(900, 740)

        self._steps = self._normalize_steps(steps_blueprint or [])
        self._system_step_ids = {sid for sid in (system_step_ids or []) if sid}

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QLabel(
            "스텝 사이 [+] 버튼으로 새 스텝을 삽입할 수 있습니다. "
            "기본(시스템) 스텝은 읽기 전용이며, 사용자 추가 스텝만 편집/삭제 가능합니다."
        )
        head.setWordWrap(True)
        root.addWidget(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.steps_wrap = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_wrap)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(8)
        self.scroll.setWidget(self.steps_wrap)
        root.addWidget(self.scroll, 1)

        self.lblSummary = QLabel("")
        self.lblSummary.setWordWrap(True)
        root.addWidget(self.lblSummary)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_validate = QPushButton("검증")
        btn_save = QPushButton("저장")
        btn_cancel = QPushButton("취소")
        btn_validate.clicked.connect(self._on_validate)
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_validate)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

        self._rerender()

    def _normalize_steps(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for idx, raw in enumerate(rows):
            row = copy.deepcopy(raw if isinstance(raw, dict) else {})
            sid = _flow_step_id(row)
            if not sid or sid in seen:
                sid = _new_flow_step_id(seen)
            row["id"] = sid
            row.pop("step_uuid", None)
            if not str(row.get("name") or "").strip():
                row["name"] = f"Step {idx + 1}"
            if not str(row.get("type") or "").strip():
                row["type"] = "comment"
            normalized.append(row)
            seen.add(sid)
        return normalized

    def _clear_steps_layout(self):
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _step_detail_text(self, row: dict[str, Any]) -> str:
        step_type = str(row.get("type") or "")
        if step_type == "wait":
            return f"wait_ms={int(row.get('wait_ms') or 0)}"
        if step_type == "click_point":
            return (
                f"click=({int(row.get('click_x') or 0)}, {int(row.get('click_y') or 0)}), "
                f"btn={row.get('click_btn') or 'left'}"
            )
        if step_type == "image_click":
            return (
                f"image='{row.get('anchor_image_path') or ''}', "
                f"anchor={row.get('click_anchor') or 'center'}, "
                f"offset=({int(row.get('click_offset_x') or 0)}, {int(row.get('click_offset_y') or 0)}), "
                f"timeout={int(row.get('timeout_ms') or 0)}ms"
            )
        if step_type == "wait_for_image":
            return (
                f"image='{row.get('anchor_image_path') or ''}', "
                f"timeout={int(row.get('timeout_ms') or 0)}ms, "
                f"poll={int(row.get('poll_ms') or 0)}ms"
            )
        if step_type in {"key", "keyboard"}:
            return f"key='{row.get('key_string') or ''}'"
        if step_type == "start_loop":
            return f"loop_count={int(row.get('loop_count') or 0)}"
        if step_type == "end_loop":
            return f"start_loop_id={row.get('start_loop_id') or ''}"
        if step_type == "jump_if":
            return (
                f"{row.get('condition_var') or ''} {row.get('condition_operator') or '=='} "
                f"{row.get('condition_value') or ''} -> {row.get('target_true_id') or ''}"
            )
        if step_type == "pixel_check":
            return (
                f"pixel=({int(row.get('pixel_x') or 0)}, {int(row.get('pixel_y') or 0)}), "
                f"color={row.get('pixel_color_hex') or ''}"
            )
        if step_type == "ocr_check_text":
            return (
                f"roi=({int(row.get('ocr_roi_x') or 0)}, {int(row.get('ocr_roi_y') or 0)}, "
                f"{int(row.get('ocr_roi_w') or 0)}, {int(row.get('ocr_roi_h') or 0)}), "
                f"expected='{row.get('ocr_expected_text') or ''}'"
            )
        comment = str(row.get("comment") or "").strip()
        return comment if comment else "-"

    def _rerender(self):
        self._clear_steps_layout()
        total = len(self._steps)
        for idx in range(total + 1):
            insert_wrap = QWidget()
            insert_row = QHBoxLayout(insert_wrap)
            insert_row.setContentsMargins(0, 0, 0, 0)
            insert_row.setSpacing(6)
            insert_row.addStretch(1)
            btn_insert = QPushButton("+ 스텝 추가")
            btn_insert.clicked.connect(lambda _=False, target_idx=idx: self._on_insert(target_idx))
            insert_row.addWidget(btn_insert)
            insert_row.addStretch(1)
            self.steps_layout.addWidget(insert_wrap)

            if idx >= total:
                continue

            row = self._steps[idx]
            sid = _flow_step_id(row)
            is_system = sid in self._system_step_ids

            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            frame.setStyleSheet(
                "QFrame { background:#303030; border:1px solid #666; border-radius:6px; }"
                if is_system
                else "QFrame { background:#1f2733; border:1px solid #4a90e2; border-radius:6px; }"
            )

            card = QVBoxLayout(frame)
            card.setContentsMargins(10, 8, 10, 8)
            card.setSpacing(6)

            head_row = QHBoxLayout()
            title = QLabel(f"{idx + 1}. [{row.get('type')}] {row.get('name')}")
            head_row.addWidget(title, 1)
            badge = QLabel("기본 스텝" if is_system else "사용자 스텝")
            badge.setStyleSheet("color:#bbbbbb;")
            head_row.addWidget(badge)
            btn_edit = QPushButton("편집")
            btn_edit.setEnabled(not is_system)
            btn_edit.clicked.connect(lambda _=False, target_idx=idx: self._on_edit(target_idx))
            btn_delete = QPushButton("삭제")
            btn_delete.setEnabled(not is_system)
            btn_delete.clicked.connect(lambda _=False, target_idx=idx: self._on_delete(target_idx))
            head_row.addWidget(btn_edit)
            head_row.addWidget(btn_delete)
            card.addLayout(head_row)

            info = QLabel(f"id={sid}")
            info.setStyleSheet("color:#a8a8a8;")
            card.addWidget(info)

            detail = QLabel(self._step_detail_text(row))
            detail.setWordWrap(True)
            detail.setStyleSheet("color:#d0d0d0;")
            card.addWidget(detail)
            self.steps_layout.addWidget(frame)

        self.steps_layout.addStretch(1)
        custom_count = sum(1 for row in self._steps if _flow_step_id(row) not in self._system_step_ids)
        self.lblSummary.setText(
            f"총 {len(self._steps)} 스텝 (기본 {len(self._steps) - custom_count}, 사용자 {custom_count})"
        )

    def _on_insert(self, index: int):
        existing_ids = {_flow_step_id(row) for row in self._steps}
        dlg = FlowStepEditDialog(existing_ids=existing_ids, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        step = dlg.get_step()
        if not step:
            return
        self._steps.insert(index, step)
        self._rerender()

    def _on_edit(self, index: int):
        if index < 0 or index >= len(self._steps):
            return
        current = self._steps[index]
        sid = _flow_step_id(current)
        if sid in self._system_step_ids:
            QMessageBox.information(self, "커스텀 흐름 편집", "기본 스텝은 편집할 수 없습니다.")
            return

        existing_ids = {_flow_step_id(row) for row in self._steps if _flow_step_id(row) != sid}
        dlg = FlowStepEditDialog(step=current, existing_ids=existing_ids, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        updated = dlg.get_step()
        if not updated:
            return
        self._steps[index] = updated
        self._rerender()

    def _on_delete(self, index: int):
        if index < 0 or index >= len(self._steps):
            return
        current = self._steps[index]
        sid = _flow_step_id(current)
        if sid in self._system_step_ids:
            QMessageBox.information(self, "커스텀 흐름 편집", "기본 스텝은 삭제할 수 없습니다.")
            return

        refs = find_references_in_blueprint(self._steps, sid)
        if refs:
            sample = ", ".join(f"{row.get('step_name')}:{row.get('field')}" for row in refs[:4])
            suffix = "" if len(refs) <= 4 else f" 외 {len(refs) - 4}건"
            reply = QMessageBox.warning(
                self,
                "참조 경고",
                f"이 스텝을 참조하는 분기 {len(refs)}건이 있습니다.\n"
                f"대상: {sample}{suffix}\n\n"
                "삭제하면 가능한 경우 다음 스텝으로 자동 연결됩니다.\n계속하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        updated, rewired, warnings = delete_step_with_lazy_repair(self._steps, sid)
        self._steps = updated
        if rewired or warnings:
            lines: list[str] = []
            if rewired:
                lines.append(f"자동 보정 {len(rewired)}건 적용")
            lines.extend(f"- {msg}" for msg in warnings)
            QMessageBox.information(self, "삭제 보정 결과", "\n".join(lines))
        self._rerender()

    def _validation_messages(self) -> tuple[list[str], list[str]]:
        report = validate_custom_flow_blueprint(self._steps)
        errors: list[str] = []
        warnings: list[str] = []
        for item in report.get("errors", []):
            suffix = f" (step={item.step_id})" if getattr(item, "step_id", None) else ""
            errors.append(f"{item.message}{suffix}")
        for item in report.get("warnings", []):
            suffix = f" (step={item.step_id})" if getattr(item, "step_id", None) else ""
            warnings.append(f"{item.message}{suffix}")
        return errors, warnings

    def _on_validate(self):
        errors, warnings = self._validation_messages()
        dlg = FlowValidationDialog(errors, warnings, allow_save=False, parent=self)
        dlg.exec_()

    def _on_save(self):
        errors, warnings = self._validation_messages()
        dlg = FlowValidationDialog(errors, warnings, allow_save=True, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        if not dlg.confirmed_save():
            return
        self.accept()

    def get_steps_blueprint(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._steps)

    def get_system_step_ids(self) -> list[str]:
        active_ids = {_flow_step_id(row) for row in self._steps}
        kept = [sid for sid in sorted(self._system_step_ids) if sid in active_ids]
        return kept


class UserTemplateEditDialog(QDialog):
    def __init__(
        self,
        template: dict[str, Any],
        initial_values: dict[str, Any] | None = None,
        flow_blueprint: list[dict[str, Any]] | None = None,
        flow_system_step_ids: list[str] | set[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("사용자 템플릿 편집")
        self.resize(760, 820)
        self._template = template
        self._default_widgets: dict[str, Any] = {}
        self._flow_seed_blueprint = copy.deepcopy(flow_blueprint or [])
        self._flow_blueprint = copy.deepcopy(flow_blueprint or [])
        self._flow_system_step_ids = {str(x).strip() for x in (flow_system_step_ids or []) if str(x).strip()}
        self._flow_enabled = str(template.get("mode") or "").strip().lower() == "custom_flow"
        if self._flow_enabled and not self._flow_seed_blueprint:
            self._flow_seed_blueprint = copy.deepcopy(template.get("steps_blueprint") or [])
            self._flow_blueprint = copy.deepcopy(self._flow_seed_blueprint)

        initial_values = initial_values or {}
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self.edTitle = QLineEdit(str(template.get("title") or ""))
        self.edSummary = QPlainTextEdit(str(template.get("summary") or ""))
        self.edSummary.setFixedHeight(84)
        tags = ", ".join(str(x) for x in template.get("tags", []) if str(x).strip())
        self.edTags = QLineEdit(tags)

        meta_form = QFormLayout()
        meta_form.addRow("제목", self.edTitle)
        meta_form.addRow("요약", self.edSummary)
        meta_form.addRow("태그(콤마 구분)", self.edTags)
        root.addLayout(meta_form)

        root.addWidget(QLabel("기본값 편집"))
        defaults_wrap = QWidget()
        self.defaults_form = QFormLayout(defaults_wrap)
        self.defaults_form.setContentsMargins(6, 6, 6, 6)
        self.defaults_form.setSpacing(8)

        for field in template.get("fields", []):
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            raw_default = initial_values.get(name, field.get("default"))
            self._add_default_field(field, raw_default)

        defaults_scroll = QScrollArea()
        defaults_scroll.setWidgetResizable(True)
        defaults_scroll.setWidget(defaults_wrap)
        root.addWidget(defaults_scroll, 1)

        flow_box = QFrame()
        flow_box.setFrameShape(QFrame.StyledPanel)
        flow_box.setStyleSheet("QFrame { border:1px solid #555; border-radius:6px; }")
        flow_layout = QVBoxLayout(flow_box)
        flow_layout.setContentsMargins(8, 8, 8, 8)
        flow_layout.setSpacing(6)
        flow_layout.addWidget(QLabel("고급 편집: 스텝 흐름(custom_flow)"))
        self.lblFlowState = QLabel("")
        self.lblFlowState.setWordWrap(True)
        flow_layout.addWidget(self.lblFlowState)
        flow_btn_row = QHBoxLayout()
        flow_btn_row.setContentsMargins(0, 0, 0, 0)
        self.btnFlowEdit = QPushButton("흐름 편집 열기")
        self.btnFlowEdit.clicked.connect(self._on_edit_flow)
        flow_btn_row.addWidget(self.btnFlowEdit)
        flow_btn_row.addStretch(1)
        flow_layout.addLayout(flow_btn_row)
        root.addWidget(flow_box)
        self._refresh_flow_state()

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_ok = QPushButton("저장")
        btn_cancel = QPushButton("취소")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

    def _add_default_field(self, field: dict[str, Any], value: Any):
        name = str(field.get("name") or "").strip()
        label = str(field.get("label") or name)
        ftype = str(field.get("type", "str"))

        widget: Any
        if ftype == "int":
            spin = QSpinBox()
            spin.setRange(int(field.get("min", -2147483648)), int(field.get("max", 2147483647)))
            spin.setValue(int(value or 0))
            widget = spin
        elif ftype == "float":
            dspin = QDoubleSpinBox()
            dspin.setDecimals(4)
            dspin.setRange(float(field.get("min", -1e12)), float(field.get("max", 1e12)))
            dspin.setValue(float(value or 0.0))
            widget = dspin
        elif ftype == "bool":
            check = QCheckBox()
            check.setChecked(bool(value))
            widget = check
        elif ftype == "choice":
            combo = QComboBox()
            options = field.get("options") or []
            for option in options:
                if isinstance(option, dict):
                    combo.addItem(str(option.get("label", option.get("value", ""))), option.get("value"))
                else:
                    combo.addItem(str(option), option)
            idx = combo.findData(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            widget = combo
        elif ftype == "multiline":
            text = QPlainTextEdit(str(value or ""))
            text.setFixedHeight(84)
            widget = text
        else:
            widget = QLineEdit(str(value or ""))

        self._default_widgets[name] = widget
        self.defaults_form.addRow(label, widget)

    def _read_widget_value(self, widget: Any) -> Any:
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            data = widget.currentData()
            return data if data is not None else widget.currentText()
        return None

    def _refresh_flow_state(self):
        seed_count = len(self._flow_seed_blueprint)
        flow_count = len(self._flow_blueprint)
        if self._flow_enabled and flow_count > 0:
            self.lblFlowState.setText(f"custom_flow 사용 중: {flow_count} 스텝")
            self.lblFlowState.setStyleSheet("color:#7bd88f;")
            return
        if seed_count > 0:
            self.lblFlowState.setText(
                "기본 빌더 방식 사용 중. 필요하면 흐름 편집에서 스텝 사이에 동작을 삽입할 수 있습니다."
            )
            self.lblFlowState.setStyleSheet("color:#d0d0d0;")
            return
        self.lblFlowState.setText("현재 입력값으로는 흐름 편집을 시작할 스텝이 없습니다.")
        self.lblFlowState.setStyleSheet("color:#f6c177;")

    def _on_edit_flow(self):
        source = self._flow_blueprint if self._flow_enabled and self._flow_blueprint else self._flow_seed_blueprint
        if not source:
            QMessageBox.information(
                self,
                "사용자 템플릿 편집",
                "흐름 편집을 시작할 스텝이 없습니다. 먼저 템플릿 입력값을 채워 미리보기를 생성하세요.",
            )
            return

        if self._flow_enabled:
            system_ids = self._flow_system_step_ids
        else:
            system_ids = {_flow_step_id(row) for row in source}

        dlg = CustomFlowEditorDialog(
            steps_blueprint=source,
            system_step_ids=system_ids,
            parent=self,
        )
        if dlg.exec_() != QDialog.Accepted:
            return

        self._flow_blueprint = dlg.get_steps_blueprint()
        self._flow_system_step_ids = set(dlg.get_system_step_ids())
        self._flow_enabled = True
        self._refresh_flow_state()

    def get_payload(self) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for name, widget in self._default_widgets.items():
            defaults[name] = self._read_widget_value(widget)

        tags = [x.strip() for x in self.edTags.text().split(",") if x.strip()]
        return {
            "title": self.edTitle.text().strip(),
            "summary": self.edSummary.toPlainText().strip(),
            "tags": tags,
            "defaults": defaults,
            "use_custom_flow": bool(self._flow_enabled and self._flow_blueprint),
            "steps_blueprint": copy.deepcopy(self._flow_blueprint) if self._flow_enabled else None,
            "system_step_ids": sorted(self._flow_system_step_ids) if self._flow_enabled else [],
        }


class ScenarioWizardDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("시나리오 마법사")
        self.resize(1080, 740)

        self._templates = list_templates()
        self._current_template: dict[str, Any] | None = None
        self._field_widgets: dict[str, Any] = {}
        self._field_defs: dict[str, dict[str, Any]] = {}
        self._column_map_buttons: dict[str, QPushButton] = {}
        self._data_columns: list[str] = []
        self._data_file_path_cache: str = ""
        self._data_file_error: str = ""
        self._planned: dict[str, Any] | None = None
        self._result: dict[str, Any] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QLabel(
            "고급 사용자 활용 예시를 선택하면, 필요한 값만 입력해 매크로 스텝을 자동 생성합니다."
        )
        head.setWordWrap(True)
        root.addWidget(head)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        self.cbScope = QComboBox()
        self.cbScope.addItem("추천", "recommended")
        self.cbScope.addItem("전체", "all")
        self.cbScope.addItem("사용자", "user")
        self.cbScope.currentIndexChanged.connect(self._refresh_template_list)
        self.edSearch = QLineEdit()
        self.edSearch.setPlaceholderText("템플릿 검색 (제목/요약/태그)")
        self.edSearch.textChanged.connect(self._refresh_template_list)
        filter_row.addWidget(QLabel("목록"))
        filter_row.addWidget(self.cbScope)
        filter_row.addWidget(self.edSearch, 1)
        left_layout.addLayout(filter_row)

        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(0, 0, 0, 0)
        self.btnCloneTemplate = QPushButton("복제 저장")
        self.btnCloneTemplate.clicked.connect(self._on_clone_template)
        self.btnEditTemplate = QPushButton("사용자 편집")
        self.btnEditTemplate.clicked.connect(self._on_edit_template)
        self.btnDeleteTemplate = QPushButton("사용자 삭제")
        self.btnDeleteTemplate.clicked.connect(self._on_delete_template)
        edit_row.addWidget(self.btnCloneTemplate)
        edit_row.addWidget(self.btnEditTemplate)
        edit_row.addWidget(self.btnDeleteTemplate)
        left_layout.addLayout(edit_row)

        self.lstTemplates = QListWidget()
        self.lstTemplates.currentItemChanged.connect(self._on_template_changed)
        left_layout.addWidget(self.lstTemplates, 3)

        left_layout.addWidget(QLabel("템플릿 설명"))
        self.txtTemplateMeta = QPlainTextEdit()
        self.txtTemplateMeta.setReadOnly(True)
        self.txtTemplateMeta.setPlaceholderText("템플릿을 선택하면 난이도/전제조건/실패 포인트가 표시됩니다.")
        left_layout.addWidget(self.txtTemplateMeta, 2)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        right_layout.addWidget(QLabel("필요 정보 입력"))
        self.form_container = QWidget()
        self.form_layout = QFormLayout(self.form_container)
        self.form_layout.setContentsMargins(6, 6, 6, 6)
        self.form_layout.setSpacing(8)

        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(self.form_container)
        right_layout.addWidget(form_scroll, 3)

        insert_row = QHBoxLayout()
        insert_row.setContentsMargins(0, 0, 0, 0)
        self.cbInsertMode = QComboBox()
        self.cbInsertMode.addItem("선택 스텝 다음에 삽입", "after_selection")
        self.cbInsertMode.addItem("시나리오 끝에 삽입", "end")
        insert_row.addWidget(QLabel("삽입 위치"))
        insert_row.addWidget(self.cbInsertMode, 1)
        right_layout.addLayout(insert_row)

        right_layout.addWidget(QLabel("생성 미리보기"))
        self.txtPreview = QPlainTextEdit()
        self.txtPreview.setReadOnly(True)
        self.txtPreview.setPlaceholderText("입력값을 채우면 생성될 스텝이 여기에 표시됩니다.")
        right_layout.addWidget(self.txtPreview, 2)

        self.lblValidation = QLabel("템플릿을 선택하세요.")
        self.lblValidation.setWordWrap(True)
        right_layout.addWidget(self.lblValidation)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.btnApply = QPushButton("매크로에 추가")
        self.btnApply.setEnabled(False)
        self.btnApply.clicked.connect(self._on_apply)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btnApply)
        btn_row.addWidget(btn_cancel)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([430, 650])

        self._refresh_template_list()

    def _clear_form(self):
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._field_widgets.clear()
        self._field_defs.clear()
        self._column_map_buttons.clear()
        self._data_columns = []
        self._data_file_path_cache = ""
        self._data_file_error = ""

    def _reload_templates(self):
        self._templates = list_templates()

    def _select_template_by_id(self, template_id: str):
        wanted = str(template_id or "")
        for idx in range(self.lstTemplates.count()):
            item = self.lstTemplates.item(idx)
            if str(item.data(Qt.UserRole) or "") == wanted:
                self.lstTemplates.setCurrentRow(idx)
                return

    def _update_template_buttons(self):
        has_template = self._current_template is not None
        user_template = is_user_template(self._current_template)
        self.btnCloneTemplate.setEnabled(has_template)
        self.btnEditTemplate.setEnabled(user_template)
        self.btnDeleteTemplate.setEnabled(user_template)

    def _refresh_template_list(self):
        self._reload_templates()
        scope = self.cbScope.currentData() or "recommended"
        query = self.edSearch.text().strip().lower()

        self.lstTemplates.clear()
        for template in self._templates:
            if scope == "recommended" and not bool(template.get("recommended")):
                continue
            if scope == "user" and not is_user_template(template):
                continue

            haystack = " ".join(
                [
                    str(template.get("title", "")),
                    str(template.get("summary", "")),
                    " ".join(str(tag) for tag in template.get("tags", [])),
                ]
            ).lower()
            if query and query not in haystack:
                continue

            title = str(template.get("title", template.get("id", "unknown")))
            summary = str(template.get("summary", "")).strip()
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, template.get("id"))
            if summary:
                item.setToolTip(f"{title}\n{summary}")
            self.lstTemplates.addItem(item)

        if self.lstTemplates.count() > 0:
            self.lstTemplates.setCurrentRow(0)
        else:
            self._current_template = None
            self._clear_form()
            self.txtTemplateMeta.setPlainText("일치하는 템플릿이 없습니다.")
            self.txtPreview.clear()
            self.lblValidation.setText("템플릿이 선택되지 않았습니다.")
            self.btnApply.setEnabled(False)
            self._update_template_buttons()

    def _render_template_meta(self, template: dict[str, Any]):
        lines: list[str] = []
        lines.append(f"제목: {template.get('title', '')}")
        lines.append(f"출처: {_template_source_label(template)}")
        lines.append(f"난이도: {_difficulty_label(template.get('difficulty'))}")
        lines.append(f"요약: {template.get('summary', '')}")

        tags = [str(x) for x in template.get("tags", []) if str(x).strip()]
        if tags:
            lines.append("태그: " + ", ".join(tags))

        prereq = [str(x) for x in template.get("prerequisites", []) if str(x).strip()]
        if prereq:
            lines.append("")
            lines.append("전제조건")
            for row in prereq:
                lines.append(f"- {row}")

        risks = [str(x) for x in template.get("failure_points", []) if str(x).strip()]
        if risks:
            lines.append("")
            lines.append("실패 포인트")
            for row in risks:
                lines.append(f"- {row}")

        self.txtTemplateMeta.setPlainText("\n".join(lines))

    def _on_template_changed(self, current: QListWidgetItem, _previous: QListWidgetItem | None):
        if current is None:
            self._current_template = None
            self._clear_form()
            self.txtPreview.clear()
            self.lblValidation.setText("템플릿이 선택되지 않았습니다.")
            self.btnApply.setEnabled(False)
            self._update_template_buttons()
            return

        template_id = str(current.data(Qt.UserRole) or "")
        template = get_template(template_id)
        self._current_template = template
        self._clear_form()

        if template is None:
            self.txtTemplateMeta.setPlainText("선택한 템플릿을 불러올 수 없습니다.")
            self.lblValidation.setText("템플릿 로딩 실패")
            self.btnApply.setEnabled(False)
            self._update_template_buttons()
            return

        self._render_template_meta(template)
        for field in template.get("fields", []):
            self._add_field(field)
        self._update_template_buttons()
        self._refresh_preview()

    def _connect_refresh_signal(self, widget: Any):
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._refresh_preview)
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(self._refresh_preview)
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(self._refresh_preview)
        elif isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(self._refresh_preview)
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(self._refresh_preview)
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(self._refresh_preview)

    def _browse_path(self, field_name: str):
        field = self._field_defs.get(field_name, {})
        field_widget = self._field_widgets.get(field_name)
        if not isinstance(field_widget, tuple) or not field_widget:
            return
        line_edit: QLineEdit = field_widget[0]
        mode = str(field.get("browse_mode") or "open_file")
        file_filter = str(field.get("file_filter") or "All Files (*)")
        current = line_edit.text().strip()

        if mode == "save_file":
            path, _ = QFileDialog.getSaveFileName(self, "경로 선택", current, file_filter)
            if path:
                line_edit.setText(path)
            return

        if mode == "open_dir":
            path = QFileDialog.getExistingDirectory(self, "폴더 선택", current)
            if path:
                line_edit.setText(path)
            return

        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", current, file_filter)
        if path:
            line_edit.setText(path)

    def _extract_data_file_path(self, values: dict[str, Any]) -> str:
        if "data_file_path" in values:
            return str(values.get("data_file_path") or "").strip()

        for name, field in self._field_defs.items():
            if str(field.get("type") or "") != "path":
                continue
            lname = name.lower()
            if "data" in lname and "file" in lname:
                return str(values.get(name) or "").strip()
        return ""

    def _refresh_data_file_context(self, values: dict[str, Any]):
        path = self._extract_data_file_path(values)
        if path == self._data_file_path_cache:
            return

        self._data_file_path_cache = path
        self._data_file_error = ""
        self._data_columns = []

        if path:
            ok, info, err = inspect_data_file(path)
            if ok:
                self._data_columns = [str(x) for x in info.get("columns", []) if str(x).strip()]
                empty_rows = int(info.get("empty_row_count") or 0)
                if empty_rows > 0:
                    self._data_file_error = f"빈 행 {empty_rows}개는 자동 스킵됩니다."
            else:
                self._data_file_error = str(err or "데이터 파일을 읽을 수 없습니다.")

        self._update_column_map_buttons()

    def _update_column_map_buttons(self):
        for button in self._column_map_buttons.values():
            if self._data_columns:
                button.setEnabled(True)
                button.setToolTip("데이터 컬럼 토큰을 삽입합니다.")
            else:
                button.setEnabled(False)
                if self._data_file_path_cache:
                    button.setToolTip(self._data_file_error or "데이터 컬럼을 불러오지 못했습니다.")
                else:
                    button.setToolTip("먼저 데이터 파일 경로를 입력하세요.")

    def _insert_column_token(self, field_name: str, column_name: str):
        token = f"{{{column_name}}}"
        widget = self._field_widgets.get(field_name)
        if isinstance(widget, tuple):
            target = widget[0]
        else:
            target = widget

        if isinstance(target, QLineEdit):
            target.insert(token)
        elif isinstance(target, QPlainTextEdit):
            cursor = target.textCursor()
            cursor.insertText(token)
            target.setTextCursor(cursor)
        self._refresh_preview()

    def _open_column_map_menu(self, field_name: str):
        if not self._data_columns:
            QMessageBox.information(self, "컬럼 매핑", "먼저 유효한 데이터 파일을 선택하세요.")
            return

        button = self._column_map_buttons.get(field_name)
        if button is None:
            return
        menu = QMenu(button)
        for col in self._data_columns:
            action = menu.addAction(f"{{{col}}}")
            action.triggered.connect(lambda _=False, key=field_name, c=col: self._insert_column_token(key, c))
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def _add_field(self, field: dict[str, Any]):
        name = str(field.get("name", "")).strip()
        if not name:
            return
        label = str(field.get("label") or name)
        ftype = str(field.get("type", "str"))
        default = field.get("default")
        has_data_source_field = bool(
            self._current_template
            and any(str(f.get("name") or "").strip() == "data_file_path" for f in self._current_template.get("fields", []))
        )

        widget: Any
        if ftype == "int":
            spin = QSpinBox()
            spin.setRange(int(field.get("min", -2147483648)), int(field.get("max", 2147483647)))
            spin.setValue(int(default or 0))
            widget = spin
        elif ftype == "float":
            dspin = QDoubleSpinBox()
            dspin.setDecimals(4)
            dspin.setRange(float(field.get("min", -1e12)), float(field.get("max", 1e12)))
            dspin.setValue(float(default or 0.0))
            widget = dspin
        elif ftype == "bool":
            check = QCheckBox()
            check.setChecked(bool(default))
            widget = check
        elif ftype == "choice":
            combo = QComboBox()
            options = field.get("options") or []
            for option in options:
                if isinstance(option, dict):
                    combo.addItem(str(option.get("label", option.get("value", ""))), option.get("value"))
                else:
                    combo.addItem(str(option), option)
            target = field.get("default")
            idx = combo.findData(target)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            widget = combo
        elif ftype == "multiline":
            text = QPlainTextEdit()
            text.setPlainText(str(default or ""))
            text.setFixedHeight(84)
            widget = text
        elif ftype == "path":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            edit = QLineEdit(str(default or ""))
            browse = QPushButton("찾기...")
            browse.setFixedWidth(70)
            browse.clicked.connect(lambda _=False, key=name: self._browse_path(key))
            row_layout.addWidget(edit, 1)
            row_layout.addWidget(browse)
            widget = (edit, browse, row)
        else:
            line = QLineEdit(str(default or ""))
            placeholder = str(field.get("placeholder") or "")
            if placeholder:
                line.setPlaceholderText(placeholder)
            if ftype == "str" and has_data_source_field:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)
                map_btn = QPushButton("컬럼")
                map_btn.setFixedWidth(56)
                map_btn.setEnabled(False)
                map_btn.setToolTip("먼저 데이터 파일 경로를 입력하세요.")
                map_btn.clicked.connect(lambda _=False, key=name: self._open_column_map_menu(key))
                row_layout.addWidget(line, 1)
                row_layout.addWidget(map_btn)
                self._column_map_buttons[name] = map_btn
                widget = (line, map_btn, row)
            else:
                widget = line

        self._field_defs[name] = field
        self._field_widgets[name] = widget

        if isinstance(widget, tuple):
            self.form_layout.addRow(label, widget[2])
            self._connect_refresh_signal(widget[0])
        else:
            self.form_layout.addRow(label, widget)
            self._connect_refresh_signal(widget)

    def _collect_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name, widget in self._field_widgets.items():
            if isinstance(widget, tuple):
                values[name] = widget[0].text()
            elif isinstance(widget, QLineEdit):
                values[name] = widget.text()
            elif isinstance(widget, QPlainTextEdit):
                values[name] = widget.toPlainText()
            elif isinstance(widget, QSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                data = widget.currentData()
                values[name] = data if data is not None else widget.currentText()
        return values

    def _steps_to_blueprint(self, steps: list[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for idx, step in enumerate(steps):
            if isinstance(step, dict):
                row = copy.deepcopy(step)
            elif hasattr(step, "to_serializable"):
                row = step.to_serializable()
            else:
                row = {}
            sid = str(getattr(step, "id", None) or row.get("id") or row.get("step_uuid") or "").strip()
            if not sid or sid in seen:
                sid = _new_flow_step_id(seen)
            row["id"] = sid
            row.pop("step_uuid", None)
            if not str(row.get("name") or "").strip():
                row["name"] = f"Step {idx + 1}"
            if not str(row.get("type") or "").strip():
                row["type"] = "comment"
            rows.append(row)
            seen.add(sid)
        return rows

    def _has_user_value(self, field: dict[str, Any], values: dict[str, Any]) -> bool:
        name = str(field.get("name") or "").strip()
        if not name or name not in values:
            return False
        value = values.get(name)
        ftype = str(field.get("type") or "str")
        if ftype in {"str", "path", "multiline", "choice"}:
            return str(value or "").strip() != ""
        return value is not None

    def _auto_seed_field_value(self, field: dict[str, Any]) -> Any:
        ftype = str(field.get("type") or "str")
        required = bool(field.get("required"))

        if "default" in field and field.get("default") not in (None, ""):
            return field.get("default")

        if ftype == "int":
            min_val = field.get("min")
            if min_val is not None:
                try:
                    return int(min_val)
                except Exception:
                    pass
            return 1 if required else 0

        if ftype == "float":
            min_val = field.get("min")
            if min_val is not None:
                try:
                    return float(min_val)
                except Exception:
                    pass
            return 1.0 if required else 0.0

        if ftype == "bool":
            return bool(field.get("default", False))

        if ftype == "choice":
            options = field.get("options") or []
            if options:
                first = options[0]
                if isinstance(first, dict):
                    return first.get("value")
                if isinstance(first, (list, tuple)) and len(first) >= 2:
                    return first[1]
                return first
            return ""

        if ftype == "path":
            mode = str(field.get("browse_mode") or "open_file")
            if mode == "open_dir":
                return "."
            if mode == "save_file":
                return "output.png"
            return "input.txt"

        if ftype == "multiline":
            return "auto"

        if ftype == "str":
            return "auto" if required else ""

        return ""

    def _build_auto_seed_values(self, template: dict[str, Any], initial_values: dict[str, Any]) -> dict[str, Any]:
        values = dict(initial_values or {})
        for field in template.get("fields", []):
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            if self._has_user_value(field, values):
                continue
            values[name] = self._auto_seed_field_value(field)
        return values

    def _flow_seed_for_editor(
        self,
        template: dict[str, Any],
        initial_values: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], set[str]]:
        mode = str(template.get("mode") or "").strip().lower()
        if mode == "custom_flow":
            raw_rows = template.get("steps_blueprint") or []
            if not isinstance(raw_rows, list):
                return [], set()
            rows = self._steps_to_blueprint(raw_rows)
            valid_ids = {_flow_step_id(row) for row in rows}
            stored = template.get("custom_flow_system_step_ids") or []
            system_ids = {str(x).strip() for x in stored if str(x).strip() in valid_ids}
            return rows, system_ids

        template_id = str(template.get("id") or "")
        planned = plan_template(template_id, initial_values)
        if planned.get("errors"):
            auto_seed = self._build_auto_seed_values(template, initial_values)
            planned = plan_template(template_id, auto_seed)
            if planned.get("errors"):
                return [], set()
        rows = self._steps_to_blueprint(planned.get("steps") or [])
        return rows, {_flow_step_id(row) for row in rows}

    def _apply_custom_flow_payload(self, template: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        if not bool(payload.get("use_custom_flow")):
            return []

        rows = payload.get("steps_blueprint")
        if not isinstance(rows, list) or not rows:
            return ["custom_flow 스텝이 비어 있어 저장할 수 없습니다."]

        report = validate_custom_flow_blueprint(rows)
        errors = [item.message for item in report.get("errors", [])]
        if errors:
            return errors

        step_ids = {_flow_step_id(row) for row in rows}
        system_ids = [str(x).strip() for x in payload.get("system_step_ids", []) if str(x).strip() in step_ids]

        template["mode"] = "custom_flow"
        template["steps_blueprint"] = copy.deepcopy(rows)
        template["fields"] = []
        template["recommended"] = False
        template["custom_flow_system_step_ids"] = system_ids
        return []

    def _open_user_template_editor(self, template: dict[str, Any], initial_values: dict[str, Any]) -> dict[str, Any] | None:
        flow_blueprint, flow_system_ids = self._flow_seed_for_editor(template, initial_values)
        dlg = UserTemplateEditDialog(
            template,
            initial_values=initial_values,
            flow_blueprint=flow_blueprint,
            flow_system_step_ids=flow_system_ids,
            parent=self,
        )
        if dlg.exec_() != QDialog.Accepted:
            return None
        return dlg.get_payload()

    def _on_clone_template(self):
        template = self._current_template
        if not template:
            QMessageBox.warning(self, "시나리오 마법사", "복제할 템플릿을 먼저 선택하세요.")
            return

        payload = self._open_user_template_editor(template, self._collect_values())
        if payload is None:
            return

        new_template, errors = create_user_template_from_base(
            str(template.get("id") or ""),
            title=payload.get("title"),
            summary=payload.get("summary"),
            tags=payload.get("tags"),
            field_defaults=payload.get("defaults"),
        )
        if errors or new_template is None:
            QMessageBox.warning(self, "시나리오 마법사", "\n".join(errors or ["사용자 템플릿 생성 실패"]))
            return

        flow_errors = self._apply_custom_flow_payload(new_template, payload)
        if flow_errors:
            QMessageBox.warning(self, "시나리오 마법사", "\n".join(flow_errors))
            return

        ok, save_errors = upsert_user_template(new_template)
        if not ok:
            QMessageBox.warning(self, "시나리오 마법사", "\n".join(save_errors or ["사용자 템플릿 저장 실패"]))
            return

        if self.cbScope.currentData() == "recommended":
            idx = self.cbScope.findData("user")
            if idx >= 0:
                self.cbScope.setCurrentIndex(idx)
        self._refresh_template_list()
        self._select_template_by_id(str(new_template.get("id") or ""))

    def _on_edit_template(self):
        template = self._current_template
        if not template or not is_user_template(template):
            QMessageBox.information(self, "시나리오 마법사", "사용자 템플릿만 편집할 수 있습니다.")
            return

        payload = self._open_user_template_editor(template, self._collect_values())
        if payload is None:
            return

        edited_template, errors = create_user_template_from_base(
            str(template.get("id") or ""),
            title=payload.get("title"),
            summary=payload.get("summary"),
            tags=payload.get("tags"),
            field_defaults=payload.get("defaults"),
            user_template_id=str(template.get("id") or ""),
        )
        if errors or edited_template is None:
            QMessageBox.warning(self, "시나리오 마법사", "\n".join(errors or ["사용자 템플릿 편집 실패"]))
            return

        flow_errors = self._apply_custom_flow_payload(edited_template, payload)
        if flow_errors:
            QMessageBox.warning(self, "시나리오 마법사", "\n".join(flow_errors))
            return

        ok, save_errors = upsert_user_template(edited_template)
        if not ok:
            QMessageBox.warning(self, "시나리오 마법사", "\n".join(save_errors or ["사용자 템플릿 저장 실패"]))
            return

        self._refresh_template_list()
        self._select_template_by_id(str(edited_template.get("id") or ""))

    def _on_delete_template(self):
        template = self._current_template
        if not template or not is_user_template(template):
            QMessageBox.information(self, "시나리오 마법사", "사용자 템플릿만 삭제할 수 있습니다.")
            return

        title = str(template.get("title") or template.get("id") or "")
        reply = QMessageBox.question(
            self,
            "사용자 템플릿 삭제",
            f"'{title}' 템플릿을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        ok, error = delete_user_template(str(template.get("id") or ""))
        if not ok:
            QMessageBox.warning(self, "시나리오 마법사", str(error or "사용자 템플릿 삭제 실패"))
            return

        self._refresh_template_list()

    def _refresh_preview(self):
        if not self._current_template:
            self.btnApply.setEnabled(False)
            return

        template_id = str(self._current_template.get("id") or "")
        values = self._collect_values()
        self._refresh_data_file_context(values)
        planned = plan_template(template_id, values)
        self._planned = planned

        lines = summarize_steps(planned.get("steps") or [])
        if lines:
            self.txtPreview.setPlainText("\n".join(lines))
        else:
            self.txtPreview.setPlainText("생성된 스텝이 없습니다.")

        errors = planned.get("errors") or []
        warnings = planned.get("warnings") or []

        if errors:
            joined = "\n".join(f"- {row}" for row in errors)
            self.lblValidation.setText(f"오류 {len(errors)}건\n{joined}")
            self.lblValidation.setStyleSheet("color:#ff6666;")
            self.btnApply.setEnabled(False)
            return

        if warnings:
            joined = "\n".join(f"- {row}" for row in warnings)
            self.lblValidation.setText(f"경고 {len(warnings)}건\n{joined}")
            self.lblValidation.setStyleSheet("color:#f6c177;")
        else:
            self.lblValidation.setText("검증 통과: 즉시 적용 가능합니다.")
            self.lblValidation.setStyleSheet("color:#7bd88f;")

        self.btnApply.setEnabled(bool(planned.get("steps")))

    def _on_apply(self):
        self._refresh_preview()
        if not self._planned:
            return

        errors = self._planned.get("errors") or []
        warnings = self._planned.get("warnings") or []
        steps = self._planned.get("steps") or []
        template = self._planned.get("template") or self._current_template or {}
        if errors or not steps:
            QMessageBox.warning(self, "시나리오 마법사", "오류를 먼저 해결해주세요.")
            return

        if warnings:
            detail = "\n".join(f"- {row}" for row in warnings)
            reply = QMessageBox.question(
                self,
                "경고 확인",
                f"다음 경고가 있습니다.\n\n{detail}\n\n계속 생성하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._result = {
            "template_id": template.get("id"),
            "template_title": template.get("title"),
            "insert_mode": self.cbInsertMode.currentData() or "end",
            "steps": steps,
            "values": self._planned.get("values") or {},
        }
        self.accept()

    def get_result(self) -> dict[str, Any] | None:
        return self._result

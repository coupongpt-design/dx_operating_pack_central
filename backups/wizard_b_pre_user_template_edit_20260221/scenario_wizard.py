from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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

from ..core.scenario_wizard import get_template, list_templates, plan_template, summarize_steps


def _difficulty_label(raw: str | None) -> str:
    norm = str(raw or "").strip().lower()
    mapping = {
        "beginner": "초급",
        "intermediate": "중급",
        "advanced": "고급",
    }
    return mapping.get(norm, norm or "미정")


class ScenarioWizardDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("시나리오 마법사")
        self.resize(1080, 740)

        self._templates = list_templates()
        self._current_template: dict[str, Any] | None = None
        self._field_widgets: dict[str, Any] = {}
        self._field_defs: dict[str, dict[str, Any]] = {}
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
        self.cbScope.currentIndexChanged.connect(self._refresh_template_list)
        self.edSearch = QLineEdit()
        self.edSearch.setPlaceholderText("템플릿 검색 (제목/요약/태그)")
        self.edSearch.textChanged.connect(self._refresh_template_list)
        filter_row.addWidget(QLabel("목록"))
        filter_row.addWidget(self.cbScope)
        filter_row.addWidget(self.edSearch, 1)
        left_layout.addLayout(filter_row)

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

    def _refresh_template_list(self):
        scope = self.cbScope.currentData() or "recommended"
        query = self.edSearch.text().strip().lower()

        self.lstTemplates.clear()
        for template in self._templates:
            if scope == "recommended" and not bool(template.get("recommended")):
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

    def _render_template_meta(self, template: dict[str, Any]):
        lines: list[str] = []
        lines.append(f"제목: {template.get('title', '')}")
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
            return

        template_id = str(current.data(Qt.UserRole) or "")
        template = get_template(template_id)
        self._current_template = template
        self._clear_form()

        if template is None:
            self.txtTemplateMeta.setPlainText("선택한 템플릿을 불러올 수 없습니다.")
            self.lblValidation.setText("템플릿 로딩 실패")
            self.btnApply.setEnabled(False)
            return

        self._render_template_meta(template)
        for field in template.get("fields", []):
            self._add_field(field)
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

    def _add_field(self, field: dict[str, Any]):
        name = str(field.get("name", "")).strip()
        if not name:
            return
        label = str(field.get("label") or name)
        ftype = str(field.get("type", "str"))
        default = field.get("default")

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

    def _refresh_preview(self):
        if not self._current_template:
            self.btnApply.setEnabled(False)
            return

        template_id = str(self._current_template.get("id") or "")
        planned = plan_template(template_id, self._collect_values())
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

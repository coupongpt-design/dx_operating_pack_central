import logging
from PyQt5.QtWidgets import (
    QListWidget, QListWidgetItem, QMenu, QAbstractItemView,
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QRubberBand, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QPen, QPolygon
from ..core.models import StepData
from ..utils.common import hk_pretty

LOGGER = logging.getLogger(__name__)

class StepItemWidget(QWidget):
    def __init__(self, step: StepData, index: int, parent=None, flow_hint: str = "", excel_preview: str = ""):
        super().__init__(parent)
        self.step = step
        self.index = index
        self.flow_hint = str(flow_hint or "")
        self.excel_preview = str(excel_preview or "")
        self._active = False
        self._failed = False
        self.setObjectName("stepItemWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()
        self._apply_state_style()
        self._editing = False

    def _init_ui(self):
        layout = QHBoxLayout(self)
        # Keep a left lane for flow arrows rendered by StepList.
        layout.setContentsMargins(16, 5, 5, 5)
        layout.setSpacing(10)

        # Icon Area
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setStyleSheet(f"""
            background-color: {self._get_icon_color()};
            color: white;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
        """)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setText(str(self.index))
        layout.addWidget(self.icon_label)

        # Text Area
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.title_label = QLabel(self.step.name)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #ddd;")

        self.title_edit = QLineEdit(self.step.name)
        # Slightly taller with more padding so text isn't vertically clipped during edit
        self.title_edit.setStyleSheet("font-weight: bold; font-size: 13px; color: #ddd; padding: 6px;")
        self.title_edit.setFixedHeight(32)
        self.title_edit.hide()
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.title_edit)
        
        desc = self._get_description()
        self.desc_label = QLabel(desc)
        self.desc_label.setStyleSheet("font-size: 11px; color: #888;")
        text_layout.addWidget(self.desc_label)

        self.flow_label = QLabel(self.flow_hint)
        self.flow_label.setStyleSheet("font-size: 11px; color: #8fb3d9;")
        self.flow_label.setWordWrap(True)
        self.flow_label.setVisible(bool(self.flow_hint))
        text_layout.addWidget(self.flow_label)

        self.preview_label = QLabel(self.excel_preview)
        self.preview_label.setStyleSheet("font-size: 11px; color: #8a8a8a;")
        self.preview_label.setWordWrap(True)
        self.preview_label.setVisible(bool(self.excel_preview))
        text_layout.addWidget(self.preview_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Type Badge (Optional)
        type_label = QLabel(self.step.type.replace("_", " ").upper())
        type_label.setStyleSheet("font-size: 10px; color: #666; background: #222; padding: 2px 4px; border-radius: 2px;")
        layout.addWidget(type_label)

    def _apply_state_style(self):
        if self._failed and self._active:
            style = (
                "#stepItemWidget {"
                "background-color: #3a1f24;"
                "border: 1px solid #d94a4a;"
                "border-radius: 6px;"
                "}"
            )
        elif self._failed:
            style = (
                "#stepItemWidget {"
                "background-color: #2f1a1f;"
                "border: 1px solid #a33a3a;"
                "border-radius: 6px;"
                "}"
            )
        elif self._active:
            style = (
                "#stepItemWidget {"
                "background-color: #1f2a3a;"
                "border: 1px solid #2b5a88;"
                "border-radius: 6px;"
                "}"
            )
        else:
            style = (
                "#stepItemWidget {"
                "background-color: transparent;"
                "border: 1px solid transparent;"
                "border-radius: 6px;"
                "}"
            )
        self.setStyleSheet(style)

    def set_active(self, active: bool):
        active = bool(active)
        if self._active == active:
            return
        self._active = active
        self._apply_state_style()

    def set_failed(self, failed: bool):
        failed = bool(failed)
        if self._failed == failed:
            return
        self._failed = failed
        self._apply_state_style()

    def _get_icon_color(self):
        # Color coding based on step type
        if self.step.type == "image_click": return "#007ACC" # Blue
        if self.step.type == "wait_for_image": return "#4FC3F7" # Light Blue
        if self.step.type == "key": return "#D16D6D" # Reddish
        if self.step.type == "comment": return "#6A9955" # Green
        if self.step.type == "start_loop": return "#C586C0" # Purple
        if self.step.type == "image_branch": return "#D7BA7D" # Yellow
        return "#444"

    def _get_description(self):
        if self.step.type == "image_click":
            return "Find image & Click"
        if self.step.type == "wait_for_image":
            return "Wait until image appears"
        if self.step.type == "text":
            return f"Paste text '{(self.step.key_string or '')}'"
        if self.step.type == "key":
            pretty = hk_pretty(self.step.key_string) if self.step.key_string else ""
            return f"Press {pretty or (self.step.key_string or '')}"
        if self.step.type == "comment":
            return getattr(self.step, "comment", None) or "No content"
        return self.step.type

class StepList(QListWidget):
    requestEdit = pyqtSignal(int)
    requestDelete = pyqtSignal(int)
    requestDuplicate = pyqtSignal(int)
    requestDuplicateMany = pyqtSignal(list)
    requestDeleteMany = pyqtSignal(list)
    requestConvertToBranch = pyqtSignal(int)
    requestRunFrom = pyqtSignal(int)
    requestRename = pyqtSignal(int, str)
    orderChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(self.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(self.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAlternatingRowColors(False) # Custom widget handles colors
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)
        self.setSpacing(2) # Gap between cards
        try:
            self.setEditTriggers(QAbstractItemView.NoEditTriggers) # Disable default editing
        except Exception as e:
            LOGGER.debug("Failed to disable list edit triggers (non-fatal): %s", e)
        self._rubber_band = None
        self._rubber_origin = None
        self._rubber_toggle = False
        self._rubber_active = False
        self._inline_edit_item = None
        self._active_row = None
        self._failed_row = None
        self._flow_edges = []
        self._flow_colors = {
            "jump_true": QColor("#4FC3F7"),
            "jump_false": QColor("#FFB74D"),
            "branch_true": QColor("#81C784"),
            "branch_false": QColor("#E57373"),
            "loop_back": QColor("#BA68C8"),
        }

    def _calc_item_height(self, flow_hint: str = "", excel_preview: str = "") -> int:
        height = 50
        if str(flow_hint or "").strip():
            height += 16
        if str(excel_preview or "").strip():
            height += 16
        return max(50, height)

    def add_step_item(self, step: StepData, flow_hint: str = "", excel_preview: str = "", tooltip: str = ""):
        item = QListWidgetItem(self)
        item.setSizeHint(QSize(0, self._calc_item_height(flow_hint, excel_preview)))
        item.setData(Qt.UserRole, step)
        if tooltip:
            item.setToolTip(str(tooltip))
        self.addItem(item)
        
        # Create widget
        idx = self.count()
        widget = StepItemWidget(step, idx, flow_hint=flow_hint, excel_preview=excel_preview)
        widget.title_label.mousePressEvent = lambda e, it=item: self._begin_inline_edit(it)
        widget.title_edit.editingFinished.connect(lambda it=item, w=widget: self._finish_inline_edit(it, w))
        widget.title_edit.returnPressed.connect(lambda it=item, w=widget: self._finish_inline_edit(it, w))
        self.setItemWidget(item, widget)

    def refresh_indices(self):
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if widget:
                widget.index = i + 1
                widget.icon_label.setText(str(i + 1))

    def set_flow_edges(self, edges):
        safe_edges = []
        for e in edges or []:
            if not isinstance(e, (tuple, list)) or len(e) < 2:
                continue
            src = int(e[0])
            dst = int(e[1])
            kind = str(e[2]) if len(e) >= 3 else "jump_true"
            if src < 0 or dst < 0:
                continue
            safe_edges.append((src, dst, kind))
        self._flow_edges = safe_edges
        self.viewport().update()

    def set_active_index(self, idx: int | None):
        prev = self._active_row
        if prev is not None and 0 <= prev < self.count():
            item = self.item(prev)
            widget = self.itemWidget(item)
            if hasattr(widget, "set_active"):
                widget.set_active(False)
        self._active_row = idx if idx is not None else None
        if idx is None:
            return
        if 0 <= idx < self.count():
            item = self.item(idx)
            widget = self.itemWidget(item)
            if hasattr(widget, "set_active"):
                widget.set_active(True)

    def set_failed_index(self, idx: int | None):
        prev = self._failed_row
        if prev is not None and 0 <= prev < self.count():
            item = self.item(prev)
            widget = self.itemWidget(item)
            if hasattr(widget, "set_failed"):
                widget.set_failed(False)
        self._failed_row = idx if idx is not None else None
        if idx is None:
            return
        if 0 <= idx < self.count():
            item = self.item(idx)
            widget = self.itemWidget(item)
            if hasattr(widget, "set_failed"):
                widget.set_failed(True)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.refresh_indices()
        self.viewport().update()
        self.orderChanged.emit()
        self._inline_edit_item = None

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._flow_edges:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, True)
        lane_base_x = 7
        lane_step_x = 6
        edge_count = max(1, len(self._flow_edges))

        for edge_idx, (src, dst, kind) in enumerate(self._flow_edges):
            if src >= self.count() or dst >= self.count():
                continue
            src_item = self.item(src)
            dst_item = self.item(dst)
            if src_item is None or dst_item is None:
                continue
            src_rect = self.visualItemRect(src_item)
            dst_rect = self.visualItemRect(dst_item)
            if src_rect.isNull() or dst_rect.isNull():
                continue
            if src_rect.bottom() < 0 and dst_rect.bottom() < 0:
                continue
            if src_rect.top() > self.viewport().height() and dst_rect.top() > self.viewport().height():
                continue

            start_y = src_rect.center().y()
            end_y = dst_rect.center().y()
            lane_x = lane_base_x + (edge_idx % min(6, edge_count)) * lane_step_x
            color = self._flow_colors.get(kind, QColor("#8FB3D9"))
            pen = QPen(color, 1.8)
            painter.setPen(pen)

            if src == dst:
                loop_rect = QRect(lane_x - 6, start_y - 6, 12, 12)
                painter.drawEllipse(loop_rect)
                continue

            painter.drawLine(lane_x, start_y, lane_x, end_y)
            arrow_dir = 1 if end_y >= start_y else -1
            tip = QPoint(lane_x, end_y)
            left = QPoint(lane_x - 4, end_y - 6 * arrow_dir)
            right = QPoint(lane_x + 4, end_y - 6 * arrow_dir)
            painter.setBrush(color)
            painter.drawPolygon(QPolygon([tip, left, right]))

    def show_menu(self, pos):
        it = self.itemAt(pos)
        if not it:
            return
        idx = self.row(it)
        s: StepData = it.data(Qt.UserRole)
        sel_items = self.selectedItems()
        sel_rows = sorted({self.row(x) for x in sel_items})
        
        menu = QMenu(self)
        aRunFrom = menu.addAction("Run from here")
        aRunFrom.triggered.connect(lambda: self.requestRunFrom.emit(idx))
        menu.addSeparator()
        
        aEdit = menu.addAction("Edit")
        aEdit.triggered.connect(lambda: self.requestEdit.emit(idx))
        
        if len(sel_rows) > 1:
            aDupMany = menu.addAction(f"Duplicate Selected ({len(sel_rows)})")
            aDupMany.triggered.connect(lambda: self.requestDuplicateMany.emit(sel_rows))
            aDelMany = menu.addAction(f"Delete Selected ({len(sel_rows)})")
            aDelMany.triggered.connect(lambda: self.requestDeleteMany.emit(sel_rows))
        else:
            aDup = menu.addAction("Duplicate")
            aDup.triggered.connect(lambda: self.requestDuplicate.emit(idx))
            aDel = menu.addAction("Delete")
            aDel.triggered.connect(lambda: self.requestDelete.emit(idx))
            
        menu.addSeparator()
        if s and getattr(s, 'type', None) == 'image_click':
            aConvert = menu.addAction("Convert to Branch Step")
            aConvert.triggered.connect(lambda: self.requestConvertToBranch.emit(idx))
            
        menu.exec_(self.viewport().mapToGlobal(pos))

    def _start_rubber_band(self, pos, toggle_mode):
        self._rubber_origin = pos
        self._rubber_toggle = toggle_mode
        if self._rubber_band is None:
            self._rubber_band = QRubberBand(QRubberBand.Rectangle, self.viewport())
        self._rubber_band.setGeometry(QRect(pos, pos))
        self._rubber_band.show()
        self._rubber_active = True

    def _finish_rubber_band(self):
        if self._rubber_band:
            self._rubber_band.hide()
        self._rubber_active = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if item is None or (event.modifiers() & Qt.ControlModifier):
                self._start_rubber_band(event.pos(), bool(event.modifiers() & Qt.ControlModifier))
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._rubber_active and self._rubber_band:
            rect = QRect(self._rubber_origin, event.pos()).normalized()
            self._rubber_band.setGeometry(rect)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._rubber_active and self._rubber_band:
            self._apply_rubber_selection()
            self._finish_rubber_band()
            return
        super().mouseReleaseEvent(event)

    def _apply_rubber_selection(self):
        if not self._rubber_band:
            return
        rect = self._rubber_band.geometry()
        if rect.width() < 2 and rect.height() < 2:
            if not self._rubber_toggle:
                self.clearSelection()
            return
        if not self._rubber_toggle:
            self.clearSelection()
        for i in range(self.count()):
            item = self.item(i)
            item_rect = self.visualItemRect(item)
            if rect.intersects(item_rect):
                if self._rubber_toggle and item.isSelected():
                    item.setSelected(False)
                else:
                    item.setSelected(True)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            sel_items = self.selectedItems()
            rows = sorted({self.row(it) for it in sel_items})
            if not rows:
                return
            if len(rows) == 1:
                self.requestDelete.emit(rows[0])
            else:
                self.requestDeleteMany.emit(rows)
            return
        if event.key() == Qt.Key_F2:
            it = self.currentItem()
            if it:
                self._begin_inline_edit(it)
            return
        super().keyPressEvent(event)

    # --- Inline rename helpers ---
    def _begin_inline_edit(self, item: QListWidgetItem):
        if item is None:
            return
        widget: StepItemWidget = self.itemWidget(item)
        if not widget:
            return
        self._inline_edit_item = item
        widget.title_label.hide()
        if hasattr(widget, "desc_label"):
            widget.desc_label.hide()
        widget.title_edit.setText(widget.step.name)
        widget.title_edit.show()
        widget.title_edit.setFocus()
        widget.title_edit.selectAll()

    def _finish_inline_edit(self, item: QListWidgetItem, widget: StepItemWidget):
        if item is None or widget is None:
            return
        new_name = widget.title_edit.text().strip()
        old_name = getattr(widget.step, "name", "")
        widget.title_edit.hide()
        widget.title_label.show()
        if hasattr(widget, "desc_label"):
            widget.desc_label.show()
        self._inline_edit_item = None
        if not new_name or new_name == old_name:
            widget.title_label.setText(old_name)
            return
        widget.title_label.setText(new_name)
        self.requestRename.emit(self.row(item), new_name)

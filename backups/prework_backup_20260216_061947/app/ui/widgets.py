import logging
from PyQt5.QtWidgets import (
    QListWidget, QListWidgetItem, QMenu, QAbstractItemView,
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QRubberBand, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from ..core.models import StepData
from ..utils.common import hk_pretty

LOGGER = logging.getLogger(__name__)

class StepItemWidget(QWidget):
    def __init__(self, step: StepData, index: int, parent=None):
        super().__init__(parent)
        self.step = step
        self.index = index
        self._active = False
        self.setObjectName("stepItemWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()
        self._apply_active_style()
        self._editing = False

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
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
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Type Badge (Optional)
        type_label = QLabel(self.step.type.replace("_", " ").upper())
        type_label.setStyleSheet("font-size: 10px; color: #666; background: #222; padding: 2px 4px; border-radius: 2px;")
        layout.addWidget(type_label)

    def _apply_active_style(self):
        if self._active:
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
        self._apply_active_style()

    def _get_icon_color(self):
        # Color coding based on step type
        if self.step.type == "image_click": return "#007ACC" # Blue
        if self.step.type == "key": return "#D16D6D" # Reddish
        if self.step.type == "comment": return "#6A9955" # Green
        if self.step.type == "start_loop": return "#C586C0" # Purple
        if self.step.type == "image_branch": return "#D7BA7D" # Yellow
        return "#444"

    def _get_description(self):
        if self.step.type == "image_click":
            return "Find image & Click"
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

    def add_step_item(self, step: StepData):
        item = QListWidgetItem(self)
        item.setSizeHint(QSize(0, 50)) # Fixed height for card
        item.setData(Qt.UserRole, step)
        self.addItem(item)
        
        # Create widget
        idx = self.count()
        widget = StepItemWidget(step, idx)
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

    def dropEvent(self, event):
        super().dropEvent(event)
        self.refresh_indices()
        self.orderChanged.emit()
        self._inline_edit_item = None

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

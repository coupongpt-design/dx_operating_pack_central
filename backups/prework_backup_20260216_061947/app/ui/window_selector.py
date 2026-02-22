from typing import List, Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QDialogButtonBox,
)

from app.core.window_manager import WindowManager


class WindowSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Window")
        self.resize(420, 400)
        self.window_manager = WindowManager()
        self.full_list: List[Dict] = []
        self.selected_title: Optional[str] = None

        layout = QVBoxLayout(self)

        # Filter input
        self.edFilter = QLineEdit(self)
        self.edFilter.setPlaceholderText("Filter (e.g., !chrome, proc:game.exe)")
        self.edFilter.textChanged.connect(self._apply_filter)

        # List
        self.list = QListWidget(self)
        self.list.itemDoubleClicked.connect(self._accept_selection)

        # Buttons
        btn_refresh = QPushButton("Refresh", self)
        btn_refresh.clicked.connect(self._refresh_list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)

        layout.addWidget(self.edFilter)
        layout.addWidget(self.list)
        h = QHBoxLayout()
        h.addWidget(btn_refresh)
        h.addStretch(1)
        layout.addLayout(h)
        layout.addWidget(buttons)

        self._refresh_list()

    def _refresh_list(self):
        self.full_list = self.window_manager.get_window_list()
        self._apply_filter()

    def _apply_filter(self):
        filter_text = self.edFilter.text().strip()
        filtered = self.window_manager.filter_windows(self.full_list, filter_text)
        self.list.clear()
        for win in filtered:
            proc = win.get("process_name", "")
            title = win.get("title", "")
            item = QListWidgetItem(f"[{proc}] {title}")
            item.setData(Qt.UserRole, win)
            self.list.addItem(item)

    def _accept_selection(self):
        item = self.list.currentItem()
        if not item:
            self.reject()
            return
        win = item.data(Qt.UserRole)
        self.selected_title = win.get("title", "")
        self.accept()

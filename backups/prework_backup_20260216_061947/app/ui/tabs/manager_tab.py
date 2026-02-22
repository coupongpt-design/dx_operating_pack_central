from __future__ import annotations

import os
import logging
from typing import List

from PyQt5.QtCore import Qt, QTimer, QTime
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from app.core.session_manager import GameSession, SessionManager
from app.ui.window_selector import WindowSelectorDialog


class ManagerTab(QWidget):
    """Multi-Client Session Manager (Round-Robin)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(__name__ + ".ManagerTab")
        self.manager = SessionManager(self)
        self.sessions: List[GameSession] = []
        self._build_ui()
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(500)
        self._status_timer.timeout.connect(self._refresh_table_status)
        self._status_timer.start()

    # UI -----------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter)

        # Left panel -----------------------------------------------------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["Name", "Target", "Script", "Status"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        btn_row = QHBoxLayout()
        self.btnAdd = QPushButton("Add Session")
        self.btnDel = QPushButton("Remove")
        self.btnDup = QPushButton("Duplicate")
        btn_row.addWidget(self.btnAdd)
        btn_row.addWidget(self.btnDel)
        btn_row.addWidget(self.btnDup)
        left_layout.addWidget(self.tbl)
        left_layout.addLayout(btn_row)
        splitter.addWidget(left)

        # Right panel ----------------------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)

        form = QVBoxLayout()
        # Name
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Name"))
        self.edName = QLineEdit()
        row_name.addWidget(self.edName)
        form.addLayout(row_name)
        # Target
        row_target = QHBoxLayout()
        row_target.addWidget(QLabel("Target Window"))
        self.edTarget = QLineEdit()
        self.btnTargetPick = QPushButton("...")
        self.btnTargetPick.setFixedWidth(32)
        row_target.addWidget(self.edTarget)
        row_target.addWidget(self.btnTargetPick)
        form.addLayout(row_target)
        # Script
        row_script = QHBoxLayout()
        row_script.addWidget(QLabel("Script Path"))
        self.edScript = QLineEdit()
        self.btnBrowse = QPushButton("Browse")
        row_script.addWidget(self.edScript)
        row_script.addWidget(self.btnBrowse)
        form.addLayout(row_script)
        # Reset group
        reset_group = QGroupBox("Reset Config")
        reset_layout = QHBoxLayout(reset_group)
        reset_layout.addWidget(QLabel("Daily Time"))
        self.timeReset = QTimeEdit()
        self.timeReset.setDisplayFormat("HH:mm")
        self.timeReset.setTime(QTime(4, 0))
        reset_layout.addWidget(self.timeReset)
        reset_layout.addWidget(QLabel("Reset Vars (comma)"))
        self.edResetVars = QLineEdit()
        reset_layout.addWidget(self.edResetVars)
        form.addWidget(reset_group)
        # Save button
        self.btnSave = QPushButton("Save Session")
        form.addWidget(self.btnSave)
        form.addStretch()

        right_layout.addLayout(form)

        # Bottom controls
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Switch Interval (sec):"))
        self.spInterval = QSpinBox()
        self.spInterval.setRange(1, 600)
        self.spInterval.setValue(10)
        bottom.addWidget(self.spInterval)
        self.btnStartAll = QPushButton("Start All")
        self.btnStopAll = QPushButton("Stop All")
        bottom.addWidget(self.btnStartAll)
        bottom.addWidget(self.btnStopAll)
        bottom.addStretch()
        right_layout.addLayout(bottom)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        # Connections
        self.tbl.itemSelectionChanged.connect(self._on_selection_changed)
        self.btnAdd.clicked.connect(self._on_add)
        self.btnDel.clicked.connect(self._on_remove)
        self.btnDup.clicked.connect(self._on_duplicate)
        self.btnBrowse.clicked.connect(self._on_browse)
        self.btnTargetPick.clicked.connect(self._on_pick_target)
        self.btnSave.clicked.connect(self._on_save)
        self.btnStartAll.clicked.connect(self._on_start_all)
        self.btnStopAll.clicked.connect(self._on_stop_all)

    # Helpers ------------------------------------------------------------
    def _on_add(self) -> None:
        sess = GameSession(
            name=self.edName.text() or f"Session {len(self.sessions)+1}",
            target_title=self.edTarget.text(),
            script_path=self.edScript.text(),
            reset_time=self.timeReset.time().toString("HH:mm"),
            reset_vars=self._parse_reset_vars(),
        )
        self.sessions.append(sess)
        self.manager.add_session(sess)
        self._refresh_table()

    def _on_remove(self) -> None:
        row = self.tbl.currentRow()
        if row < 0:
            return
        self.manager.remove_session(row)
        self.sessions.pop(row)
        self._refresh_table()

    def _on_duplicate(self) -> None:
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self.sessions):
            return
        src = self.sessions[row]
        dup = GameSession(
            name=src.name + " Copy",
            target_title=src.target_title,
            script_path=src.script_path,
            reset_time=src.reset_time,
            reset_vars=list(src.reset_vars),
        )
        self.sessions.append(dup)
        self.manager.add_session(dup)
        self._refresh_table()

    def _on_browse(self) -> None:
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Script", "", "GameBot Files (*.json *.macro);;All Files (*)"
        )
        if fname:
            self.edScript.setText(fname)

    def _on_pick_target(self) -> None:
        dlg = WindowSelectorDialog(self)
        if dlg.exec_() == dlg.Accepted:
            title = dlg.selected_title()
            if title:
                self.edTarget.setText(title)

    def _on_save(self) -> None:
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self.sessions):
            QMessageBox.information(self, "Save", "Select a session to save.")
            return
        sess = self.sessions[row]
        sess.name = self.edName.text()
        sess.target_title = self.edTarget.text()
        sess.script_path = self.edScript.text()
        sess.reset_time = self.timeReset.time().toString("HH:mm")
        sess.reset_vars = self._parse_reset_vars()
        self._refresh_table(select_row=row)

    def _on_selection_changed(self) -> None:
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self.sessions):
            return
        sess = self.sessions[row]
        self.edName.setText(sess.name)
        self.edTarget.setText(sess.target_title)
        self.edScript.setText(sess.script_path)
        if sess.reset_time:
            try:
                h, m = map(int, sess.reset_time.split(":"))
                self.timeReset.setTime(QTime(h, m))
            except Exception as e:
                self._logger.warning("Invalid reset_time '%s' in session '%s': %s", sess.reset_time, sess.name, e)
        if isinstance(sess.reset_vars, list):
            self.edResetVars.setText(", ".join(sess.reset_vars))
        else:
            self.edResetVars.setText(str(sess.reset_vars))

    def _on_start_all(self) -> None:
        self.manager.set_interval_sec(self.spInterval.value())
        self.manager.start_rotation()
        self._refresh_table()

    def _on_stop_all(self) -> None:
        self.manager.stop_all()
        self._refresh_table()

    def _refresh_table(self, select_row: int | None = None) -> None:
        self.tbl.setRowCount(len(self.sessions))
        for r, sess in enumerate(self.sessions):
            self.tbl.setItem(r, 0, QTableWidgetItem(sess.name))
            self.tbl.setItem(r, 1, QTableWidgetItem(sess.target_title))
            self.tbl.setItem(r, 2, QTableWidgetItem(sess.script_path))
            self.tbl.setItem(r, 3, QTableWidgetItem(sess.status))
        self.tbl.resizeColumnsToContents()
        if select_row is not None and 0 <= select_row < self.tbl.rowCount():
            self.tbl.selectRow(select_row)

    def _refresh_table_status(self) -> None:
        for r, sess in enumerate(self.sessions):
            item = self.tbl.item(r, 3)
            if item:
                item.setText(sess.status)

    # Utilities ---------------------------------------------------------
    def _parse_reset_vars(self) -> list[str]:
        text = self.edResetVars.text()
        if not text:
            return []
        return [v.strip() for v in text.split(",") if v.strip()]

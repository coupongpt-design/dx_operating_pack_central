from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.run_history import RunSummary, list_run_summaries, load_run_events


def _safe_text(value) -> str:
    return str(value or "").strip()


class ExecutionHistoryDialog(QDialog):
    def __init__(self, parent=None, *, log_dir: str | Path = "logs"):
        super().__init__(parent)
        self.setWindowTitle("실행 이력")
        self.resize(1180, 720)
        self.log_dir = Path(log_dir)
        self._summaries: list[RunSummary] = []

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.lblPath = QLabel(f"Log Dir: {self.log_dir}")
        self.btnRefresh = QPushButton("새로고침")
        self.btnOpenFolder = QPushButton("폴더 열기")
        self.btnClose = QPushButton("닫기")
        self.btnRefresh.clicked.connect(self.refresh_history)
        self.btnOpenFolder.clicked.connect(self._open_log_folder)
        self.btnClose.clicked.connect(self.accept)
        top.addWidget(self.lblPath, 1)
        top.addWidget(self.btnRefresh)
        top.addWidget(self.btnOpenFolder)
        top.addWidget(self.btnClose)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("실행 목록"))
        self.tblRuns = QTableWidget(0, 8)
        self.tblRuns.setHorizontalHeaderLabels(
            ["시작", "상태", "총소요(ms)", "스텝", "실패", "Run ID", "병목 스텝(ms)", "파일"]
        )
        self.tblRuns.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tblRuns.setSelectionBehavior(QTableWidget.SelectRows)
        self.tblRuns.setSelectionMode(QTableWidget.SingleSelection)
        self.tblRuns.verticalHeader().setVisible(False)
        self.tblRuns.itemSelectionChanged.connect(self._on_run_selected)
        left_layout.addWidget(self.tblRuns, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("선택 실행 상세"))

        form = QFormLayout()
        self.lblRunId = QLabel("-")
        self.lblStatus = QLabel("-")
        self.lblDuration = QLabel("-")
        self.lblSteps = QLabel("-")
        self.lblFails = QLabel("-")
        self.lblSlowest = QLabel("-")
        form.addRow("Run ID", self.lblRunId)
        form.addRow("상태", self.lblStatus)
        form.addRow("총 소요(ms)", self.lblDuration)
        form.addRow("스텝 수", self.lblSteps)
        form.addRow("실패 수", self.lblFails)
        form.addRow("병목", self.lblSlowest)
        right_layout.addLayout(form)

        self.tblTimeline = QTableWidget(0, 5)
        self.tblTimeline.setHorizontalHeaderLabels(["시간", "이벤트", "스텝", "지연(ms)", "에러"])
        self.tblTimeline.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tblTimeline.setSelectionBehavior(QTableWidget.SelectRows)
        self.tblTimeline.verticalHeader().setVisible(False)
        right_layout.addWidget(self.tblTimeline, 1)
        splitter.addWidget(right)

        splitter.setSizes([560, 620])
        self.refresh_history()

    def refresh_history(self):
        self._summaries = list_run_summaries(self.log_dir, limit=500)
        self.tblRuns.setRowCount(len(self._summaries))
        for row, summary in enumerate(self._summaries):
            slow = "-"
            if summary.slowest_duration_ms is not None:
                slow = f"{summary.slowest_step_name} ({summary.slowest_duration_ms})"
            cells = [
                _safe_text(summary.started_at),
                _safe_text(summary.status),
                "-" if summary.duration_ms is None else str(summary.duration_ms),
                str(summary.total_steps),
                str(summary.failed_steps),
                _safe_text(summary.run_id),
                slow,
                Path(summary.file_path).name,
            ]
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if col in (2, 3, 4):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tblRuns.setItem(row, col, item)
            self._color_status_row(row, summary.status)

        if self._summaries:
            self.tblRuns.selectRow(0)
            self._on_run_selected()
        else:
            self._clear_details()

    def _color_status_row(self, row: int, status: str):
        color = None
        st = _safe_text(status).lower()
        if st == "failed":
            color = QColor(80, 25, 25)
        elif st == "success":
            color = QColor(25, 60, 25)
        elif st in ("running", "incomplete"):
            color = QColor(70, 60, 25)
        if color is None:
            return
        for col in range(self.tblRuns.columnCount()):
            item = self.tblRuns.item(row, col)
            if item is not None:
                item.setBackground(color)

    def _on_run_selected(self):
        selected = self.tblRuns.selectionModel().selectedRows()
        if not selected:
            self._clear_details()
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._summaries):
            self._clear_details()
            return
        summary = self._summaries[row]
        self.lblRunId.setText(_safe_text(summary.run_id) or "-")
        self.lblStatus.setText(_safe_text(summary.status) or "-")
        self.lblDuration.setText("-" if summary.duration_ms is None else str(summary.duration_ms))
        self.lblSteps.setText(str(summary.total_steps))
        self.lblFails.setText(str(summary.failed_steps))
        if summary.slowest_duration_ms is not None:
            self.lblSlowest.setText(f"{summary.slowest_step_name} ({summary.slowest_duration_ms} ms)")
        else:
            self.lblSlowest.setText("-")
        self._load_timeline(summary.file_path)

    def _load_timeline(self, file_path: str):
        rows = load_run_events(file_path)
        self.tblTimeline.setRowCount(len(rows))
        for row, event in enumerate(rows):
            event_name = _safe_text(event.get("event"))
            step_name = _safe_text(event.get("step_name"))
            step_uuid = _safe_text(event.get("step_uuid"))
            step_text = step_name if step_name else step_uuid
            error = _safe_text(event.get("error"))
            duration = event.get("duration_ms")
            duration_text = "-" if duration is None else str(duration)
            values = [
                _safe_text(event.get("timestamp")),
                event_name,
                step_text,
                duration_text,
                error,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tblTimeline.setItem(row, col, item)

            if event_name in ("step_failed",):
                self._color_timeline_row(row, QColor(85, 25, 25))
            elif event_name == "run_finished" and event.get("success") is False:
                self._color_timeline_row(row, QColor(85, 35, 25))
            elif event_name == "step_succeeded":
                self._color_timeline_row(row, QColor(25, 55, 25))

        if self.tblTimeline.rowCount() > 0:
            self.tblTimeline.scrollToBottom()

    def _color_timeline_row(self, row: int, color: QColor):
        for col in range(self.tblTimeline.columnCount()):
            item = self.tblTimeline.item(row, col)
            if item is not None:
                item.setBackground(color)

    def _clear_details(self):
        self.lblRunId.setText("-")
        self.lblStatus.setText("-")
        self.lblDuration.setText("-")
        self.lblSteps.setText("-")
        self.lblFails.setText("-")
        self.lblSlowest.setText("-")
        self.tblTimeline.setRowCount(0)

    def _open_log_folder(self):
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_dir.resolve())))
        except Exception:
            pass

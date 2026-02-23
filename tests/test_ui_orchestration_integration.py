import os
import sys
import time

import pytest

pytest.importorskip("pytestqt")
from PyQt5.QtWidgets import QApplication

from app.core.models import StepData

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _create_xlsx(path, rows: int):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.cell(row=1, column=1, value="name")
    ws.cell(row=1, column=2, value="text")
    for i in range(rows):
        ws.cell(row=i + 2, column=1, value=f"user-{i}")
        ws.cell(row=i + 2, column=2, value="hello {{name}}")
    wb.save(str(path))
    wb.close()


def _create_xlsx_with_gap(path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.cell(row=1, column=1, value="name")
    ws.cell(row=1, column=2, value="text")
    ws.cell(row=2, column=1, value="user-0")
    ws.cell(row=2, column=2, value="hello {{name}}")
    # row 3 intentionally empty
    ws.cell(row=4, column=1, value="user-1")
    ws.cell(row=4, column=2, value="hello {{name}}")
    ws.cell(row=5, column=1, value="user-2")
    ws.cell(row=5, column=2, value="hello {{name}}")
    wb.save(str(path))
    wb.close()


def _create_xlsx_single_column(path, header: str, values: list[str]):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.cell(row=1, column=1, value=header)
    for i, value in enumerate(values):
        ws.cell(row=i + 2, column=1, value=value)
    wb.save(str(path))
    wb.close()


def _create_xlsx_name_message(path, rows: list[tuple[str, str]]):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.cell(row=1, column=1, value="user_name")
    ws.cell(row=1, column=2, value="message")
    for i, (name, message) in enumerate(rows):
        ws.cell(row=i + 2, column=1, value=name)
        ws.cell(row=i + 2, column=2, value=message)
    wb.save(str(path))
    wb.close()


def test_excel_orchestration_ui_success_flow(monkeypatch, qapp, qtbot, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from pathlib import Path
    from app import main as main_module
    from app.main import MainWindow

    in_xlsx = tmp_path / "input.xlsx"
    _create_xlsx(in_xlsx, rows=3)

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append(text))

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.chkExcelDataMode.setChecked(True)
    win.edExcelDataPath.setText(str(in_xlsx))
    win.spExcelParallelism.setValue(2)

    win._on_run_button_clicked()
    qtbot.waitUntil(lambda: not win._excel_mode_running, timeout=8000)
    out_xlsx = Path(win._excel_output_path)

    assert out_xlsx.exists()
    assert typed == ["hello user-0", "hello user-1", "hello user-2"]
    assert win.act_run.isEnabled() is True
    assert win.act_stop.isEnabled() is False
    assert "ok" in win.lblExcelStatus.text()

    wb = openpyxl.load_workbook(str(out_xlsx), data_only=True)
    try:
        ws = wb.active
        assert ws.cell(row=1, column=3).value == "_status"
        assert ws.cell(row=1, column=4).value == "_error_reason"
        assert ws.cell(row=2, column=3).value == "SUCCESS"
        assert ws.cell(row=3, column=3).value == "SUCCESS"
        assert ws.cell(row=4, column=3).value == "SUCCESS"
    finally:
        wb.close()
    win.close()


def test_excel_orchestration_ui_stop_flow(monkeypatch, qapp, qtbot, tmp_path):
    from pathlib import Path
    from app import main as main_module
    from app.main import MainWindow

    in_xlsx = tmp_path / "input_stop.xlsx"
    _create_xlsx(in_xlsx, rows=20)

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: time.sleep(0.15))

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.chkExcelDataMode.setChecked(True)
    win.edExcelDataPath.setText(str(in_xlsx))
    win.spExcelParallelism.setValue(1)

    win._on_run_button_clicked()
    qtbot.waitUntil(lambda: win._excel_mode_running, timeout=3000)
    qtbot.wait(120)
    win.stop_macro()
    qtbot.waitUntil(lambda: not win._excel_mode_running, timeout=8000)
    out_xlsx = Path(win._excel_output_path)

    assert out_xlsx.exists() is False
    assert win.act_run.isEnabled() is True
    assert win.act_stop.isEnabled() is False
    assert "stopped" in win.lblExcelStatus.text().lower() or "Excel:" in win.lblExcelStatus.text()
    win.close()


def test_excel_orchestration_ui_step_template_fallback(monkeypatch, qapp, qtbot, tmp_path):
    from pathlib import Path
    from app import main as main_module
    from app.main import MainWindow

    in_xlsx = tmp_path / "input_fallback.xlsx"
    _create_xlsx_single_column(in_xlsx, "user_name", ["alice", "bob"])

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append(text))

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.steps = [StepData(id="s1", name="Text", type="text", key_string="{{user_name}}")]

    win.chkExcelDataMode.setChecked(True)
    win.edExcelDataPath.setText(str(in_xlsx))
    win.spExcelParallelism.setValue(1)

    win._on_run_button_clicked()
    qtbot.waitUntil(lambda: not win._excel_mode_running, timeout=8000)
    out_xlsx = Path(win._excel_output_path)

    assert out_xlsx.exists() is True
    assert typed == ["alice", "bob"]
    win.close()


def test_excel_orchestration_ui_template_priority_over_message(monkeypatch, qapp, qtbot, tmp_path):
    from pathlib import Path
    from app import main as main_module
    from app.main import MainWindow

    in_xlsx = tmp_path / "input_template_priority.xlsx"
    _create_xlsx_name_message(
        in_xlsx,
        rows=[
            ("kim", "엑셀 1번 행 데이터입니다."),
            ("lee", "2번 일꾼이 처리 중입니다."),
        ],
    )

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append(text))

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.steps = [StepData(id="s1", name="Text", type="text", key_string="{{USER_NAME}}")]
    win.chkExcelDataMode.setChecked(True)
    win.edExcelDataPath.setText(str(in_xlsx))
    win.spExcelParallelism.setValue(1)

    win._on_run_button_clicked()
    qtbot.waitUntil(lambda: not win._excel_mode_running, timeout=10000)
    out_xlsx = Path(win._excel_output_path)

    assert out_xlsx.exists() is True
    assert typed == ["kim", "lee"]
    win.close()


def test_excel_orchestration_ui_unresolved_template_fails_without_typing(monkeypatch, qapp, qtbot, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from pathlib import Path
    from app import main as main_module
    from app.main import MainWindow

    in_xlsx = tmp_path / "input_unresolved.xlsx"
    _create_xlsx_single_column(in_xlsx, "user_name", ["alice"])

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    typed = []
    monkeypatch.setattr(main_module.pyautogui, "write", lambda text, interval=0.0: typed.append(text))

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.steps = [StepData(id="s1", name="Text", type="text", key_string="{{missing}}")]

    win.chkExcelDataMode.setChecked(True)
    win.edExcelDataPath.setText(str(in_xlsx))
    win.spExcelParallelism.setValue(1)

    win._on_run_button_clicked()
    qtbot.waitUntil(lambda: not win._excel_mode_running, timeout=10000)
    out_xlsx = Path(win._excel_output_path)

    assert typed == []
    assert out_xlsx.exists() is True
    wb = openpyxl.load_workbook(str(out_xlsx), data_only=True)
    try:
        ws = wb.active
        assert ws.cell(row=2, column=2).value == "FAILED"
        assert "unresolved_placeholder" in str(ws.cell(row=2, column=3).value or "")
    finally:
        wb.close()
    win.close()


def test_excel_orchestration_ui_mixed_results_export_integrity(monkeypatch, qapp, qtbot, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from pathlib import Path
    from app import main as main_module
    from app.main import MainWindow

    in_xlsx = tmp_path / "input_mixed.xlsx"
    _create_xlsx_with_gap(in_xlsx)

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    def flaky_write(text, interval=0.0):
        if "user-1" in str(text):
            raise RuntimeError("sim-write-fail")
        return None

    monkeypatch.setattr(main_module.pyautogui, "write", flaky_write)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.chkExcelDataMode.setChecked(True)
    win.edExcelDataPath.setText(str(in_xlsx))
    win.spExcelParallelism.setValue(2)

    win._on_run_button_clicked()
    qtbot.waitUntil(lambda: not win._excel_mode_running, timeout=15000)
    out_xlsx = Path(win._excel_output_path)

    assert out_xlsx.exists() is True
    wb = openpyxl.load_workbook(str(out_xlsx), data_only=True)
    try:
        ws = wb.active
        # Row 2 -> success
        assert ws.cell(row=2, column=3).value == "SUCCESS"
        # Row 3 gap should remain blank
        assert ws.cell(row=3, column=3).value in ("", None)
        # Row 4 -> failed after retries
        assert ws.cell(row=4, column=3).value == "FAILED"
        assert "input_failed" in str(ws.cell(row=4, column=4).value or "")
        # Row 5 -> success
        assert ws.cell(row=5, column=3).value == "SUCCESS"
    finally:
        wb.close()
    win.close()


def test_hotkey_run_follows_excel_mode_branch(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    called = {"excel": 0, "macro": 0}
    monkeypatch.setattr(win, "run_excel_orchestration", lambda: called.__setitem__("excel", called["excel"] + 1))
    monkeypatch.setattr(win, "run_macro", lambda start_index=0: called.__setitem__("macro", called["macro"] + 1))

    win.chkExcelDataMode.setChecked(True)
    win._act_run_from_hotkey()
    assert called == {"excel": 1, "macro": 0}

    win.chkExcelDataMode.setChecked(False)
    win._act_run_from_hotkey()
    assert called == {"excel": 1, "macro": 1}
    win.close()

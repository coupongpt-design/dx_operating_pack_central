import os
import sys

import pytest

pytest.importorskip("pytestqt")
openpyxl = pytest.importorskip("openpyxl")
from PyQt5.QtWidgets import QApplication


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _build_excel(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.cell(row=1, column=1, value="user_name")
    ws.cell(row=1, column=2, value="message")
    ws.cell(row=2, column=1, value="김철수")
    ws.cell(row=2, column=2, value="안녕하세요")
    wb.save(str(path))
    wb.close()


def test_build_step_flow_hint_for_jump_and_loop(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    start = StepData(id="loop_start_1", name="Start", type="start_loop", loop_count=3)
    jump = StepData(id="jump_1", name="Jump", type="jump_if", target_true_id="loop_start_1")
    end = StepData(id="loop_end_1", name="End", type="end_loop", start_loop_id="loop_start_1")
    id_to_index = {"loop_start_1": 0, "jump_1": 1, "loop_end_1": 2}

    start_hint = win._build_step_flow_hint(start, id_to_index)
    jump_hint = win._build_step_flow_hint(jump, id_to_index)
    end_hint = win._build_step_flow_hint(end, id_to_index)

    assert "반복 시작 (3회)" in start_hint
    assert "조건 참 -> #1" in jump_hint
    assert "루프 복귀 -> #1" in end_hint

    win.close()


def test_refresh_step_list_shows_case_insensitive_excel_preview(tmp_path, monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    excel_path = tmp_path / "preview.xlsx"
    _build_excel(excel_path)

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    step = StepData(id="text_1", name="입력", type="text", key_string="{{USER_NAME}}")
    win.steps = [step]
    win.chkExcelDataMode.setChecked(True)
    win.edExcelDataPath.setText(str(excel_path))
    qapp.processEvents()
    win.refresh_step_list()

    item = win.list.item(0)
    assert item is not None
    tooltip = item.toolTip()
    assert "{{USER_NAME}}" in tooltip
    assert "김철수" in tooltip

    widget = win.list.itemWidget(item)
    assert widget is not None
    assert widget.preview_label.isHidden() is False
    assert "김철수" in widget.preview_label.text()

    win.close()


def test_refresh_step_list_builds_flow_edges_for_jump_and_loop(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    step_start = StepData(id="s1", name="Loop Start", type="start_loop", loop_count=2)
    step_jump = StepData(id="j1", name="Jump If", type="jump_if", target_true_id="t1")
    step_target = StepData(id="t1", name="Target", type="comment", comment="ok")
    step_end = StepData(id="e1", name="Loop End", type="end_loop", start_loop_id="s1")
    win.steps = [step_start, step_jump, step_target, step_end]
    win.refresh_step_list()

    assert hasattr(win.list, "_flow_edges")
    edges = set(win.list._flow_edges)
    assert (1, 2, "jump_true", "ok") in edges
    assert (3, 0, "loop_back", "ok") in edges

    win.close()


def test_refresh_step_list_builds_flow_edges_for_step_fail_and_match_routes(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    check = StepData(
        id="w1",
        name="이미지 확인",
        type="wait_for_image",
        on_match_goto_id="ok1",
        branch_on_fail_goto_id="fail1",
    )
    fail = StepData(id="fail1", name="Fail", type="comment", comment="fail")
    ok = StepData(id="ok1", name="OK", type="comment", comment="ok")
    win.steps = [check, fail, ok]
    win.refresh_step_list()

    edges = set(win.list._flow_edges)
    assert (0, 2, "jump_true", "ok") in edges
    assert (0, 1, "jump_false", "ok") in edges

    win.close()

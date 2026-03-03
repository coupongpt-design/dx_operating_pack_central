import os
import sys
from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication

pytest.importorskip("pytestqt")


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _write_excel(path: Path, headers: list[str], rows: list[list[object]]):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    for col, name in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=name)
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=value)
    wb.save(str(path))
    wb.close()


def test_logic_path_simulator_jump_if_path_matches_context():
    from app.core.evaluator import ConditionEvaluator
    from app.core.logic_path_simulator import LogicPathSimulator
    from app.core.models import StepData

    steps = [
        StepData(
            id="j1",
            name="jump",
            type="jump_if",
            condition_var="user_name",
            condition_operator="==",
            condition_value="Kim",
            target_true_id="t1",
        ),
        StepData(id="f1", name="false", type="comment", comment="f"),
        StepData(id="t1", name="true", type="comment", comment="t"),
    ]

    sim_true = LogicPathSimulator(steps, {"user_name": "Kim"}, ConditionEvaluator(), max_hops=10)
    rep_true = sim_true.simulate(start_index=0)
    assert rep_true.visited_indices[:2] == [0, 2]

    sim_false = LogicPathSimulator(steps, {"user_name": "Lee"}, ConditionEvaluator(), max_hops=10)
    rep_false = sim_false.simulate(start_index=0)
    assert rep_false.visited_indices[:3] == [0, 1, 2]


def test_logic_path_simulator_max_hops_guard_on_infinite_loop():
    from app.core.evaluator import ConditionEvaluator
    from app.core.logic_path_simulator import LogicPathSimulator
    from app.core.models import StepData

    steps = [
        StepData(id="loop_1", name="start", type="start_loop", loop_count=0),
        StepData(id="loop_end_1", name="end", type="end_loop", start_loop_id="loop_1"),
    ]
    sim = LogicPathSimulator(steps, {}, ConditionEvaluator(), max_hops=6)
    rep = sim.simulate(start_index=0)
    assert rep.terminated_reason == "max_hops"
    assert len(rep.visited_indices) == 6
    assert any("max_hops" in w for w in rep.warnings)


@pytest.mark.usefixtures("qapp")
def test_main_run_logic_simulation_highlights_expected_path(tmp_path, monkeypatch, qapp, qtbot):
    pytest.importorskip("pytestqt")
    from app.core.models import StepData
    from app.main import MainWindow

    excel_path = tmp_path / "sim_input.xlsx"
    _write_excel(excel_path, ["user_name"], [["Kim"]])

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.steps = [
        StepData(
            id="jump_1",
            name="jump",
            type="jump_if",
            condition_var="user_name",
            condition_operator="==",
            condition_value="Kim",
            target_true_id="target_1",
        ),
        StepData(id="else_1", name="else", type="comment", comment="else"),
        StepData(id="target_1", name="target", type="comment", comment="target"),
    ]
    win.edExcelDataPath.setText(str(excel_path))
    win.refresh_step_list()
    win.run_logic_simulation()

    assert 0 in win._simulated_indices
    assert 2 in win._simulated_indices
    assert 1 not in win._simulated_indices
    assert hasattr(win.list, "_simulated_rows")
    assert 2 in win.list._simulated_rows

    win.close()

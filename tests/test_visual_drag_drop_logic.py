import os
import sys

import pytest

pytest.importorskip("pytestqt")
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


def _edge_set(edges):
    return {tuple(e) for e in (edges or [])}


def test_build_flow_preview_edges_marks_ok_self_jump_and_dangling(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    step_a = StepData(id="a1", name="A", type="jump_if", target_true_id="b1")
    step_b = StepData(id="b1", name="B", type="comment", comment="ok")
    step_c = StepData(id="c1", name="C", type="jump_if", target_true_id="c1")
    step_d = StepData(id="d1", name="D", type="jump_if", target_true_id="missing-id")

    temp_steps = [step_b, step_a, step_c, step_d]
    edges = _edge_set(win._build_flow_preview_edges(temp_steps))

    assert (1, 0, "jump_true", "ok") in edges
    assert (2, 2, "jump_true", "self_jump") in edges
    assert (3, 3, "jump_true", "dangling") in edges

    win.close()


def test_build_flow_preview_edges_uses_cache(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    a = StepData(id="x1", name="X", type="jump_if", target_true_id="x2")
    b = StepData(id="x2", name="Y", type="comment", comment="")
    order = [a, b]

    before = len(win._flow_preview_cache)
    first = win._build_flow_preview_edges(order)
    mid = len(win._flow_preview_cache)
    second = win._build_flow_preview_edges(order)
    after = len(win._flow_preview_cache)

    assert mid == before + 1
    assert after == mid
    assert first == second

    win.close()


def test_flow_preview_request_applies_and_clears_edges(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    step_1 = StepData(id="s1", name="S1", type="jump_if", target_true_id="s2")
    step_2 = StepData(id="s2", name="S2", type="comment", comment="")
    win.steps = [step_1, step_2]
    win.refresh_step_list()

    # Preview as if dragged into reversed row order.
    win._on_flow_preview_requested([1, 0])
    assert win._flow_preview_active is True
    preview_edges = _edge_set(win.list._flow_edges)
    assert (1, 0, "jump_true", "ok") in preview_edges

    # Clear preview should restore stable list-order edges.
    win._on_flow_preview_requested([])
    assert win._flow_preview_active is False
    restored_edges = _edge_set(win.list._flow_edges)
    assert (0, 1, "jump_true", "ok") in restored_edges

    win.close()

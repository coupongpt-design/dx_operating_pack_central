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


def _ids(steps):
    return [str(getattr(s, "id", "") or "") for s in steps]


def test_collect_step_group_detects_wizard_reference_cluster(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    base = StepData(id="base", name="Base", type="comment", comment="")
    loop = StepData(id="wz1", name="WZ 재시도 시작", type="start_loop", loop_count=3)
    check = StepData(
        id="wz2",
        name="WZ 텍스트 확인",
        type="jump_if",
        target_true_id="wz5",
        target_false_id="wz3",
    )
    wait = StepData(id="wz3", name="WZ 재시도 대기", type="wait", wait_ms=500)
    end_loop = StepData(id="wz4", name="WZ 루프 종료", type="end_loop", start_loop_id="wz1")
    tail = StepData(id="wz5", name="WZ 완료", type="comment", comment="WZ anchor")
    out = StepData(id="out1", name="Outside", type="comment", comment="")

    win.steps = [base, loop, check, wait, end_loop, tail, out]
    group = win.collect_step_group(2)
    group_ids = [_ids(win.steps)[i] for i in group]
    assert set(group_ids) == {"wz1", "wz2", "wz3", "wz4", "wz5"}

    win.close()


def test_sync_order_smart_snap_moves_group_and_normalizes_legacy_indices(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    ext_a = StepData(id="extA", name="outside A", type="comment", comment="")
    wz_start = StepData(id="wzA", name="WZ retry start", type="start_loop", loop_count=2)
    wz_jump = StepData(
        id="wzB",
        name="WZ gate",
        type="jump_if",
        target_true_id="wzD",
        target_false_id="extB",
        target_true_index=99,
        target_false_index=99,
        jump_to_index=99,
    )
    wz_wait = StepData(id="wzC", name="WZ wait", type="wait", wait_ms=300)
    wz_end = StepData(id="wzD", name="WZ loop end", type="end_loop", start_loop_id="wzA")
    ext_b = StepData(id="extB", name="outside B", type="comment", comment="")

    win.steps = [ext_a, wz_start, wz_jump, wz_wait, wz_end, ext_b]
    win.refresh_step_list()
    assert win.chkSmartSnap.isChecked() is True

    # Move only one step from the WZ set; smart snap should move the full group block.
    moved = win.list.takeItem(2)  # wz_jump
    win.list.insertItem(5, moved)
    win.list.setCurrentRow(5)
    win.list.orderChanged.emit()

    current_ids = _ids(win.steps)
    group_ids = ["wzA", "wzB", "wzC", "wzD"]
    positions = [current_ids.index(x) for x in group_ids]
    assert positions == list(range(min(positions), max(positions) + 1))
    assert [current_ids[p] for p in positions] == group_ids

    jump_step = next(s for s in win.steps if s.id == "wzB")
    end_idx = current_ids.index("wzD")
    ext_b_idx = current_ids.index("extB")
    assert jump_step.target_true_index == end_idx
    assert jump_step.jump_to_index == end_idx
    assert jump_step.target_false_index == ext_b_idx

    end_step = next(s for s in win.steps if s.id == "wzD")
    assert end_step.start_loop_id == "wzA"

    win.close()


def test_smart_snap_dangling_warning_sets_flow_warning_edges(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    s1 = StepData(id="s1", name="WZ jump", type="jump_if", target_true_id="missing_step")
    s2 = StepData(id="s2", name="WZ note", type="comment", comment="WZ anchor")
    s3 = StepData(id="s3", name="plain", type="comment", comment="")
    win.steps = [s1, s2, s3]
    win.refresh_step_list()

    moved = win.list.takeItem(2)
    win.list.insertItem(0, moved)
    win.list.setCurrentRow(0)
    win.list.orderChanged.emit()

    assert any(len(e) >= 4 and e[3] == "dangling" for e in (win.list._flow_edges or []))

    win.close()

import os
import sys

import pytest

pytest.importorskip("pytestqt")

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication, QDialog

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


def _set_combo_by_data(combo, data):
    idx = combo.findData(data)
    assert idx >= 0
    combo.setCurrentIndex(idx)


def _write_dummy_png(path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    img = np.zeros((16, 16, 3), dtype=np.uint8)
    img[:, :] = (0, 200, 255)
    ok, encoded = cv2.imencode(".png", img)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_conditional_wizard_generates_click_flow(qapp, qtbot):
    from app.ui.dialogs import ConditionalActionWizardDialog

    dlg = ConditionalActionWizardDialog([])
    qtbot.addWidget(dlg)
    dlg.edFindText.setText("완료")
    dlg.spClickX.setValue(120)
    dlg.spClickY.setValue(340)

    steps = dlg.build_steps()
    assert [s.type for s in steps] == ["ocr_jump_if", "jump_if", "click_point", "comment"]

    check, route, click, tail = steps
    assert check.target_true_id == click.id
    assert check.condition_value == "완료"
    assert route.condition_var == "__wiz_gate__"
    assert route.condition_operator == "!="
    assert route.condition_value == "__WIZ_SENTINEL__"
    assert route.target_true_id == tail.id
    assert click.click_x == 120
    assert click.click_y == 340


def test_conditional_wizard_generates_jump_targets(qapp, qtbot):
    from app.core.models import StepData
    from app.ui.dialogs import ConditionalActionWizardDialog

    target_ok = StepData(id="ok01", name="Success Target", type="comment", comment="")
    target_fail = StepData(id="fail01", name="Fail Target", type="comment", comment="")
    dlg = ConditionalActionWizardDialog([target_ok, target_fail])
    qtbot.addWidget(dlg)

    dlg.edFindText.setText("START")
    _set_combo_by_data(dlg.cbSuccessAction, "jump_target")
    _set_combo_by_data(dlg.cbFailAction, "jump_target")
    _set_combo_by_data(dlg.cbSuccessTarget, "ok01")
    _set_combo_by_data(dlg.cbFailTarget, "fail01")

    steps = dlg.build_steps()
    assert [s.type for s in steps] == ["ocr_jump_if", "jump_if", "comment"]
    assert steps[0].target_true_id == "ok01"
    assert steps[1].target_true_id == "fail01"


def test_conditional_wizard_generated_steps_compatible_with_addsteps_command(qapp, qtbot):
    from app.core.commands import AddStepsCommand, UndoStack
    from app.core.models import StepData
    from app.ui.dialogs import ConditionalActionWizardDialog

    scenario_steps = [StepData(id="base1", name="Base", type="comment", comment="base")]
    dlg = ConditionalActionWizardDialog(scenario_steps)
    qtbot.addWidget(dlg)
    dlg.edFindText.setText("READY")
    generated = dlg.build_steps()

    cmd = AddStepsCommand(scenario_steps, generated, index=1)
    stack = UndoStack()
    stack.push(cmd)
    assert len(scenario_steps) == 1 + len(generated)
    assert scenario_steps[1].id == generated[0].id
    assert scenario_steps[-1].type == "comment"
    stack.undo()
    assert [s.id for s in scenario_steps] == ["base1"]


def test_conditional_wizard_generates_retry_then_stop_flow(qapp, qtbot):
    from app.ui.dialogs import ConditionalActionWizardDialog

    dlg = ConditionalActionWizardDialog([])
    qtbot.addWidget(dlg)
    _set_combo_by_data(dlg.cbIntent, "ocr_retry_then_stop")
    dlg.edFindText.setText("READY")
    dlg.spRetryCount.setValue(4)
    dlg.spRetryDelayMs.setValue(700)

    steps = dlg.build_steps()
    assert [s.type for s in steps] == ["start_loop", "ocr_check_text", "wait", "end_loop", "ocr_check_text", "comment"]

    loop, check, wait, end_loop, fail_stop, success = steps
    assert loop.loop_count == 4
    assert check.ocr_expected_text == "READY"
    assert check.branch_on_fail_goto_id == wait.id
    assert check.on_match_goto_id == success.id
    assert wait.wait_ms == 700
    assert end_loop.start_loop_id == loop.id
    assert fail_stop.type == "ocr_check_text"


def test_conditional_wizard_generates_image_check_flow(tmp_path, qapp, qtbot):
    from app.ui.dialogs import ConditionalActionWizardDialog

    image_path = tmp_path / "wizard_target.png"
    _write_dummy_png(image_path)

    dlg = ConditionalActionWizardDialog([])
    qtbot.addWidget(dlg)
    _set_combo_by_data(dlg.cbIntent, "image_check_then_click_branch")
    dlg.edImagePath.setText(str(image_path))
    dlg.spImageTimeoutMs.setValue(3200)
    dlg.spClickX.setValue(64)
    dlg.spClickY.setValue(128)

    steps = dlg.build_steps()
    assert [s.type for s in steps] == ["wait_for_image", "click_point", "comment"]

    check, click, tail = steps
    assert check.anchor_image_path == str(image_path)
    assert check.on_match_goto_id == click.id
    assert check.branch_on_fail_goto_id == tail.id
    assert check.timeout_ms == 3200
    assert click.click_x == 64
    assert click.click_y == 128


def test_conditional_wizard_pick_click_accepts_qpoint(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_select_point(*_args, **_kwargs):
        return QPoint(41, 52)

    monkeypatch.setattr(dialogs, "safe_select_point", fake_select_point)
    dlg = dialogs.ConditionalActionWizardDialog([])
    qtbot.addWidget(dlg)

    dlg._on_pick_click()

    assert dlg.spClickX.value() == 41
    assert dlg.spClickY.value() == 52


def test_main_conditional_wizard_button_inserts_steps(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    class DummyConditionalWizard:
        Accepted = QDialog.Accepted

        def __init__(self, all_steps, parent=None):
            self.parent = parent

        def exec_(self):
            return self.Accepted

        def build_steps(self):
            return [StepData(id="cw1", name="Generated by Wizard", type="comment", comment="cw")]

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.ConditionalActionWizardDialog", DummyConditionalWizard)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    assert hasattr(win, "btnConditionalWizard")
    assert len(win.steps) == 0
    qtbot.mouseClick(win.btnConditionalWizard, Qt.LeftButton)

    assert len(win.steps) == 1
    assert win.steps[0].id == "cw1"
    win.close()

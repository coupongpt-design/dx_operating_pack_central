import os
import sys
import types

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.models import StepData, RepeatConfig  # noqa: E402
from app.core.runner import MacroRunner  # noqa: E402
from app.ui.dialogs import BranchStepDialog  # noqa: E402


def test_runner_variable_branch_true_false(monkeypatch):
    """_image_branch should honor branch_mode='variable' and use compare_condition."""
    # Build a branch step with variable mode
    branch = StepData(
        id="b1",
        name="Branch",
        type="image_branch",
        branch_mode="variable",
        branch_var="hp",
        branch_op="<",
        branch_value=50,
        branch_true_goto_id="T",
        branch_false_goto_id="F",
        conditional_targets=[],
    )
    runner = MacroRunner([branch], repeat=RepeatConfig(repeat_count=1), dry_run=True)
    # Inject context value
    runner.variable_context["hp"] = 20
    ok, goto = runner._image_branch(None, None, branch)
    assert ok is True
    assert goto == "T"
    # False path
    runner.variable_context["hp"] = 80
    ok, goto = runner._image_branch(None, None, branch)
    assert ok is True
    assert goto == "F"


def test_runner_variable_branch_ocr(monkeypatch):
    class DummyGrab:
        def __init__(self, width: int, height: int):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class DummyMSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 10, "height": 10}]

        def grab(self, region):
            return DummyGrab(region["width"], region["height"])

    branch = StepData(
        id="b2",
        name="Branch OCR",
        type="image_branch",
        branch_mode="variable",
        branch_value_source="ocr",
        branch_op="<",
        branch_value=50,
        target_true_id="T",
        target_false_id="F",
        ocr_roi_x=0,
        ocr_roi_y=0,
        ocr_roi_w=5,
        ocr_roi_h=5,
    )
    runner = MacroRunner([branch], repeat=RepeatConfig(repeat_count=1), dry_run=True)

    vals = [40, 60]

    def fake_extract(self, img, psm_mode=6):
        return vals.pop(0)

    monkeypatch.setattr("app.core.runner.ImageProcessor.extract_number", fake_extract, raising=False)

    sct = DummyMSS()
    mon = sct.monitors[0]
    ok, goto = runner._image_branch(sct, mon, branch)
    assert ok is True
    assert goto == "T"
    ok, goto = runner._image_branch(sct, mon, branch)
    assert ok is True
    assert goto == "F"


def test_branch_dialog_saves_variable_mode(qtbot):
    """BranchStepDialog should save branch_mode and variable fields when variable tab is selected."""
    # Prepare steps for target lists
    s1 = StepData(id="s1", name="Step1", type="comment")
    s2 = StepData(id="s2", name="Step2", type="comment")
    all_steps = [s1, s2]
    step = StepData(id="b1", name="Branch", type="image_branch", conditional_targets=[])

    dlg = BranchStepDialog(step, all_steps)
    qtbot.addWidget(dlg)
    # Switch to Variable Logic tab
    dlg.tabs.setCurrentIndex(1)
    dlg.cbVarName.setCurrentText("hp")
    dlg.cbVarOp.setCurrentText("미만 (<)")
    dlg.edVarValue.setText("100")
    dlg.cbBranchTrue.setCurrentIndex(1)  # s1
    dlg.cbBranchFalse.setCurrentIndex(2)  # s2

    dlg.accept()
    saved = dlg.get_step_data()
    assert saved.branch_mode == "variable"
    assert saved.branch_var == "hp"
    assert saved.branch_op in ("<", "미만 (<)")  # stored as symbol via currentData
    assert saved.branch_value == 100.0
    assert saved.branch_true_goto_id == "s1"
    assert saved.branch_false_goto_id == "s2"

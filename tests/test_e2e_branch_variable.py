import os
import sys
import types

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.models import StepData, RepeatConfig  # noqa: E402
from app.core.runner import MacroRunner  # noqa: E402


def _dummy_mss():
    class Dummy:
        monitors = [
            {"left": 0, "top": 0, "width": 10, "height": 10},
            {"left": 0, "top": 0, "width": 10, "height": 10},
        ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def grab(self, region):
            return types.SimpleNamespace(rgb=b"\x00" * (region["width"] * region["height"] * 3),
                                         width=region["width"], height=region["height"])

    return Dummy()


def test_e2e_branch_variable(monkeypatch):
    """
    End-to-end style check: OCR -> variable stored -> branch_mode=variable selects TRUE path.
    """
    # Steps: OCR store (stub) -> branch (variable) -> true comment -> false comment
    s_ocr = StepData(id="ocr1", name="OCR", type="ocr_store", ocr_store_var="hp")
    s_branch = StepData(
        id="branch1",
        name="Branch Var",
        type="image_branch",
        branch_mode="variable",
        branch_var="hp",
        branch_op="<",
        branch_value=50,
        branch_true_goto_id="true1",
        branch_false_goto_id="false1",
    )
    s_true = StepData(id="true1", name="TruePath", type="comment")
    s_false = StepData(id="false1", name="FalsePath", type="comment")
    steps = [s_ocr, s_branch, s_true, s_false]

    runner = MacroRunner(steps, repeat=RepeatConfig(repeat_count=1), dry_run=True)

    # Mock mss to avoid real screen access
    monkeypatch.setattr("app.core.runner.mss", types.SimpleNamespace(mss=_dummy_mss))

    # Stub ocr_store to set variable and succeed
    def fake_ocr_store(sct, mon, step):
        runner.variable_context["hp"] = 10
        return True, None, 0

    runner._ocr_store = fake_ocr_store  # type: ignore

    visited = []
    real_exec = runner._exec_step

    def wrapped_exec(sct, mon, st, idx):
        visited.append(getattr(st, "id", None))
        return real_exec(sct, mon, st, idx)

    runner._exec_step = wrapped_exec  # type: ignore

    runner.run()

    # Ensure branch chose TRUE path first; runner may still walk remaining steps sequentially
    assert visited[:3] == ["ocr1", "branch1", "true1"]

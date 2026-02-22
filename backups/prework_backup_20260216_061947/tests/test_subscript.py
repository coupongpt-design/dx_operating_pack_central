import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.runner import MacroRunner
from app.core.models import StepData, RepeatConfig


def _write_macro(path, steps):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"steps": steps}, f)


def test_subscript_execution_order(tmp_path):
    parent_path = tmp_path / "parent.json"
    child_path = tmp_path / "child.json"

    parent_steps = [
        {"id": "p1", "name": "Start", "type": "comment"},
        {"id": "p2", "name": "Run Child", "type": "run_macro", "target_macro_path": str(child_path)},
        {"id": "p3", "name": "End", "type": "comment"},
    ]
    child_steps = [
        {"id": "c1", "name": "Child Work", "type": "comment"},
        {"id": "c2", "name": "Set Var", "type": "ocr_store", "ocr_store_var": "child_done", "ocr_roi_w": 0, "ocr_roi_h": 0},
    ]

    _write_macro(parent_path, parent_steps)
    _write_macro(child_path, child_steps)

    logs = []

    # Stub ocr_store to set var directly
    def fake_ocr_store(sct, mon, step):
        runner.variable_context["child_done"] = 1
        logs.append("Child Work")
        return True

    runner = MacroRunner([], repeat=RepeatConfig(repeat_count=1), dry_run=True, current_file_path=str(parent_path))
    runner.steps = [StepData(**d) for d in parent_steps]
    runner.log.connect(logs.append)
    runner._ocr_store = fake_ocr_store  # type: ignore
    runner.run()

    assert any("Enter sub-script" in m for m in logs)
    assert any("Returning from sub-script" in m for m in logs)
    child_idx = next((i for i, m in enumerate(logs) if "Child Work" in m), -1)
    assert child_idx != -1
    assert runner.variable_context.get("child_done") == 1

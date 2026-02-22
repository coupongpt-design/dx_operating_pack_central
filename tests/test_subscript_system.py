from types import SimpleNamespace
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.runner import MacroRunner
from app.core.models import StepData, RepeatConfig


def test_subscript_context_shared(monkeypatch, tmp_path):
    """Parent runs a child macro, child sets a var, parent reads it."""
    child_steps = [StepData(id="c0", name="ChildVar", type="comment")]
    child_file = tmp_path / "child.json"
    child_file.write_text(json.dumps({"steps": [child_steps[0].__dict__]}), encoding="utf-8")

    parent_steps = [
        StepData(id="p0", name="RunChild", type="run_macro", target_macro_path=str(child_file)),
        StepData(id="p1", name="UseChildVar", type="comment"),
    ]

    runner = MacroRunner(parent_steps, repeat=RepeatConfig(repeat_count=1), dry_run=True)

    # Fake mss to avoid real screen access
    def fake_mss():
        class Dummy:
            monitors = [{"left": 0, "top": 0, "width": 10, "height": 10}]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def grab(self, region):
                size = region["width"] * region["height"] * 3
                return SimpleNamespace(rgb=b"\x00" * size, width=region["width"], height=region["height"])

        return Dummy()

    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=fake_mss))

    # Fake loader for sub-script to avoid real file parsing issues
    monkeypatch.setattr(runner, "_load_macro_file", lambda path: child_steps)

    # Override comment handler to set/read context
    def handle_comment(sct, mon, step: StepData, idx: int):
        if step.name == "ChildVar":
            runner.variable_context["child_done"] = 1
        if step.name == "UseChildVar":
            runner.variable_context["used_child"] = runner.variable_context.get("child_done")
        return True, None, 0

    runner._step_handlers["comment"] = lambda sct, mon, s, idx: handle_comment(sct, mon, s, idx)

    runner.run()

    assert runner.variable_context.get("child_done") == 1
    assert runner.variable_context.get("used_child") == 1
    assert runner.call_stack == []

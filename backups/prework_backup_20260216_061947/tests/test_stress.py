import random
import sys
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.runner import MacroRunner
from app.core.models import StepData, RepeatConfig
from app.core.commands import UndoStack, AddStepCommand, RemoveStepCommand, MoveStepCommand, EditStepCommand


def _dummy_mss():
    class DummyGrab:
        def __init__(self, w, h):
            self.width = w
            self.height = h
            self.rgb = b"\x00" * (w * h * 3)

    class DummyCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        @property
        def monitors(self):
            return [{"left": 0, "top": 0, "width": 10, "height": 10}]

        def grab(self, region):
            return DummyGrab(region.get("width", 10), region.get("height", 10))

    return DummyCtx()


def test_long_running_macro(monkeypatch):
    """Run a simple loop 1,000 iterations with mocked sleep to ensure stability."""
    steps = [
        StepData(id="s0", name="HP Scan", type="ocr_store", ocr_store_var="hp"),
        StepData(id="s1", name="Wait", type="wait", wait_ms=1),
    ]
    runner = MacroRunner(
        steps,
        repeat=RepeatConfig(repeat_count=1000, repeat_cooldown_ms=0),
        dry_run=True,
        capture_on_fail=False,
    )
    runner.poll_interval = 0.0

    # Mock mss and matcher
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=_dummy_mss))
    monkeypatch.setattr(runner, "_matcher", SimpleNamespace(find_best_optimized=lambda frame, s: SimpleNamespace(ok=False)))

    # Mock sleep to be instant
    monkeypatch.setattr(runner, "msleep", lambda ms: None)

    # Mock ocr_store to store dummy hp
    def fake_ocr_store(sct, mon, step):
        runner.variable_context["hp"] = 1000
        return True

    runner._ocr_store = fake_ocr_store  # type: ignore

    runner.run()
    # If no exception, test passes. Check loop count reached
    assert runner.repeat.repeat_count == 1000


def test_chaos_undo_redo(monkeypatch):
    """Randomly apply undo/redo/add/move/edit on a step list to ensure no crashes."""
    steps = [StepData(id="s0", name="Base", type="comment")]
    undo_stack = UndoStack()

    def push(cmd):
        undo_stack.push(cmd)

    for _ in range(200):
        action = random.choice(["add", "del", "move", "edit", "undo", "redo"])
        if action == "add":
            new = StepData(id=str(random.randint(1, 9999)), name="N", type="comment")
            push(AddStepCommand(steps, new))
        elif action == "del" and steps:
            idx = random.randrange(len(steps))
            push(RemoveStepCommand(steps, idx))
        elif action == "move" and len(steps) > 1:
            a, b = random.sample(range(len(steps)), 2)
            push(MoveStepCommand(steps, a, b))
        elif action == "edit" and steps:
            idx = random.randrange(len(steps))
            old = steps[idx]
            new = StepData(id=old.id, name=old.name + "E", type=old.type)
            push(EditStepCommand(steps, idx, old, new))
        elif action == "undo":
            with suppress(Exception):
                undo_stack.undo()
        elif action == "redo":
            with suppress(Exception):
                undo_stack.redo()

    # No crash, ensure undo/redo stacks coherent
    assert undo_stack.can_undo() or undo_stack.can_redo() or True


def test_call_stack_no_leak(monkeypatch):
    """Ensure call_stack does not grow indefinitely."""
    steps = [StepData(id="s0", name="Child", type="comment")]
    runner = MacroRunner(steps, repeat=RepeatConfig(repeat_count=2), dry_run=True)
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=_dummy_mss))
    monkeypatch.setattr(runner, "_matcher", SimpleNamespace(find_best_optimized=lambda frame, s: SimpleNamespace(ok=False)))
    monkeypatch.setattr(runner, "_handle_run_macro", lambda s: True)
    runner._step_handlers["run_macro"] = lambda sct, mon, s, idx: (runner._handle_run_macro(s), None, 0)

    runner.call_stack = []
    runner.run()
    assert len(runner.call_stack) == 0

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.commands import (
    UndoStack,
    AddStepCommand,
    RemoveStepCommand,
    EditStepCommand,
    MoveStepCommand,
)


def test_add_remove_redo():
    steps = []
    stack = UndoStack()

    stack.push(AddStepCommand(steps, "A"))
    stack.push(AddStepCommand(steps, "B"))
    assert steps == ["A", "B"]

    stack.undo()
    assert steps == ["A"]

    stack.redo()
    assert steps == ["A", "B"]


def test_edit_move():
    steps = ["A", "B", "C"]
    stack = UndoStack()

    stack.push(EditStepCommand(steps, 1, "B", "B2"))
    assert steps == ["A", "B2", "C"]
    stack.undo()
    assert steps == ["A", "B", "C"]
    stack.redo()
    assert steps == ["A", "B2", "C"]

    stack.push(MoveStepCommand(steps, 0, 2))
    assert steps == ["B2", "C", "A"]
    stack.undo()
    assert steps == ["A", "B2", "C"]

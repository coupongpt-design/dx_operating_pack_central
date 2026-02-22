from app.core.commands import MoveStepCommand, UndoStack
from app.core.models import StepData


def test_move_step_command_undo_redo():
    steps = [
        StepData(id="s0", name="First", type="comment"),
        StepData(id="s1", name="Second", type="comment"),
        StepData(id="s2", name="Third", type="comment"),
    ]

    stack = UndoStack()

    # Move the last item to the front.
    stack.push(MoveStepCommand(steps, 2, 0))
    assert [s.id for s in steps] == ["s2", "s0", "s1"]

    stack.undo()
    assert [s.id for s in steps] == ["s0", "s1", "s2"]

    stack.redo()
    assert [s.id for s in steps] == ["s2", "s0", "s1"]

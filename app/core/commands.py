from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Any


class Command(ABC):
    @abstractmethod
    def execute(self) -> None:
        ...

    @abstractmethod
    def undo(self) -> None:
        ...


class AddStepCommand(Command):
    def __init__(self, step_list: List[Any], new_step: Any, index: int | None = None):
        self.step_list = step_list
        self.new_step = new_step
        self.index = index if index is not None else len(step_list)

    def execute(self) -> None:
        self.step_list.insert(self.index, self.new_step)

    def undo(self) -> None:
        if 0 <= self.index < len(self.step_list):
            self.step_list.pop(self.index)


class RemoveStepCommand(Command):
    def __init__(self, step_list: List[Any], index_to_remove: int):
        self.step_list = step_list
        self.index = index_to_remove
        self.removed = None

    def execute(self) -> None:
        if 0 <= self.index < len(self.step_list):
            self.removed = self.step_list.pop(self.index)

    def undo(self) -> None:
        if self.removed is not None:
            self.step_list.insert(self.index, self.removed)


class EditStepCommand(Command):
    def __init__(self, step_list: List[Any], index: int, old_data: Any, new_data: Any):
        self.step_list = step_list
        self.index = index
        self.old_data = old_data
        self.new_data = new_data

    def execute(self) -> None:
        if 0 <= self.index < len(self.step_list):
            self.step_list[self.index] = self.new_data

    def undo(self) -> None:
        if 0 <= self.index < len(self.step_list):
            self.step_list[self.index] = self.old_data


class MoveStepCommand(Command):
    def __init__(self, step_list: List[Any], old_index: int, new_index: int):
        self.step_list = step_list
        self.old_index = old_index
        self.new_index = new_index

    def execute(self) -> None:
        if not (0 <= self.old_index < len(self.step_list)):
            return
        item = self.step_list.pop(self.old_index)
        self.step_list.insert(self.new_index, item)
        # Swap indices for undo
        self.old_index, self.new_index = self.new_index, self.old_index

    def undo(self) -> None:
        # execute already swapped indices, so call execute to revert
        self.execute()


class ReorderStepsCommand(Command):
    def __init__(self, step_list: List[Any], new_order: List[Any]):
        self.step_list = step_list
        self.old_order = list(step_list)
        self.new_order = list(new_order)

    def execute(self) -> None:
        self.step_list[:] = self.new_order

    def undo(self) -> None:
        self.step_list[:] = self.old_order


class AddStepsCommand(Command):
    def __init__(self, step_list: List[Any], new_steps: List[Any], index: int | None = None):
        self.step_list = step_list
        self.new_steps = list(new_steps)
        self.index = index if index is not None else len(step_list)

    def execute(self) -> None:
        for offset, step in enumerate(self.new_steps):
            self.step_list.insert(self.index + offset, step)

    def undo(self) -> None:
        if not self.new_steps:
            return
        del self.step_list[self.index:self.index + len(self.new_steps)]


class UndoStack:
    def __init__(self):
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def push(self, command: Command) -> None:
        command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)

    def redo(self) -> None:
        if not self.redo_stack:
            return
        cmd = self.redo_stack.pop()
        cmd.execute()
        self.undo_stack.append(cmd)

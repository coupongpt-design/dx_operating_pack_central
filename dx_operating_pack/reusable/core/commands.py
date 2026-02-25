from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Any
import os


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


class AddRecordedStepsCommand(AddStepsCommand):
    """
    Recording-aware batch add command.
    - undo(): remove inserted steps + cleanup managed temp image files if unreferenced.
    - execute(): restore missing managed image files (from cached bytes) before re-insert (redo-safe).
    """

    def __init__(
        self,
        step_list: List[Any],
        new_steps: List[Any],
        index: int | None = None,
        managed_image_paths: list[str] | None = None,
    ):
        super().__init__(step_list, new_steps, index=index)
        self.managed_image_paths = [os.path.abspath(p) for p in (managed_image_paths or []) if p]
        self._asset_bytes: dict[str, bytes] = {}
        self._build_asset_cache()

    def _build_asset_cache(self):
        for step in self.new_steps:
            path = getattr(step, "image_path", None) or getattr(step, "anchor_image_path", None)
            if not path:
                continue
            ap = os.path.abspath(str(path))
            if self.managed_image_paths and ap not in self.managed_image_paths:
                continue
            payload = getattr(step, "png_bytes", None)
            if isinstance(payload, (bytes, bytearray)) and payload:
                self._asset_bytes[ap] = bytes(payload)
                continue
            try:
                if os.path.exists(ap):
                    with open(ap, "rb") as f:
                        self._asset_bytes[ap] = f.read()
            except Exception:
                continue

    def _restore_missing_assets(self):
        for path, blob in self._asset_bytes.items():
            try:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                if not os.path.exists(path):
                    with open(path, "wb") as f:
                        f.write(blob)
            except Exception:
                continue

    def _step_uses_path(self, step: Any, target_abs: str) -> bool:
        for key in ("image_path", "anchor_image_path"):
            val = getattr(step, key, None)
            if not val:
                continue
            try:
                if os.path.abspath(str(val)) == target_abs:
                    return True
            except Exception:
                continue
        return False

    def _is_path_referenced(self, target_abs: str) -> bool:
        for step in self.step_list:
            if self._step_uses_path(step, target_abs):
                return True
        return False

    def _cleanup_unreferenced_assets(self):
        for path in self.managed_image_paths:
            try:
                if self._is_path_referenced(path):
                    continue
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                continue

    def execute(self) -> None:
        self._restore_missing_assets()
        super().execute()

    def undo(self) -> None:
        super().undo()
        self._cleanup_unreferenced_assets()


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

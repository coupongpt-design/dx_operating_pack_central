"""Custom exception hierarchy for macro runtime."""

from __future__ import annotations


class MacroBaseError(Exception):
    """Base class for macro runtime errors."""


class ExecutionError(MacroBaseError):
    """Generic execution failure in runner loop."""


class ResourceError(MacroBaseError):
    """Resource loading/access failure (image/config/data files)."""


class ActionError(MacroBaseError):
    """Concrete action failure (click/type/drag/step handler)."""


class TargetWindowError(MacroBaseError):
    """Target window lookup/activation failure."""


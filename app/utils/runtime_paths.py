from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None))


def get_runtime_base_dir() -> Path:
    """
    Base directory for bundled resources.
    - PyInstaller onefile/onedir: sys._MEIPASS
    - Dev run: project root (.. / .. from app/utils)
    """
    if is_frozen_runtime():
        return Path(str(getattr(sys, "_MEIPASS"))).resolve()
    return Path(__file__).resolve().parents[2]


def get_resource_path(relative_path: str) -> str:
    rel = str(relative_path or "").replace("\\", "/").lstrip("/")
    return str((get_runtime_base_dir() / rel).resolve())


def get_writable_app_dir() -> Path:
    """
    Writable app directory used for user-editable data.
    Priority:
    1) IMAGEMACRO_DATA_DIR env override
    2) Qt AppDataLocation
    3) ~/.imagemacro
    """
    env_override = str(os.getenv("IMAGEMACRO_DATA_DIR", "") or "").strip()
    if env_override:
        base = Path(os.path.expandvars(os.path.expanduser(env_override)))
        base.mkdir(parents=True, exist_ok=True)
        return base

    base = ""
    try:
        from PyQt5.QtCore import QStandardPaths  # type: ignore

        base = str(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or "").strip()
    except Exception:
        base = ""

    if not base:
        base = str((Path.home() / ".imagemacro").resolve())

    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path

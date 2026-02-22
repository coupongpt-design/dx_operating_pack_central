from __future__ import annotations

import os
import shutil
from typing import Any

try:
    from PyQt5.QtCore import QSettings  # type: ignore
except Exception:  # pragma: no cover - defensive fallback
    QSettings = None  # type: ignore


DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_TESSERACT_SETTINGS_KEYS = ("ocr/tesseract_cmd", "general/tesseract_cmd")


def _normalize_cmd(cmd: Any) -> str:
    return str(cmd or "").strip()


def _command_exists(cmd: str) -> bool:
    text = _normalize_cmd(cmd)
    if not text:
        return False
    expanded = os.path.expandvars(os.path.expanduser(text))
    if os.path.exists(expanded):
        return True
    low = text.lower()
    if low in {"tesseract", "tesseract.exe"}:
        return shutil.which("tesseract") is not None
    return False


def _get_settings(settings: Any | None = None):
    if settings is not None:
        return settings
    if QSettings is None:
        return None
    try:
        return QSettings("ImageMacro", "MVP")
    except Exception:
        return None


def load_tesseract_cmd_from_settings(settings: Any | None = None) -> str:
    st = _get_settings(settings)
    if st is None:
        return ""
    for key in _TESSERACT_SETTINGS_KEYS:
        try:
            raw = st.value(key, "")
        except Exception:
            raw = ""
        text = _normalize_cmd(raw)
        if text:
            return text
    return ""


def save_tesseract_cmd_to_settings(cmd: str, settings: Any | None = None) -> bool:
    st = _get_settings(settings)
    if st is None:
        return False
    value = _normalize_cmd(cmd)
    try:
        st.setValue("ocr/tesseract_cmd", value)
        return True
    except Exception:
        return False


def resolve_tesseract_cmd(settings: Any | None = None) -> tuple[str | None, str]:
    env_cmd = _normalize_cmd(os.getenv("TESSERACT_CMD", ""))
    if env_cmd and _command_exists(env_cmd):
        return env_cmd, "env"

    setting_cmd = load_tesseract_cmd_from_settings(settings=settings)
    if setting_cmd and _command_exists(setting_cmd):
        return setting_cmd, "settings"

    if _command_exists(DEFAULT_TESSERACT_PATH):
        return DEFAULT_TESSERACT_PATH, "default"

    if _command_exists("tesseract"):
        return "tesseract", "path"

    return None, "missing"


def configure_tesseract_cmd(settings: Any | None = None) -> tuple[str | None, str]:
    try:
        import pytesseract
    except Exception:
        return None, "pytesseract_missing"

    cmd, source = resolve_tesseract_cmd(settings=settings)
    if cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
        except Exception:
            pass
    return cmd, source


def get_tesseract_status(settings: Any | None = None) -> dict[str, Any]:
    cmd, source = resolve_tesseract_cmd(settings=settings)
    return {
        "configured": bool(cmd),
        "cmd": cmd or "",
        "source": source,
        "exists": bool(cmd and _command_exists(cmd)),
    }

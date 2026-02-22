from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
import ctypes

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None

try:  # pragma: no cover - optional on non-Windows test envs
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32process  # type: ignore
    import win32api  # type: ignore
    _WIN32_AVAILABLE = True
except ImportError:  # pragma: no cover
    win32con = win32gui = win32process = win32api = None  # type: ignore
    _WIN32_AVAILABLE = False


class WindowManager:
    """Helpers to locate and gently refresh windows on Windows."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__ + ".WindowManager")

    # ----------------- Basic operations -----------------
    def find_window(self, partial_title: str) -> Optional[int]:
        """Find the first visible window whose title contains the given text."""
        if not _WIN32_AVAILABLE:
            self.logger.warning("pywin32 not available; find_window skipped")
            return None
        if not partial_title:
            self.logger.debug("Skipping window search: empty title")
            return None

        self.logger.debug("Searching for window containing: %s", partial_title)
        found: Optional[int] = None

        def _enum_handler(hwnd: int, _ctx: Any) -> None:
            nonlocal found
            if found is not None:
                return
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd) or ""
            if partial_title.lower() in title.lower():
                found = hwnd

        win32gui.EnumWindows(_enum_handler, None)
        if found:
            self.logger.info("Found window hwnd=%s", found)
        else:
            self.logger.debug("No window matched: %s", partial_title)
        return found

    def activate_window(self, hwnd: int) -> None:
        if not _WIN32_AVAILABLE:
            return
        if not hwnd:
            return
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        self.force_refresh(hwnd)

    def force_refresh(self, hwnd: int) -> None:
        """Nudge the window size to force a repaint (DPI/black-screen fix)."""
        if not _WIN32_AVAILABLE:
            return
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width, height = right - left, bottom - top
            win32gui.MoveWindow(hwnd, left, top, width + 1, height, True)
            time.sleep(0.05)
            win32gui.MoveWindow(hwnd, left, top, width, height, True)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("force_refresh failed: %s", exc)

    def get_window_rect(self, hwnd: int) -> Optional[Dict[str, int]]:
        if not _WIN32_AVAILABLE:
            return None
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            return {"left": left, "top": top, "width": right - left, "height": bottom - top}
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("get_window_rect failed: %s", exc)
            return None

    # ----------------- Listing & Filtering -----------------
    def get_window_list(self) -> List[Dict[str, Any]]:
        if not _WIN32_AVAILABLE:
            return self._get_window_list_ctypes()
        windows: List[Dict[str, Any]] = []

        def _enum(hwnd: int, _ctx: Any) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd) or ""
            if not title:
                return
            class_name = win32gui.GetClassName(hwnd) or ""
            proc_name = ""
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if psutil:
                    proc_name = psutil.Process(pid).name()
            except Exception:  # noqa: BLE001
                proc_name = ""
            windows.append(
                {
                    "hwnd": hwnd,
                    "title": title,
                    "class_name": class_name,
                    "process_name": proc_name,
                }
            )

        if _WIN32_AVAILABLE:
            win32gui.EnumWindows(_enum, None)
        return windows

    def _get_window_list_ctypes(self) -> List[Dict[str, Any]]:
        """Fallback window enumeration when pywin32 is unavailable."""
        windows: List[Dict[str, Any]] = []
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            enum_windows = user32.EnumWindows
            is_visible = user32.IsWindowVisible
            get_text_len = user32.GetWindowTextLengthW
            get_text = user32.GetWindowTextW
            get_class = user32.GetClassNameW
            get_pid = user32.GetWindowThreadProcessId
            enum_windows.restype = ctypes.c_bool

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def _enum(hwnd, _lparam):
                try:
                    if not is_visible(hwnd):
                        return True
                    length = int(get_text_len(hwnd))
                    if length <= 0:
                        return True
                    title_buf = ctypes.create_unicode_buffer(length + 1)
                    get_text(hwnd, title_buf, length + 1)
                    title = (title_buf.value or "").strip()
                    if not title:
                        return True

                    class_buf = ctypes.create_unicode_buffer(256)
                    get_class(hwnd, class_buf, 256)
                    class_name = class_buf.value or ""

                    proc_name = ""
                    pid = ctypes.c_ulong(0)
                    get_pid(hwnd, ctypes.byref(pid))
                    if psutil and int(pid.value) > 0:
                        try:
                            proc_name = psutil.Process(int(pid.value)).name()
                        except Exception:
                            proc_name = ""

                    windows.append(
                        {
                            "hwnd": int(hwnd),
                            "title": title,
                            "class_name": class_name,
                            "process_name": proc_name,
                        }
                    )
                except Exception:
                    pass
                return True

            enum_windows(_enum, 0)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("ctypes fallback window enumeration failed: %s", exc)
            return []
        return windows

    def _match_rule(self, win: Dict[str, Any], rule: str) -> bool:
        rule = rule.strip()
        if not rule:
            return False
        target = rule
        field = None
        if ":" in rule:
            prefix, val = rule.split(":", 1)
            if prefix in ("title", "class", "proc"):
                field = prefix
                target = val
        target = target.lower()
        if field == "title":
            return target in win.get("title", "").lower()
        if field == "class":
            return target in win.get("class_name", "").lower()
        if field == "proc":
            return target in win.get("process_name", "").lower()
        # no prefix: match any field
        return any(target in str(win.get(k, "")).lower() for k in ("title", "class_name", "process_name"))

    def filter_windows(self, full_list: List[Dict[str, Any]], filter_text: str) -> List[Dict[str, Any]]:
        if not filter_text:
            return full_list
        tokens = [t.strip() for t in filter_text.split(",") if t.strip()]
        include_rules = [t for t in tokens if not t.startswith("!")]
        exclude_rules = [t[1:] for t in tokens if t.startswith("!")]

        result: List[Dict[str, Any]] = []
        for win in full_list:
            if any(self._match_rule(win, r) for r in exclude_rules):
                continue
            if include_rules:
                if not any(self._match_rule(win, r) for r in include_rules):
                    continue
            result.append(win)
        return result

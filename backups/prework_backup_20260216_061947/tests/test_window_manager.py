import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.window_manager import WindowManager


@pytest.fixture
def wm():
    return WindowManager()


def test_force_refresh_no_pywin32(monkeypatch, wm):
    """If pywin32 is missing, methods should return gracefully."""
    monkeypatch.setattr("app.core.window_manager.win32gui", None)
    monkeypatch.setattr("app.core.window_manager.win32con", None)
    monkeypatch.setattr("app.core.window_manager.win32api", None)
    wm.force_refresh(0)  # Should not raise
    wm.activate_window(0)  # Should not raise
    assert True


def test_find_window_mock(monkeypatch, wm):
    """Mock EnumWindows to simulate a hit."""
    calls = {}

    def fake_enum(handler, _):
        handler(1234, None)

    def fake_gettext(hwnd):
        return "My Game Window"

    def fake_visible(hwnd):
        return True

    monkeypatch.setattr("app.core.window_manager.win32gui", SimpleNamespace(EnumWindows=fake_enum, GetWindowText=fake_gettext, IsWindowVisible=fake_visible))
    hwnd = wm.find_window("Game")
    assert hwnd == 1234


def test_activate_window_calls_refresh(monkeypatch, wm):
    """Ensure activate_window calls force_refresh after bringing to front."""
    events = {"refreshed": False}

    class FakeGui:
        def __init__(self):
            self.restored = False
            self.foreground = False

        def IsIconic(self, hwnd):
            return True

        def ShowWindow(self, hwnd, mode):
            self.restored = True

        def SetForegroundWindow(self, hwnd):
            self.foreground = True

    fake_gui = FakeGui()

    def fake_refresh(hwnd):
        events["refreshed"] = True

    monkeypatch.setattr("app.core.window_manager.win32gui", fake_gui)
    monkeypatch.setattr("app.core.window_manager.win32con", SimpleNamespace(SW_RESTORE=9))
    monkeypatch.setattr("app.core.window_manager.win32api", SimpleNamespace())
    monkeypatch.setattr(wm, "force_refresh", fake_refresh)

    wm.activate_window(999)
    assert fake_gui.restored is True
    assert fake_gui.foreground is True
    assert events["refreshed"] is True


def test_filter_windows_include_and_exclude_rules(wm):
    windows = [
        {"title": "Alpha Game", "class_name": "UnityWndClass", "process_name": "game.exe"},
        {"title": "Browser", "class_name": "Chrome_WidgetWin_1", "process_name": "chrome.exe"},
        {"title": "Chat", "class_name": "QtWnd", "process_name": "messenger.exe"},
    ]

    filtered = wm.filter_windows(windows, "title:game,!proc:chrome")
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Alpha Game"

    filtered_any = wm.filter_windows(windows, "class:qt,proc:chrome")
    assert {w["title"] for w in filtered_any} == {"Browser", "Chat"}


def test_get_window_list_collects_visible_windows(monkeypatch, wm):
    monkeypatch.setattr("app.core.window_manager._WIN32_AVAILABLE", True)
    data = {
        1: {"visible": True, "title": "Alpha", "class": "UnityWndClass", "pid": 101},
        2: {"visible": False, "title": "Hidden", "class": "HiddenClass", "pid": 999},
        3: {"visible": True, "title": "", "class": "NoTitleClass", "pid": 555},
        4: {"visible": True, "title": "Beta", "class": "QtWnd", "pid": 202},
    }

    def fake_enum(handler, _ctx):
        for hwnd in (1, 2, 3, 4):
            handler(hwnd, None)

    fake_gui = SimpleNamespace(
        EnumWindows=fake_enum,
        IsWindowVisible=lambda hwnd: data[hwnd]["visible"],
        GetWindowText=lambda hwnd: data[hwnd]["title"],
        GetClassName=lambda hwnd: data[hwnd]["class"],
    )
    fake_proc = SimpleNamespace(GetWindowThreadProcessId=lambda hwnd: (0, data[hwnd]["pid"]))

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid

        def name(self):
            if self.pid == 202:
                raise RuntimeError("process disappeared")
            return f"p{self.pid}.exe"

    monkeypatch.setattr("app.core.window_manager.win32gui", fake_gui)
    monkeypatch.setattr("app.core.window_manager.win32process", fake_proc)
    monkeypatch.setattr("app.core.window_manager.psutil", SimpleNamespace(Process=FakeProcess))

    windows = wm.get_window_list()
    assert [w["title"] for w in windows] == ["Alpha", "Beta"]
    assert windows[0]["process_name"] == "p101.exe"
    assert windows[1]["process_name"] == ""


def test_get_window_rect_returns_none_on_failure(monkeypatch, wm):
    monkeypatch.setattr("app.core.window_manager._WIN32_AVAILABLE", True)
    monkeypatch.setattr(
        "app.core.window_manager.win32gui",
        SimpleNamespace(GetClientRect=lambda hwnd: (_ for _ in ()).throw(RuntimeError("boom"))),
    )
    assert wm.get_window_rect(1234) is None

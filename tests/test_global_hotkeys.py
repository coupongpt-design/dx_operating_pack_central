import ctypes
from ctypes import wintypes

from app.ui.hotkeys import SystemHotkeys
from app.ui.hotkeys import WM_HOTKEY


class _Ptr:
    def __init__(self, addr: int):
        self._addr = int(addr)

    def __int__(self) -> int:
        return self._addr


def test_system_hotkeys_register_all_includes_add_step_hotkeys():
    class DummyWindow:
        _hk_run = "f6"
        _hk_stop = "f7"
        _hk_record = "f8"
        _hk_pause = "f9"
        _hk_kill = "f10"
        _hk_add_img = "`"
        _hk_add_notimg = "ctrl+`"

    mw = DummyWindow()
    hotkeys = SystemHotkeys(mw)
    calls = []
    hotkeys._reg = lambda combo, hk_id: calls.append((combo, hk_id))

    hotkeys._register_all()

    assert calls == [
        ("f6", 1),
        ("f7", 2),
        ("f8", 3),
        ("f9", 4),
        ("f10", 5),
        ("`", 6),
        ("ctrl+`", 7),
    ]


def test_system_hotkeys_dispatch_add_step_hotkeys():
    class DummyWindow:
        def __init__(self):
            self.calls = []

        def add_image_step(self):
            self.calls.append("image")

        def add_not_image_step(self):
            self.calls.append("action")

    mw = DummyWindow()
    hotkeys = SystemHotkeys(mw)

    for hk_id, expected in ((6, "image"), (7, "action")):
        msg = wintypes.MSG()
        msg.message = WM_HOTKEY
        msg.wParam = hk_id

        handled, result = hotkeys.nativeEventFilter(
            "windows_generic_MSG",
            _Ptr(ctypes.addressof(msg)),
        )

        assert handled is True
        assert result == 0
        assert mw.calls[-1] == expected

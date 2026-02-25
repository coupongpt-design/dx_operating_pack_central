from app.core.recorder import InputRecorder
import app.core.recorder as recorder_mod


class _DummyListener:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._alive = False

    def start(self):
        self._alive = True

    def stop(self):
        self._alive = False

    def join(self, timeout=None):
        return None

    def is_alive(self):
        return self._alive


def _patch_dummy_listeners(monkeypatch):
    monkeypatch.setattr(recorder_mod.keyboard, "Listener", _DummyListener)
    monkeypatch.setattr(recorder_mod.mouse, "Listener", _DummyListener)


def test_self_window_click_is_excluded(monkeypatch):
    _patch_dummy_listeners(monkeypatch)
    recorder = InputRecorder(ignore_rect=None, lock_hwnd=1111)
    raw_events = []
    recorder.raw_event_received.connect(raw_events.append)
    recorder._window_from_point = lambda _x, _y: 1111

    recorder._on_click(100, 120, "left", True)

    assert raw_events == []
    assert recorder._queue.qsize() == 0


def test_stop_hotkey_is_consumed_not_recorded(monkeypatch):
    _patch_dummy_listeners(monkeypatch)
    recorder = InputRecorder(ignore_rect=None, lock_hwnd=9999)
    control_events = []
    raw_events = []
    recorder.control_event_received.connect(control_events.append)
    recorder.raw_event_received.connect(raw_events.append)
    recorder._foreground_hwnd = lambda: 7777

    recorder._on_key_press(recorder_mod.keyboard.Key.esc)

    assert control_events == ["stop_hotkey"]
    assert raw_events == []
    assert recorder._queue.qsize() == 0


def test_raw_event_emitted_and_callback_errors_swallowed(monkeypatch):
    _patch_dummy_listeners(monkeypatch)
    recorder = InputRecorder(
        ignore_rect=None,
        lock_hwnd=9999,
        raw_event_callback=lambda _payload: (_ for _ in ()).throw(RuntimeError("callback-fail")),
    )
    raw_events = []
    recorder.raw_event_received.connect(raw_events.append)
    recorder._foreground_hwnd = lambda: 2222

    recorder._on_key_press(recorder_mod.keyboard.KeyCode.from_char("a"))

    assert recorder._queue.qsize() == 1
    assert len(raw_events) == 1
    assert raw_events[0]["type"] == "key"
    assert raw_events[0]["key_code"] == "a"
    assert raw_events[0]["hwnd"] == 2222

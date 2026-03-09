import pytest
pytest.importorskip("pytestqt")

from PyQt5.QtWidgets import QApplication


class _Signal:
    def __init__(self):
        self._slots = []

    def connect(self, fn):
        self._slots.append(fn)

    def emit(self, *args, **kwargs):
        for fn in list(self._slots):
            fn(*args, **kwargs)


class _DummyRecorder:
    def __init__(self, *args, **kwargs):
        self.finished = _Signal()
        self.pausedChanged = _Signal()
        self.raw_event_received = _Signal()
        self.control_event_received = _Signal()

    def start(self):
        return None

    def stop(self):
        self.finished.emit([])


class _FakeOverlay:
    def __init__(self):
        self.visible = False
        self.count = 0
        self.ripples = []

    def set_recording(self, enabled: bool):
        self.visible = bool(enabled)

    def set_step_count(self, count: int):
        self.count = int(count)

    def trigger_click_ripple(self, x: int, y: int):
        self.ripples.append((int(x), int(y)))

    def isVisible(self):
        return self.visible


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_recording_hud_visibility_on_start_stop(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.InputRecorder", _DummyRecorder)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win._start_record()
    overlay = win._get_recording_overlay()
    assert overlay.isVisible() is True

    win._stop_record(show_summary=False)
    assert overlay.isVisible() is False
    win.close()


def test_recording_click_event_triggers_overlay_ripple(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.InputRecorder", _DummyRecorder)

    fake_overlay = _FakeOverlay()

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    monkeypatch.setattr(win, "_get_recording_overlay", lambda: fake_overlay)
    win._set_recording_overlay_visible(True)

    win._on_record_raw_event(
        {
            "timestamp": 1.0,
            "type": "click",
            "phase": "press",
            "x": 321,
            "y": 654,
            "button": "left",
            "key_code": None,
            "modifiers": [],
            "hwnd": 1,
        }
    )

    assert fake_overlay.ripples == [(321, 654)]
    win.close()

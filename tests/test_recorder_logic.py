import sys
from pathlib import Path
import logging
import time
from types import SimpleNamespace

import pytest
from PyQt5.QtCore import QSettings

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.recorder import InputRecorder


def test_record_delay_default_enabled():
    from app.core.config import ConfigManager

    st = QSettings("ImageMacro", "MVP")
    key = "rec/record_delay_enabled"
    had = st.contains(key)
    old = st.value(key) if had else None
    st.remove(key)
    st.sync()
    try:
        cfg = ConfigManager()
        settings = cfg.load_record_settings()
        assert settings["record_delay_enabled"] is True
    finally:
        if had:
            st.setValue(key, old)
        else:
            st.remove(key)
        st.sync()


def test_record_settings_none_values_fallback_to_defaults():
    from app.core.config import ConfigManager

    st = QSettings("ImageMacro", "MVP")
    keys = [
        "rec/typed_gap_ms",
        "rec/click_merge_ms",
        "rec/click_radius_px",
        "rec/scroll_flush_ms",
        "rec/scroll_scale_dx",
        "rec/scroll_scale_dy",
    ]
    old_values = {k: st.value(k) for k in keys}
    old_contains = {k: st.contains(k) for k in keys}
    for k in keys:
        st.setValue(k, None)
    st.sync()
    try:
        cfg = ConfigManager()
        settings = cfg.load_record_settings()
        assert settings["typed_gap_ms"] == 500
        assert settings["click_merge_ms"] == 350
        assert settings["click_radius_px"] == 3
        assert settings["scroll_flush_ms"] == 180
        assert settings["scroll_scale_dx"] == 30.0
        assert settings["scroll_scale_dy"] == 120.0
    finally:
        for k in keys:
            if old_contains[k]:
                st.setValue(k, old_values[k])
            else:
                st.remove(k)
        st.sync()


class DummyListener:
    def __init__(self, *a, **k):
        self._alive = False

    def start(self):
        self._alive = True

    def stop(self):
        self._alive = False

    def join(self, timeout=None):
        return True

    def is_alive(self):
        return self._alive


@pytest.fixture(autouse=True)
def mock_listeners(monkeypatch):
    monkeypatch.setattr("app.core.recorder.keyboard.Listener", DummyListener)
    monkeypatch.setattr("app.core.recorder.mouse.Listener", DummyListener)
    yield


def test_queue_overflow(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    rec = InputRecorder(ignore_rect=None, max_queue_size=50, move_min_distance_px=0)
    # Flood with move events
    for _ in range(10_000):
        rec._on_move(0, 0)
    assert rec._queue.qsize() <= rec._max_queue_size
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_distance_filter_skips_micro_moves():
    rec = InputRecorder(ignore_rect=None, max_queue_size=10, move_min_distance_px=3)
    rec._last_move_pos = (0, 0)
    rec._on_move(1, 1)  # below threshold
    rec._on_move(0, 0)  # below threshold
    # 첫 이동은 기록될 수 있으나 이후 빠른 미세 이동은 스킵되어 최대 1건만 있어야 함
    assert rec._queue.qsize() <= 1
    rec._on_move(100, 100)  # above threshold
    assert rec._queue.qsize() == 2


def test_wildcard_combo_ignored(monkeypatch):
    from app.core import recorder as recmod

    rec = InputRecorder(ignore_rect=None, ignore_combos=["ctrl+*"], max_queue_size=10)
    now = time.time()
    # Simulate ctrl down then 'c'
    rec._handle_key_press(now, recmod.keyboard.Key.ctrl)
    rec._handle_key_press(now + 0.01, recmod.keyboard.KeyCode.from_char("c"))
    assert len(rec._steps) == 0


def test_stop_safety():
    rec = InputRecorder(ignore_rect=None, max_queue_size=10)
    rec.start()
    rec._on_move(10, 10)
    rec._on_click(10, 10, None, True)
    rec._on_click(10, 10, None, False)
    rec.stop()
    # worker thread should be stopped
    assert not rec._worker_thread.is_alive()


def test_record_delay_calc_enabled():
    rec = InputRecorder(ignore_rect=None, record_delay_enabled=True)
    rec._last_event_ts = 1.0
    assert rec._calc_delay_ms(2.5) == 1500


def test_record_delay_calc_disabled():
    rec = InputRecorder(ignore_rect=None, record_delay_enabled=False)
    rec._last_event_ts = 1.0
    assert rec._calc_delay_ms(2.5) == 0


def test_record_delay_click_applied():
    rec = InputRecorder(ignore_rect=None, record_delay_enabled=True, click_radius_px=5)
    rec._ignore_until = 0.0
    rec._paused = False
    rec._last_event_ts = 1.0
    rec._handle_click(2.0, 10, 10, None, True)
    rec._handle_click(2.1, 10, 10, None, False)
    assert rec._steps[-1].pre_delay_ms == 1000


def test_record_delay_click_disabled():
    rec = InputRecorder(ignore_rect=None, record_delay_enabled=False, click_radius_px=5)
    rec._ignore_until = 0.0
    rec._paused = False
    rec._last_event_ts = 1.0
    rec._handle_click(2.0, 10, 10, None, True)
    rec._handle_click(2.1, 10, 10, None, False)
    assert rec._steps[-1].pre_delay_ms == 0


def test_recorded_scroll_keeps_pointer_position():
    rec = InputRecorder(
        ignore_rect=None,
        record_delay_enabled=True,
        scroll_scale_dx=1.0,
        scroll_scale_dy=1.0,
    )
    rec._ignore_until = 0.0
    rec._paused = False
    rec._last_event_ts = 1.0

    rec._handle_scroll(2.0, 111, 222, 3, -4)
    rec._flush_scroll(True)

    step = rec._steps[-1]
    assert step.type == "scroll"
    assert step.scroll_x == 111
    assert step.scroll_y == 222
    assert step.scroll_dx == 3
    assert step.scroll_dy == -4
    assert step.pre_delay_ms >= 1000

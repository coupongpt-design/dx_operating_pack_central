import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.models import StepData, TriggerData
from app.core.trigger_engine import TriggerWatcher


class _DummySct:
    def __init__(self, frame):
        self._frame = frame

    def grab(self, region):
        return self._frame


def test_capture_frame_bgr_from_rgb_buffer_object():
    class _Raw:
        width = 2
        height = 1
        # RGB pixels: red, green
        rgb = bytes([255, 0, 0, 0, 255, 0])

    watcher = TriggerWatcher([])
    frame = watcher._capture_frame_bgr(_DummySct(_Raw()), {"left": 0, "top": 0, "width": 2, "height": 1})

    assert frame is not None
    assert frame.shape == (1, 2, 3)
    # Converted to BGR
    assert tuple(frame[0, 0]) == (0, 0, 255)
    assert tuple(frame[0, 1]) == (0, 255, 0)


def test_capture_frame_bgr_from_bgra_numpy_array():
    raw = np.array([[[10, 20, 30, 40]]], dtype=np.uint8)  # BGRA
    watcher = TriggerWatcher([])
    frame = watcher._capture_frame_bgr(_DummySct(raw), {"left": 0, "top": 0, "width": 1, "height": 1})

    assert frame is not None
    assert frame.shape == (1, 1, 3)
    assert tuple(frame[0, 0]) == (10, 20, 30)


def test_capture_frame_bgr_returns_none_for_invalid_shape():
    watcher = TriggerWatcher([])
    frame = watcher._capture_frame_bgr(_DummySct(np.array(123)), {"left": 0, "top": 0, "width": 1, "height": 1})

    assert frame is None


def test_check_condition_uses_provided_frame_without_capture(monkeypatch):
    step = StepData(id="s1", name="Cond", type="image_click")
    trigger = TriggerData(id="t1", name="Trig", condition_step=step)
    watcher = TriggerWatcher([trigger])

    def fail_capture(*args, **kwargs):
        raise AssertionError("capture should not be called when frame_bgr is provided")

    monkeypatch.setattr(watcher, "_capture_frame_bgr", fail_capture)
    monkeypatch.setattr(
        watcher._matcher,
        "find_best_optimized",
        lambda frame, s: SimpleNamespace(ok=True),
        raising=False,
    )

    ok = watcher._check_condition(None, None, trigger, frame_bgr=np.zeros((1, 1, 3), dtype=np.uint8))
    assert ok is True


def test_check_condition_returns_false_when_capture_fails(monkeypatch):
    step = StepData(id="s1", name="Cond", type="image_click")
    trigger = TriggerData(id="t1", name="Trig", condition_step=step)
    watcher = TriggerWatcher([trigger])

    monkeypatch.setattr(watcher, "_capture_frame_bgr", lambda *a, **k: None)

    ok = watcher._check_condition(None, None, trigger, frame_bgr=None)
    assert ok is False


def test_pause_resume_sets_state_and_wakes_waiter():
    watcher = TriggerWatcher([])

    watcher.pause()
    assert watcher._paused is True
    assert watcher._wake_event.is_set() is True

    watcher._wake_event.clear()
    watcher.resume()
    assert watcher._paused is False
    assert watcher._wake_event.is_set() is True


def test_stop_sets_flags_when_not_running():
    watcher = TriggerWatcher([])
    ok = watcher.stop(timeout_ms=1)

    assert ok is True
    assert watcher._stop is True
    assert watcher._stop_event.is_set() is True


def test_stop_timeout_forces_terminate():
    class _FakeWatcher(TriggerWatcher):
        def __init__(self):
            super().__init__([])
            self._fake_running = True
            self.wait_calls = []
            self.terminated = False

        def isRunning(self):
            return self._fake_running

        def wait(self, timeout=0):
            self.wait_calls.append(timeout)
            return False

        def terminate(self):
            self.terminated = True
            self._fake_running = False

    watcher = _FakeWatcher()
    ok = watcher.stop(timeout_ms=10)

    assert ok is True
    assert watcher.terminated is True
    assert watcher.wait_calls and watcher.wait_calls[0] == 10

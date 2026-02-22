import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.recorder import InputRecorder


def _btn(name="Button.left"):
    class Btn:
        def __str__(self):
            return name
    return Btn()


@pytest.fixture(autouse=True)
def mock_listeners(monkeypatch):
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

    monkeypatch.setattr("app.core.recorder.keyboard.Listener", DummyListener)
    monkeypatch.setattr("app.core.recorder.mouse.Listener", DummyListener)
    yield


def test_hybrid_filter_jitter(monkeypatch):
    t = [0.0]

    def fake_time():
        return t[0]

    monkeypatch.setattr("app.core.recorder.time.time", fake_time)
    rec = InputRecorder(ignore_rect=None, move_min_distance_px=3)
    rec._on_move(0, 0)
    t[0] += 0.01  # 10ms
    rec._on_move(1, 1)
    t[0] += 0.01  # 10ms
    rec._on_move(0, 0)
    # 첫 이동은 저장, 10ms 지터는 스킵, 20ms 시점의 이동은 기록되어 총 2건이면 OK
    assert rec._queue.qsize() == 2


def test_hybrid_filter_precision(monkeypatch):
    t = [0.0]

    def fake_time():
        return t[0]

    monkeypatch.setattr("app.core.recorder.time.time", fake_time)
    rec = InputRecorder(ignore_rect=None, move_min_distance_px=3)
    rec._on_move(0, 0)
    t[0] += 0.05  # 50ms
    rec._on_move(1, 1)  # distance < 3, but time > 20ms => accept
    assert rec._queue.qsize() == 2


def test_drag_resample(monkeypatch):
    t = [0.0]

    def fake_time():
        return t[0]

    monkeypatch.setattr("app.core.recorder.time.time", fake_time)
    rec = InputRecorder(ignore_rect=None, move_min_distance_px=0)
    # Press
    rec._handle_click(t[0], 0, 0, _btn(), True)
    # Move with varying positions/times
    for i in range(1, 6):
        t[0] += 0.05
        rec._handle_move(t[0], i * 10, i * 5)
    # Release
    t[0] += 0.05
    rec._handle_click(t[0], 60, 30, _btn(), False)

    # One drag step should exist with resampled path
    assert rec._steps
    drag_step = rec._steps[-1]
    path = getattr(drag_step, "drag_path", [])
    assert len(path) >= 2
    # Resampled to ~20 points
    assert 15 <= len(path) <= 22

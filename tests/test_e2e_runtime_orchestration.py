import json
import os
import sys
from pathlib import Path

import pytest
pytest.importorskip("pytestqt")
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.models import RepeatConfig, StepData, TriggerData
from app.main import MainWindow


class _Signal:
    def __init__(self):
        self.connected = []

    def connect(self, cb):
        self.connected.append(cb)

    def disconnect(self, cb=None):
        if cb is None:
            self.connected.clear()
            return
        if cb in self.connected:
            self.connected.remove(cb)

    def emit(self, *args, **kwargs):
        for cb in list(self.connected):
            cb(*args, **kwargs)


class _DummyMainRunner:
    def __init__(self, running=True):
        self._running = running
        self.current_step_index = 2
        self.stop_called = False
        self.wait_called = None
        self.resume_calls = []
        self.debugEvent = _Signal()
        self.stepChanged = _Signal()

    def isRunning(self):
        return self._running

    def stop(self):
        self.stop_called = True
        self._running = False

    def wait(self, ms):
        self.wait_called = ms

    def snapshot_state(self):
        return {"state": True}

    def resume(self, index, state):
        self.resume_calls.append((index, state))
        self._running = True


class _DummyTriggerRunner:
    def __init__(self, steps, **kwargs):
        self.steps = list(steps)
        self.kwargs = kwargs
        self.finished = _Signal()
        self.log = _Signal()
        self.started = False

    def start(self):
        self.started = True


class _DummyScheduledRunner:
    def __init__(self, *args, **kwargs):
        self.finished = _Signal()
        self.log = _Signal()
        self.debugEvent = _Signal()
        self.stepChanged = _Signal()
        self.started = False

    def isRunning(self):
        return self.started

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def wait(self, ms):
        return None


class _FakeRecorder:
    def __init__(self, *args, **kwargs):
        self.finished = _Signal()
        self.pausedChanged = _Signal()
        self.metrics = {"total": 2, "dropped_move": 0, "dropped_scroll": 0, "max_queue": 2}
        self._active = False

    def start(self):
        self._active = True

    def stop(self):
        self._active = False
        self.finished.emit(
            [
                StepData(id="r1", name="Recorded 1", type="comment"),
                StepData(id="r2", name="Recorded 2", type="wait", wait_ms=5),
            ]
        )


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(autouse=True)
def isolate_settings():
    st = QSettings("ImageMacro", "MVP")
    data = {k: st.value(k) for k in st.allKeys()}
    yield
    st.clear()
    for k, v in data.items():
        st.setValue(k, v)
    st.sync()


@pytest.fixture
def window(monkeypatch, qapp, qtbot):
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(MainWindow, "_load_triggers", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.TriggerWatcher.start", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    yield win
    win.close()


def _write_macro_json(path: Path, steps: list[StepData]):
    payload = {
        "meta": {"version": "1.0", "target_window": ""},
        "repeat": RepeatConfig().to_json(),
        "steps": [s.to_dict() for s in steps],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_e2e_trigger_macro_pause_resume_with_real_files(window, monkeypatch, tmp_path):
    main_macro = tmp_path / "main.json"
    trigger_macro = tmp_path / "trigger.json"
    _write_macro_json(main_macro, [StepData(id="m1", name="Main", type="comment")])
    _write_macro_json(trigger_macro, [StepData(id="t1", name="Trigger", type="comment")])

    assert window._load_macro_from_path(str(main_macro)) is True
    window.runner = _DummyMainRunner(running=True)
    monkeypatch.setattr("app.main.MacroRunner", _DummyTriggerRunner)

    rel_trigger_path = os.path.relpath(trigger_macro, start=main_macro.parent)
    trigger = TriggerData(
        id="tg1",
        name="TriggerRun",
        condition_step=StepData(id="c1", name="Cond", type="image_click"),
        action_type="run_macro",
        action_value=rel_trigger_path,
    )

    window._on_trigger_fired(trigger)

    assert window._main_runner_paused is True
    assert window._paused_runner is not None
    assert window._paused_runner.stop_called is True
    assert window._paused_runner.wait_called == 1000
    assert isinstance(window.trigger_runner, _DummyTriggerRunner)
    assert window.trigger_runner.started is True
    assert [s.id for s in window.trigger_runner.steps] == ["t1"]

    paused = window._paused_runner
    window._on_trigger_finished(True)

    assert window._main_runner_paused is False
    assert window.runner is paused
    assert paused.resume_calls == [(2, {"state": True})]
    assert window.trigger_runner is None


def test_e2e_scheduler_sequence_runs_queue_in_order_with_real_files(window, monkeypatch, tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_macro_json(first, [StepData(id="a1", name="A1", type="comment")])
    _write_macro_json(second, [StepData(id="b1", name="B1", type="comment")])

    loaded_paths = []
    original_load = window._load_macro_from_path

    def tracked_load(path):
        loaded_paths.append(path)
        return original_load(path)

    window._load_macro_from_path = tracked_load
    window.run_macro = lambda: setattr(window, "runner", _DummyScheduledRunner())
    window.scheduler.running = True
    window.scheduler.set_macro_queue([str(first), str(second)])

    window.scheduler._start_sequence()
    assert loaded_paths == [str(first)]

    window._on_scheduled_run_finished(True)
    assert loaded_paths == [str(first), str(second)]

    window._on_scheduled_run_finished(True)
    assert window.scheduler.current_queue == []


def test_e2e_record_then_playback_transition(window, monkeypatch):
    monkeypatch.setattr("app.main.InputRecorder", _FakeRecorder)
    monkeypatch.setattr("app.main.MacroRunner", _DummyScheduledRunner)
    monkeypatch.setattr("app.main.QMessageBox.information", lambda *a, **k: None)

    calls = {"min": 0, "normal": 0}
    window.showMinimized = lambda: calls.__setitem__("min", calls["min"] + 1)
    window.showNormal = lambda: calls.__setitem__("normal", calls["normal"] + 1)
    window.steps = []
    if hasattr(window, "list"):
        window.list.clear()
    window.chkAutoMin.setChecked(True)

    window.toggle_record(True)
    window.toggle_record(False)

    assert calls["min"] == 1
    assert calls["normal"] == 1
    assert len(window.steps) == 2
    assert [s.id for s in window.steps] == ["r1", "r2"]

    window.run_macro()
    assert isinstance(window.runner, _DummyScheduledRunner)
    assert window.runner.started is True

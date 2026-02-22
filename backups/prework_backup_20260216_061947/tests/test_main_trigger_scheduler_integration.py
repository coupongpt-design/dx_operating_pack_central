import os
import sys
from pathlib import Path

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.models import StepData, TriggerData
from app.main import MainWindow


class DummySignal:
    def __init__(self, fail_disconnect: bool = False):
        self.connected = []
        self.fail_disconnect = fail_disconnect
        self.disconnect_calls = 0

    def connect(self, cb):
        self.connected.append(cb)

    def disconnect(self, cb=None):
        self.disconnect_calls += 1
        if self.fail_disconnect:
            raise RuntimeError("disconnect failed")
        if cb is None:
            self.connected.clear()
            return
        if cb in self.connected:
            self.connected.remove(cb)


class DummyMainRunner:
    def __init__(self, running: bool = True):
        self._running = running
        self.current_step_index = 2
        self.stop_called = False
        self.wait_called = None
        self.resume_calls = []
        self.snapshot_calls = 0
        self.debugEvent = DummySignal()
        self.stepChanged = DummySignal()

    def isRunning(self):
        return self._running

    def stop(self):
        self.stop_called = True
        self._running = False

    def wait(self, ms):
        self.wait_called = ms

    def snapshot_state(self):
        self.snapshot_calls += 1
        return {"saved": True}

    def resume(self, index, state):
        self.resume_calls.append((index, state))


class DummyTriggerRunner:
    def __init__(self, steps, **kwargs):
        self.steps = list(steps)
        self.kwargs = kwargs
        self.finished = DummySignal()
        self.log = DummySignal()
        self.started = False

    def start(self):
        self.started = True


class DummyScheduledRunner:
    def __init__(self, fail_disconnect: bool = False):
        self.finished = DummySignal(fail_disconnect=fail_disconnect)


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


def _trigger_run_macro(path: str) -> TriggerData:
    return TriggerData(
        id="tr1",
        name="Run Trigger",
        condition_step=StepData(id="cond1", name="Cond", type="image_click"),
        action_type="run_macro",
        action_value=path,
    )


def test_trigger_run_macro_pauses_main_and_starts_trigger_runner(window, monkeypatch, tmp_path):
    trigger_macro = tmp_path / "trigger.json"
    trigger_macro.write_text("{}", encoding="utf-8")

    main_runner = DummyMainRunner(running=True)
    window.runner = main_runner
    window._current_macro_path = str(tmp_path / "main.macro")
    monkeypatch.setattr(window, "_load_steps_from_file", lambda path: [StepData(id="tg1", name="Trigger", type="comment")])
    monkeypatch.setattr("app.main.MacroRunner", DummyTriggerRunner)

    window._on_trigger_fired(_trigger_run_macro(str(trigger_macro)))

    assert main_runner.stop_called is True
    assert main_runner.wait_called == 1000
    assert window._main_runner_paused is True
    assert window._paused_runner is main_runner
    assert window.trigger_runner is not None
    assert isinstance(window.trigger_runner, DummyTriggerRunner)
    assert window.trigger_runner.started is True
    assert len(window.trigger_runner.steps) == 1
    assert window.trigger_runner.steps[0].id == "tg1"


def test_trigger_load_failure_resumes_main_runner(window, monkeypatch, tmp_path):
    trigger_macro = tmp_path / "trigger.json"
    trigger_macro.write_text("{}", encoding="utf-8")

    main_runner = DummyMainRunner(running=True)
    window.runner = main_runner
    window._current_macro_path = str(tmp_path / "main.macro")
    monkeypatch.setattr(window, "_load_steps_from_file", lambda path: None)

    window._on_trigger_fired(_trigger_run_macro(str(trigger_macro)))

    assert window._main_runner_paused is False
    assert window._paused_runner is None
    assert window.runner is main_runner
    assert main_runner.resume_calls == [(2, {"saved": True})]
    assert window.trigger_runner is None


def test_on_trigger_finished_resumes_paused_runner(window):
    paused_runner = DummyMainRunner(running=False)
    window._main_runner_paused = True
    window._paused_runner = paused_runner
    window._resume_index = 7
    window._resume_state = {"token": 1}
    window.trigger_runner = DummyTriggerRunner([])

    window._on_trigger_finished(True)

    assert window.trigger_runner is None
    assert window._main_runner_paused is False
    assert window.runner is paused_runner
    assert paused_runner.resume_calls == [(7, {"token": 1})]
    assert window._paused_runner is None
    assert window._resume_state is None


def test_run_scheduled_macro_failure_notifies_scheduler(window, monkeypatch):
    monkeypatch.setattr(window, "_load_macro_from_path", lambda path: False)
    calls = []
    window.scheduler.notify_macro_finished = lambda ok: calls.append(ok)

    window._run_scheduled_macro(r"C:\tmp\missing.macro")

    assert calls == [False]
    assert window.sched_status_label.text().startswith("Running:")


def test_run_scheduled_macro_success_connects_finished(window, monkeypatch):
    monkeypatch.setattr(window, "_load_macro_from_path", lambda path: True)
    new_runner = DummyScheduledRunner()
    called = {"run": 0}

    def fake_run_macro():
        called["run"] += 1
        window.runner = new_runner

    window.run_macro = fake_run_macro
    window.runner = None

    window._run_scheduled_macro(r"C:\tmp\ok.macro")

    assert called["run"] == 1
    assert window._on_scheduled_run_finished in new_runner.finished.connected


def test_run_scheduled_macro_disconnect_error_does_not_block(window, monkeypatch):
    monkeypatch.setattr(window, "_load_macro_from_path", lambda path: True)
    old_runner = DummyScheduledRunner(fail_disconnect=True)
    new_runner = DummyScheduledRunner()
    window.runner = old_runner
    called = {"run": 0}

    def fake_run_macro():
        called["run"] += 1
        window.runner = new_runner

    window.run_macro = fake_run_macro

    window._run_scheduled_macro(r"C:\tmp\ok2.macro")

    assert called["run"] == 1
    assert window._on_scheduled_run_finished in new_runner.finished.connected


def test_run_scheduled_macro_notifies_when_runner_not_started(window, monkeypatch):
    monkeypatch.setattr(window, "_load_macro_from_path", lambda path: True)
    calls = []
    window.scheduler.notify_macro_finished = lambda ok: calls.append(ok)
    window.run_macro = lambda: setattr(window, "runner", None)
    window.runner = None

    window._run_scheduled_macro(r"C:\tmp\no_runner.macro")

    assert calls == [False]


def test_trigger_run_macro_without_main_handles_start_failure(window, monkeypatch, tmp_path):
    trigger_macro = tmp_path / "trigger.json"
    trigger_macro.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(window, "_load_steps_from_file", lambda path: [StepData(id="tg2", name="Trigger", type="comment")])

    class FailingTriggerRunner:
        def __init__(self, steps, **kwargs):
            self.steps = list(steps)
            self.kwargs = kwargs
            self.finished = DummySignal()
            self.log = DummySignal()

        def start(self):
            raise RuntimeError("start failed")

    errors = []
    window.err = lambda msg: errors.append(msg)
    monkeypatch.setattr("app.main.MacroRunner", FailingTriggerRunner)

    window._on_trigger_fired(_trigger_run_macro(str(trigger_macro)))

    assert window.trigger_runner is None
    assert errors and "Failed to start trigger macro:" in errors[-1]


def test_on_scheduled_run_finished_forwards_result(window):
    calls = []
    window.scheduler.notify_macro_finished = lambda ok: calls.append(ok)

    window._on_scheduled_run_finished(False)
    window._on_scheduled_run_finished(True)

    assert calls == [False, True]

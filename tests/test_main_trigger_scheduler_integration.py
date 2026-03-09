import os
import sys
from pathlib import Path

import pytest
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QApplication, QDialog

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


def _set_simple_comment_steps(window):
    window.steps = [
        StepData(id="s1", name="Step 1", type="comment"),
        StepData(id="s2", name="Step 2", type="comment"),
        StepData(id="s3", name="Step 3", type="comment"),
    ]
    window.refresh_step_list()


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
    assert window.sched_status_label.text().startswith("Status: Running")


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


def test_scheduler_failure_policy_settings_saved_and_loaded(window):
    idx = window.sched_failure_policy.findData("retry_then_continue")
    if idx >= 0:
        window.sched_failure_policy.setCurrentIndex(idx)
    window.sched_retry_count.setValue(3)
    window.sched_retry_delay_ms.setValue(1500)
    window._save_scheduler_settings()

    idx2 = window.sched_failure_policy.findData("continue_next")
    if idx2 >= 0:
        window.sched_failure_policy.blockSignals(True)
        window.sched_failure_policy.setCurrentIndex(idx2)
        window.sched_failure_policy.blockSignals(False)
    window.sched_retry_count.blockSignals(True)
    window.sched_retry_count.setValue(0)
    window.sched_retry_count.blockSignals(False)
    window.sched_retry_delay_ms.blockSignals(True)
    window.sched_retry_delay_ms.setValue(0)
    window.sched_retry_delay_ms.blockSignals(False)

    window._load_scheduler_settings()

    assert window.sched_failure_policy.currentData() == "retry_then_continue"
    assert window.sched_retry_count.value() == 3
    assert window.sched_retry_delay_ms.value() == 1500
    assert window.sched_retry_count.isEnabled() is True
    assert window.sched_retry_delay_ms.isEnabled() is True


def test_on_sched_enable_changed_applies_failure_policy_to_scheduler(window):
    idx = window.sched_failure_policy.findData("stop_sequence")
    if idx >= 0:
        window.sched_failure_policy.setCurrentIndex(idx)
    window.sched_retry_count.setValue(2)
    window.sched_retry_delay_ms.setValue(2500)
    window._add_path_to_sched_list(r"C:\tmp\dummy.macro")

    window._on_sched_enable_changed(Qt.Checked)

    assert window.scheduler.failure_policy == "stop_sequence"
    assert window.scheduler.max_retries == 2
    assert window.scheduler.retry_delay_ms == 2500


def test_scheduler_retry_controls_follow_failure_policy(window):
    idx_continue = window.sched_failure_policy.findData("continue_next")
    if idx_continue >= 0:
        window.sched_failure_policy.setCurrentIndex(idx_continue)
    assert window.sched_retry_count.isEnabled() is False
    assert window.sched_retry_delay_ms.isEnabled() is False

    idx_retry = window.sched_failure_policy.findData("retry_then_continue")
    if idx_retry >= 0:
        window.sched_failure_policy.setCurrentIndex(idx_retry)
    assert window.sched_retry_count.isEnabled() is True
    assert window.sched_retry_delay_ms.isEnabled() is True


def test_scheduler_status_signal_updates_scheduler_label(window):
    status_text = "Status: Retrying sample.macro (1/3)"

    window.scheduler.statusChanged.emit(status_text)

    assert window.sched_status_label.text() == status_text


def test_close_event_disables_scheduler_timer(window):
    window.scheduler.set_enabled(True)
    assert window.scheduler.running is True
    assert window.scheduler.timer.isActive() is True

    event = QCloseEvent()
    window.closeEvent(event)

    assert window.scheduler.running is False
    assert window.scheduler.timer.isActive() is False
    assert event.isAccepted() is True


def test_sync_order_reorders_steps_with_undo_redo(window):
    _set_simple_comment_steps(window)
    assert [s.id for s in window.steps] == ["s1", "s2", "s3"]

    moved_item = window.list.takeItem(2)
    window.list.insertItem(0, moved_item)
    window.list.setCurrentRow(0)
    window.list.orderChanged.emit()

    assert [s.id for s in window.steps] == ["s3", "s1", "s2"]
    assert window.undo_stack.can_undo() is True

    window._do_undo()
    assert [s.id for s in window.steps] == ["s1", "s2", "s3"]

    window._do_redo()
    assert [s.id for s in window.steps] == ["s3", "s1", "s2"]


def test_sync_order_noop_does_not_push_undo(window):
    _set_simple_comment_steps(window)
    before = len(window.undo_stack.undo_stack)

    window.list.orderChanged.emit()

    assert [s.id for s in window.steps] == ["s1", "s2", "s3"]
    assert len(window.undo_stack.undo_stack) == before


def test_add_not_image_step_cancel_does_not_add(window, monkeypatch):
    class CancelDialog:
        def __init__(self, step, all_steps, parent=None):
            self._step = step

        def exec_(self):
            return QDialog.Rejected

        def get_step_data(self):
            return StepData(id="cancelled", name="Cancelled", type="comment")

    monkeypatch.setattr("app.main.NotImageDialog", CancelDialog)
    before_steps = len(window.steps)
    before_undo = len(window.undo_stack.undo_stack)

    window.add_not_image_step()

    assert len(window.steps) == before_steps
    assert len(window.undo_stack.undo_stack) == before_undo


def test_add_not_image_step_uses_supported_default_type(window, monkeypatch):
    seen = {"type": None}

    class CancelDialog:
        def __init__(self, step, all_steps, parent=None):
            seen["type"] = step.type

        def exec_(self):
            return QDialog.Rejected

        def get_step_data(self):
            return None

    monkeypatch.setattr("app.main.NotImageDialog", CancelDialog)

    window.add_not_image_step()

    assert seen["type"] == "keyboard"


def test_add_not_image_step_accept_adds_step_and_is_undoable(window, monkeypatch):
    class AcceptDialog:
        def __init__(self, step, all_steps, parent=None):
            self._step = step

        def exec_(self):
            return QDialog.Accepted

        def get_step_data(self):
            return StepData(id="a1", name="Added", type="comment", comment="new")

    monkeypatch.setattr("app.main.NotImageDialog", AcceptDialog)
    before_steps = len(window.steps)
    before_undo = len(window.undo_stack.undo_stack)

    window.add_not_image_step()

    assert len(window.steps) == before_steps + 1
    assert window.steps[-1].id == "a1"
    assert window.steps[-1].name == "Added"
    assert window.steps[-1].comment == "new"
    assert len(window.undo_stack.undo_stack) == before_undo + 1

    window._do_undo()
    assert len(window.steps) == before_steps

    window._do_redo()
    assert len(window.steps) == before_steps + 1
    assert window.steps[-1].id == "a1"


def test_add_not_image_step_data_error_does_not_add(window, monkeypatch):
    class ErrorDialog:
        def __init__(self, step, all_steps, parent=None):
            self._step = step

        def exec_(self):
            return QDialog.Accepted

        def get_step_data(self):
            raise RuntimeError("broken dialog data")

    monkeypatch.setattr("app.main.NotImageDialog", ErrorDialog)
    before_steps = len(window.steps)
    before_undo = len(window.undo_stack.undo_stack)

    window.add_not_image_step()

    assert len(window.steps) == before_steps
    assert len(window.undo_stack.undo_stack) == before_undo


def test_edit_step_at_cancel_does_not_modify_step(window, monkeypatch):
    window.steps = [StepData(id="e1", name="Original", type="comment", comment="before")]
    window.refresh_step_list()

    class CancelDialog:
        def __init__(self, step, all_steps, parent=None):
            self._step = step

        def exec_(self):
            return QDialog.Rejected

        def get_step_data(self):
            return StepData(id="e1", name="Edited", type="comment", comment="after")

    monkeypatch.setattr("app.main.NotImageDialog", CancelDialog)
    before_undo = len(window.undo_stack.undo_stack)

    window.edit_step_at(0)

    assert window.steps[0].name == "Original"
    assert window.steps[0].comment == "before"
    assert len(window.undo_stack.undo_stack) == before_undo


def test_edit_step_at_accept_updates_and_is_undoable(window, monkeypatch):
    window.steps = [StepData(id="e1", name="Original", type="comment", comment="before")]
    window.refresh_step_list()

    class AcceptDialog:
        def __init__(self, step, all_steps, parent=None):
            self._step = step

        def exec_(self):
            return QDialog.Accepted

        def get_step_data(self):
            return StepData(id="e1", name="Edited", type="comment", comment="after")

    monkeypatch.setattr("app.main.NotImageDialog", AcceptDialog)
    before_undo = len(window.undo_stack.undo_stack)

    window.edit_step_at(0)

    assert window.steps[0].name == "Edited"
    assert window.steps[0].comment == "after"
    assert len(window.undo_stack.undo_stack) == before_undo + 1

    window._do_undo()
    assert window.steps[0].name == "Original"
    assert window.steps[0].comment == "before"

    window._do_redo()
    assert window.steps[0].name == "Edited"
    assert window.steps[0].comment == "after"


def test_edit_step_at_data_error_does_not_modify_step(window, monkeypatch):
    window.steps = [StepData(id="e1", name="Original", type="comment", comment="before")]
    window.refresh_step_list()

    class ErrorDialog:
        def __init__(self, step, all_steps, parent=None):
            self._step = step

        def exec_(self):
            return QDialog.Accepted

        def get_step_data(self):
            raise RuntimeError("broken edit data")

    monkeypatch.setattr("app.main.NotImageDialog", ErrorDialog)
    before_undo = len(window.undo_stack.undo_stack)

    window.edit_step_at(0)

    assert window.steps[0].name == "Original"
    assert window.steps[0].comment == "before"
    assert len(window.undo_stack.undo_stack) == before_undo

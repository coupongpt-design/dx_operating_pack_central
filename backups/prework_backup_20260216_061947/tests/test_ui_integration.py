import os
import sys
import types
from unittest.mock import MagicMock

import pytest
pytest.importorskip("pytestqt")
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QSettings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


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


class DummySignal:
    def connect(self, *a, **k):
        return None


def test_run_button_triggers_runner_start(monkeypatch, qapp, qtbot):
    from app.main import MainWindow, MacroRunner
    from app.core.models import StepData

    # Dummy runner to capture start calls
    started = {"called": False}

    class DummySignal:
        def connect(self, *a, **k):
            return None

    class DummyRunner:
        def __init__(self, *a, **k):
            started["instantiated"] = True
            self.finished = DummySignal()
            self.log = DummySignal()
            self.errorOccurred = DummySignal()
            self.requestCrosshair = DummySignal()

        def isRunning(self):
            return False

        def start(self):
            started["called"] = True

    monkeypatch.setattr("app.main.MacroRunner", DummyRunner)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    # Add minimal step so run_macro does not early-return
    win.steps.append(StepData(id="s1", name="Test", type="comment"))

    # Simulate click
    qtbot.mouseClick(win.btnRun, Qt.LeftButton)

    assert started.get("instantiated", False) is True
    assert started["called"] is True

    win.close()


@pytest.mark.parametrize(
    "perf_enabled, level, expected_queue, expected_move",
    [
        (True, 1, 20000, 1),
        (True, 2, 50000, 0),
        (True, 3, 100000, 0),
        (False, 3, 5000, 3),
    ],
)
def test_perf_level_recording_params(
    monkeypatch, qapp, qtbot, perf_enabled, level, expected_queue, expected_move
):
    from app.main import MainWindow

    captured = {}

    class DummyRecorder:
        def __init__(self, *a, **k):
            captured.update(k)
            self.finished = DummySignal()
            self.pausedChanged = DummySignal()

        def start(self):
            return None

    monkeypatch.setattr("app.main.InputRecorder", DummyRecorder)
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.chkPerfRecording.setChecked(perf_enabled)
    idx = win.cbPerfLevel.findData(level)
    if idx >= 0:
        win.cbPerfLevel.setCurrentIndex(idx)
    win._start_record()

    assert captured["max_queue_size"] == expected_queue
    assert captured["move_min_distance_px"] == expected_move

    win.close()


@pytest.mark.parametrize(
    "perf_enabled, level, expected_poll",
    [
        (True, 1, 0.05),
        (True, 2, 0.01),
        (True, 3, 0.0),
        (False, 3, 0.1),
    ],
)
def test_perf_level_playback_poll_interval(
    monkeypatch, qapp, qtbot, perf_enabled, level, expected_poll
):
    from app.main import MainWindow
    from app.core.models import StepData

    created = {}

    class DummyRunner:
        def __init__(self, *a, **k):
            created["inst"] = self
            created["perf_mode"] = k.get("perf_mode")
            self.poll_interval = None
            self.finished = DummySignal()
            self.log = DummySignal()
            self.errorOccurred = DummySignal()
            self.requestCrosshair = DummySignal()

        def isRunning(self):
            return False

        def start(self):
            return None

    monkeypatch.setattr("app.main.MacroRunner", DummyRunner)
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.steps.append(StepData(id="s1", name="Test", type="comment"))
    win.chkPerfPlayback.setChecked(perf_enabled)
    idx = win.cbPerfLevel.findData(level)
    if idx >= 0:
        win.cbPerfLevel.setCurrentIndex(idx)
    win.run_macro()

    assert created["inst"].poll_interval == expected_poll
    assert created["perf_mode"] is perf_enabled

    win.close()


def test_perf_settings_load_from_qsettings(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    st = QSettings("ImageMacro", "MVP")
    st.setValue("general/perf_playback", False)
    st.setValue("general/perf_recording", False)
    st.setValue("general/perf_level", 2)
    st.sync()

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    assert win.chkPerfPlayback.isChecked() is False
    assert win.chkPerfRecording.isChecked() is False
    assert win.cbPerfLevel.currentData() == 2

    win.close()


def test_perf_settings_invalid_level_fallback(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    st = QSettings("ImageMacro", "MVP")
    prev = st.value("general/perf_level")
    had = st.contains("general/perf_level")
    st.setValue("general/perf_level", "invalid")
    st.sync()
    try:
        monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

        win = MainWindow()
        qtbot.addWidget(win)
        win.hide()

        assert win.cbPerfLevel.currentData() == 1
        win.close()
    finally:
        if had:
            st.setValue("general/perf_level", prev)
        else:
            st.remove("general/perf_level")
        st.sync()


def test_general_settings_signal_connections_are_not_duplicated(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    calls = {"n": 0}

    def fake_save():
        calls["n"] += 1

    win._save_general_settings = fake_save
    win._load_general_settings()
    win._load_general_settings()

    before = calls["n"]
    win.chkPerfPlayback.setChecked(not win.chkPerfPlayback.isChecked())
    assert calls["n"] - before == 1

    win.close()


def test_perf_settings_save_to_qsettings(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.chkPerfPlayback.setChecked(False)
    win.chkPerfRecording.setChecked(True)
    idx = win.cbPerfLevel.findData(3)
    if idx >= 0:
        win.cbPerfLevel.setCurrentIndex(idx)
    win._save_general_settings()

    st = QSettings("ImageMacro", "MVP")
    assert st.value("general/perf_playback", type=bool) is False
    assert st.value("general/perf_recording", type=bool) is True
    assert st.value("general/perf_level", type=int) == 3

    win.close()


def test_run_macro_when_already_running_does_not_create_new_runner(monkeypatch, qapp, qtbot):
    from app.main import MainWindow
    from app.core.models import StepData

    class RunningRunner:
        def isRunning(self):
            return True

    def fail_runner_ctor(*a, **k):
        raise AssertionError("MacroRunner should not be constructed when already running")

    monkeypatch.setattr("app.main.MacroRunner", fail_runner_ctor)
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    warnings = []
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.warn = lambda msg: warnings.append(msg)
    win.steps.append(StepData(id="s1", name="Test", type="comment"))
    win.runner = RunningRunner()

    win.run_macro()

    assert warnings and "Already running." in warnings[-1]
    assert isinstance(win.runner, RunningRunner)
    win.close()


def test_run_macro_start_failure_restores_ui_state(monkeypatch, qapp, qtbot):
    from app.main import MainWindow
    from app.core.models import StepData

    class LocalSignal:
        def connect(self, *a, **k):
            return None

    class FailingRunner:
        def __init__(self, *a, **k):
            self.finished = LocalSignal()
            self.log = LocalSignal()

        def isRunning(self):
            return False

        def start(self):
            raise RuntimeError("start failed")

    monkeypatch.setattr("app.main.MacroRunner", FailingRunner)
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    calls = {"min": 0, "normal": 0}
    errors = []
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.err = lambda msg: errors.append(msg)
    win.steps.append(StepData(id="s1", name="Test", type="comment"))
    win.chkAutoMin.setChecked(True)
    win.showMinimized = lambda: calls.__setitem__("min", calls["min"] + 1)
    win.showNormal = lambda: calls.__setitem__("normal", calls["normal"] + 1)

    win.run_macro()

    assert calls["min"] == 1
    assert calls["normal"] == 1
    assert win._was_minimized is False
    assert win.runner is None
    assert win.act_run.isEnabled() is True
    assert win.act_stop.isEnabled() is False
    assert win.act_record.isEnabled() is True
    assert win.btnRun.isEnabled() is True
    assert win.btnStop.isEnabled() is False
    assert errors and "Failed to start macro:" in errors[-1]
    win.close()


def test_stop_macro_updates_ui_when_running(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    class StoppableRunner:
        def __init__(self):
            self.stopped = False

        def isRunning(self):
            return True

        def stop(self):
            self.stopped = True

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.runner = StoppableRunner()
    win.act_stop.setEnabled(True)
    win.btnStop.setEnabled(True)

    win.stop_macro()

    assert win.runner.stopped is True
    assert win.act_stop.isEnabled() is False
    assert win.btnStop.isEnabled() is False
    win.close()


def test_toggle_record_blocked_while_macro_running(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    class RunningRunner:
        def isRunning(self):
            return True

    called = {"start": 0}
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.runner = RunningRunner()
    win._start_record = lambda: called.__setitem__("start", called["start"] + 1)
    win.act_record.setChecked(True)
    win.btnRecord.setChecked(True)

    win.toggle_record(True)

    assert called["start"] == 0
    assert win.act_record.isChecked() is False
    assert win.btnRecord.isChecked() is False
    win.close()


def test_toggle_record_start_stop_flow_minimize_restore(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    calls = {"start": 0, "stop": 0, "min": 0, "normal": 0, "activate": 0}
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.chkAutoMin.setChecked(True)

    win._start_record = lambda: calls.__setitem__("start", calls["start"] + 1)
    win._stop_record = lambda show_summary=True: calls.__setitem__("stop", calls["stop"] + 1)
    win.showMinimized = lambda: calls.__setitem__("min", calls["min"] + 1)
    win.showNormal = lambda: calls.__setitem__("normal", calls["normal"] + 1)
    win.activateWindow = lambda: calls.__setitem__("activate", calls["activate"] + 1)

    win.toggle_record(True)
    assert calls["start"] == 1
    assert calls["min"] == 1
    assert win._was_minimized is True

    win.toggle_record(False)
    assert calls["stop"] == 1
    assert calls["normal"] == 1
    assert calls["activate"] == 1
    assert win._was_minimized is False
    win.close()


def test_on_macro_finished_resets_runtime_state(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    class Signal:
        def __init__(self):
            self.disconnected = 0

        def connect(self, *a, **k):
            return None

        def disconnect(self, *a, **k):
            self.disconnected += 1

    class DummyRunner:
        def __init__(self):
            self.debugEvent = Signal()
            self.stepChanged = Signal()

        def isRunning(self):
            return False

    calls = {"normal": 0}
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.runner = DummyRunner()
    win._was_minimized = True
    win._active_step_index = 4
    win.showNormal = lambda: calls.__setitem__("normal", calls["normal"] + 1)
    win.act_run.setEnabled(False)
    win.act_stop.setEnabled(True)
    win.act_record.setEnabled(False)
    win.btnRun.setEnabled(False)
    win.btnStop.setEnabled(True)

    win._on_macro_finished(True)

    assert calls["normal"] == 1
    assert win.act_run.isEnabled() is True
    assert win.act_stop.isEnabled() is False
    assert win.act_record.isEnabled() is True
    assert win.btnRun.isEnabled() is True
    assert win.btnStop.isEnabled() is False
    assert win._active_step_index is None
    assert win.runner is None
    win.close()


def test_trigger_start_log_filtered_by_default(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.delenv("IMAGEMACRO_TRIGGER_START_LOG", raising=False)
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(MainWindow, "_load_triggers", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.TriggerWatcher.start", lambda self: None, raising=False)

    logs = []
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.info = lambda msg: logs.append(msg)

    win._on_trigger_log("Trigger Watcher Started.")
    win._on_trigger_log("[Trigger] Fired: A")

    assert logs == ["[Trigger] Fired: A"]
    win.close()


def test_trigger_start_log_can_be_enabled_via_env(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setenv("IMAGEMACRO_TRIGGER_START_LOG", "1")
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(MainWindow, "_load_triggers", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.TriggerWatcher.start", lambda self: None, raising=False)

    logs = []
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.info = lambda msg: logs.append(msg)

    win._on_trigger_log("Trigger Watcher Started.")

    assert logs == ["Trigger Watcher Started."]
    win.close()

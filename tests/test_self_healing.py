import os
import sys
from types import SimpleNamespace

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.exceptions import ExecutionError, ResourceError
from app.core.models import RepeatConfig, StepData
from app.core.runner import MacroRunner


class _DummyMSS:
    monitors = [{"left": 0, "top": 0, "width": 1, "height": 1}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def grab(self, region):
        return None


def test_self_healing_recovers_on_third_attempt(monkeypatch):
    step = StepData(id="img_retry_3", name="Retry3", type="image_click")
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1, stop_on_fail=True), dry_run=True)
    runner._resource_retry_default_attempts = 3
    runner._resource_retry_default_delay_ms = 0
    events = []
    calls = {"count": 0}

    def _capture(level, event, **payload):
        events.append((level, event, payload))

    def _fake_exec_step(sct, mon, st, idx):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise ResourceError("temporary image miss")
        return (True, None, 0)

    runner._write_structured_event = _capture  # type: ignore[assignment]
    runner._exec_step = _fake_exec_step  # type: ignore[assignment]
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=lambda: _DummyMSS()))

    runner.run()

    retry_events = [evt for evt in events if evt[1] == "step_retry"]
    finished_events = [evt for evt in events if evt[1] == "run_finished"]

    assert calls["count"] == 3
    assert len(retry_events) == 2
    assert any(evt[1] == "step_retry_success" for evt in events)
    assert finished_events
    assert finished_events[0][2]["success"] is True
    assert finished_events[0][2]["retry_count"] == 2
    assert finished_events[0][2]["recovery_status"] is True
    assert runner.engine_state == "IDLE"


def test_self_healing_final_failure_releases_controls(monkeypatch):
    step = StepData(id="img_retry_fail", name="RetryFail", type="image_click")
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1, stop_on_fail=True), dry_run=True)
    runner._resource_retry_default_attempts = 1
    runner._resource_retry_default_delay_ms = 0
    events = []
    calls = {"count": 0}
    release_calls = {"count": 0}

    def _capture(level, event, **payload):
        events.append((level, event, payload))

    def _fake_exec_step(sct, mon, st, idx):
        calls["count"] += 1
        raise ResourceError("always missing")

    def _fake_release():
        release_calls["count"] += 1

    runner._write_structured_event = _capture  # type: ignore[assignment]
    runner._exec_step = _fake_exec_step  # type: ignore[assignment]
    runner._release_runtime_controls = _fake_release  # type: ignore[assignment]
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=lambda: _DummyMSS()))

    runner.run()

    step_exception_events = [evt for evt in events if evt[1] == "step_exception"]
    recovery_events = [evt for evt in events if evt[1] == "step_recovery"]
    finished_events = [evt for evt in events if evt[1] == "run_finished"]

    assert calls["count"] == 2
    assert release_calls["count"] >= 1
    assert step_exception_events
    assert step_exception_events[0][2]["exception_type"] == ExecutionError.__name__
    assert recovery_events
    assert recovery_events[0][2]["recovered"] is True
    assert finished_events
    assert finished_events[0][2]["success"] is False
    assert finished_events[0][2]["retry_count"] == 1
    assert finished_events[0][2]["recovery_status"] is True
    assert runner.engine_state == "IDLE"

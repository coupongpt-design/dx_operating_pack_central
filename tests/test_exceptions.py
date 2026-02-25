import os
import sys
from types import SimpleNamespace

import pytest

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.exceptions import (  # noqa: E402
    ActionError,
    ExecutionError,
    MacroBaseError,
    ResourceError,
    TargetWindowError,
)
from app.core.models import RepeatConfig, StepData  # noqa: E402
from app.core.runner import MacroRunner  # noqa: E402


class _DummyMSS:
    monitors = [{"left": 0, "top": 0, "width": 1, "height": 1}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def grab(self, region):
        return None


def test_exception_hierarchy_is_consistent():
    assert issubclass(ExecutionError, MacroBaseError)
    assert issubclass(ResourceError, MacroBaseError)
    assert issubclass(ActionError, MacroBaseError)
    assert issubclass(TargetWindowError, MacroBaseError)


def test_validate_step_resources_raises_resource_error_for_missing_template():
    runner = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    step = StepData(
        id="img1",
        name="MissingTemplate",
        type="image_click",
        anchor_image_path=r"D:\definitely_missing\no_file.png",
    )

    runner._normalize_step_template_path(step)
    with pytest.raises(ResourceError):
        runner._validate_step_resources(step)


def test_validate_step_resources_skips_dynamic_template_path_precheck():
    runner = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    step = StepData(
        id="img_dynamic_1",
        name="DynamicTemplate",
        type="image_click",
        anchor_image_path="{{anchor_path}}",
    )

    # Dynamic placeholder path must be resolved at runtime, not fail at precheck.
    runner._validate_step_resources(step)


def test_validate_step_resources_skips_dynamic_compare_paths_precheck():
    runner = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    step = StepData(
        id="cmp_dynamic_1",
        name="DynamicCompare",
        type="compare_images",
        image_a_path="{{image_a_path}}",
        image_b_path="{{image_b_path}}",
    )

    # Dynamic placeholder paths are runtime-bound and should bypass static existence checks.
    runner._validate_step_resources(step)


def test_runner_emits_target_window_error_telemetry_on_activation_failure(monkeypatch):
    step = StepData(id="s0", name="noop", type="comment")
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True, target_window_title="LostWindow")
    events = []

    def _capture(level, event, **payload):
        events.append((level, event, payload))

    runner._write_structured_event = _capture  # type: ignore[assignment]
    runner._window_manager = SimpleNamespace(
        find_window=lambda title: 123,
        activate_window=lambda hwnd: (_ for _ in ()).throw(RuntimeError("activation failed")),
    )  # type: ignore[assignment]
    runner._exec_step = lambda sct, mon, st, idx: (True, None, 0)  # type: ignore[assignment]
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=lambda: _DummyMSS()))

    runner.run()

    target_events = [evt for evt in events if evt[1] == "target_window_error"]
    assert target_events
    assert target_events[0][2]["exception_type"] == "TargetWindowError"


def test_runner_step_exception_telemetry_includes_step_index_and_type(monkeypatch):
    step = StepData(id="u1", name="UnknownType", type="unknown_type")
    runner = MacroRunner(
        [step],
        repeat=RepeatConfig(repeat_count=1, stop_on_fail=True),
        dry_run=True,
    )
    events = []

    def _capture(level, event, **payload):
        events.append((level, event, payload))

    runner._write_structured_event = _capture  # type: ignore[assignment]
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=lambda: _DummyMSS()))

    runner.run()

    step_events = [evt for evt in events if evt[1] == "step_exception"]
    assert step_events
    assert step_events[0][2]["step_index"] == 0
    assert step_events[0][2]["exception_type"] == "ActionError"
    assert runner.engine_state == "IDLE"

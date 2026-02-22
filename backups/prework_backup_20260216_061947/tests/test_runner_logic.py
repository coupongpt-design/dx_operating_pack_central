import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.models import StepData, RepeatConfig
from app.core.runner import MacroRunner


@pytest.fixture
def patched_runner(monkeypatch):
    import app.core.runner as runner_mod

    # Dummy mss returning simple BGRA image with white digits on black
    class DummyMSS:
        def __init__(self, *a, **k):
            self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def grab(self, region):
            import cv2

            img = np.zeros((20, 20, 4), dtype=np.uint8)
            cv2.putText(img, "5", (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255, 255), 2)
            return img

    # Mock pyautogui
    pg = MagicMock()
    monkeypatch.setattr(runner_mod, "pyautogui", pg, raising=False)
    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)
    return runner_mod, pg


def test_ocr_store_and_context(monkeypatch, patched_runner):
    runner_mod, pg = patched_runner
    step = StepData(
        id="o",
        name="OCR Store",
        type="ocr_store",
        ocr_roi_x=0,
        ocr_roi_y=0,
        ocr_roi_w=20,
        ocr_roi_h=20,
    )
    # Dynamic attributes used by runner
    step.ocr_store_var = "hp_value"
    monkeypatch.setattr("app.core.runner.ImageProcessor.extract_number", lambda self, img, psm_mode=6: 5.0)
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=True)
    ok = r._ocr_store(runner_mod.mss.mss(), runner_mod.mss.mss().monitors[0], step)
    assert ok
    assert "hp_value" in r.variable_context
    assert r.variable_context["hp_value"] is not None


def test_dynamic_substitution_with_context(patched_runner):
    runner_mod, pg = patched_runner
    r = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    r.variable_context["hp_value"] = 123
    text = r._process_dynamic_string("HP is {hp_value}")
    assert text == "HP is 123"


def test_load_data_file_resolves_relative_path(monkeypatch, tmp_path):
    base = tmp_path / "macros"
    base.mkdir()
    macro_path = base / "main.macro"
    step = StepData(id="d0", name="LoadData", type="load_data_file", data_file_path="data.csv")

    called = {}

    def fake_load_csv(path):
        called["path"] = path
        return True, [{"a": "1"}], None

    monkeypatch.setattr("app.core.runner.load_csv", fake_load_csv)
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=True, current_file_path=str(macro_path))
    ok = r._load_data_file(step)
    assert ok
    assert os.path.normpath(called["path"]) == os.path.normpath(str(base / "data.csv"))


def test_screenshot_roi_fullscreen_when_roi_missing(tmp_path):
    class DummyGrab:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class DummyMSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 4, "height": 3}]

        def grab(self, region):
            return DummyGrab(region["width"], region["height"])

    r = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    step = StepData(
        id="sc",
        name="shot",
        type="screenshot_roi",
        screenshot_roi_x=0,
        screenshot_roi_y=0,
        screenshot_roi_w=0,
        screenshot_roi_h=0,
        screenshot_filepath=str(tmp_path / "shot.png"),
    )
    ok = r._screenshot_roi(DummyMSS(), step)
    assert ok
    assert os.path.exists(step.screenshot_filepath)


def test_capture_on_fail_triggers_screenshot(monkeypatch):
    import app.core.runner as runner_mod

    class DummyGrab:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class DummyMSS:
        def __init__(self, *a, **k):
            self.monitors = [{"left": 0, "top": 0, "width": 2, "height": 2}]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def grab(self, region):
            return DummyGrab(region["width"], region["height"])

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    called = {}

    def fake_shot(self, sct, step):
        called["hit"] = True
        return True

    monkeypatch.setattr(MacroRunner, "_screenshot_roi", fake_shot, raising=False)
    step = StepData(id="f1", name="Fail", type="click_point")
    r = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True, capture_on_fail=True)
    r.run()
    assert called.get("hit") is True


def test_perf_mode_pyautogui_settings(monkeypatch):
    import app.core.runner as runner_mod

    dummy_pg = SimpleNamespace(
        PAUSE=0.2,
        MINIMUM_DURATION=0.05,
        MINIMUM_SLEEP=0.01,
        FAILSAFE=False,
    )
    monkeypatch.setattr(runner_mod, "pyautogui", dummy_pg, raising=False)
    monkeypatch.setattr("app.core.input_emulator.pyautogui", dummy_pg)

    r = MacroRunner([], repeat=RepeatConfig(), dry_run=True, perf_mode=True)
    r._apply_perf_settings()
    assert dummy_pg.PAUSE == 0
    assert dummy_pg.MINIMUM_DURATION == 0
    assert dummy_pg.MINIMUM_SLEEP == 0

    r.perf_mode = False
    r._apply_perf_settings()
    assert dummy_pg.PAUSE == 0.2
    assert dummy_pg.MINIMUM_DURATION == 0.05
    assert dummy_pg.MINIMUM_SLEEP == 0.01


def test_perf_mode_poll_interval_default(monkeypatch):
    import app.core.runner as runner_mod
    from app.core.models import RepeatConfig

    dummy_pg = SimpleNamespace(PAUSE=0, MINIMUM_DURATION=0, MINIMUM_SLEEP=0, FAILSAFE=False)
    monkeypatch.setattr(runner_mod, "pyautogui", dummy_pg, raising=False)
    monkeypatch.setattr("app.core.input_emulator.pyautogui", dummy_pg)

    r_fast = MacroRunner([], repeat=RepeatConfig(), dry_run=True, perf_mode=True)
    r_slow = MacroRunner([], repeat=RepeatConfig(), dry_run=True, perf_mode=False)
    assert r_fast.poll_interval == 0.0
    assert r_slow.poll_interval == 0.1


def test_handle_run_macro_rejects_when_max_depth_exceeded(tmp_path):
    child = tmp_path / "child.json"
    child.write_text('{"steps":[{"id":"c1","name":"c","type":"comment"}]}', encoding="utf-8")

    step = StepData(id="r1", name="RunChild", type="run_macro", target_macro_path=str(child))
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=True)
    r.call_stack = [{} for _ in range(r._max_call_depth)]

    assert r._handle_run_macro(step) is False
    assert r._switch_steps is None


def test_handle_run_macro_pushes_state_and_switches(tmp_path):
    child = tmp_path / "child.json"
    child.write_text('{"steps":[{"id":"c1","name":"Child","type":"comment"}]}', encoding="utf-8")

    parent_steps = [
        StepData(id="p1", name="Parent1", type="comment"),
        StepData(id="p2", name="RunChild", type="run_macro", target_macro_path=str(child)),
    ]
    r = MacroRunner(parent_steps, repeat=RepeatConfig(), dry_run=True, current_file_path=str(tmp_path / "parent.json"))
    r.current_step_index = 1

    ok = r._handle_run_macro(parent_steps[1])
    assert ok is True
    assert len(r.call_stack) == 1
    assert r.call_stack[0]["steps"] == parent_steps
    assert r.call_stack[0]["index"] == 1
    assert r._switch_steps is not None
    assert len(r._switch_steps) == 1
    assert r._switch_steps[0].id == "c1"


def test_jump_if_falls_back_to_index_when_id_missing():
    steps = [
        StepData(id="s1", name="A", type="comment"),
        StepData(id="s2", name="B", type="comment"),
        StepData(id="s3", name="C", type="comment"),
    ]
    r = MacroRunner(steps, repeat=RepeatConfig(), dry_run=True)
    r.variable_context["hp"] = 50
    r.evaluator = SimpleNamespace(evaluate=lambda s, ctx, actual_value=None: (True, None))

    s = StepData(
        id="j1",
        name="Jump",
        type="jump_if",
        condition_var="hp",
        condition_operator=">",
        condition_value=10,
        target_true_id="missing-id",
        target_true_index=2,
    )
    ok, goto_id, consumed = r._jump_if(s)
    assert ok is True
    assert goto_id == "s3"
    assert consumed == 0


def test_jump_if_true_without_valid_target_continues():
    steps = [
        StepData(id="s1", name="A", type="comment"),
        StepData(id="s2", name="B", type="comment"),
    ]
    r = MacroRunner(steps, repeat=RepeatConfig(), dry_run=True)
    r.variable_context["flag"] = 1
    r.evaluator = SimpleNamespace(evaluate=lambda s, ctx, actual_value=None: (True, None))

    s = StepData(
        id="j2",
        name="JumpMissing",
        type="jump_if",
        condition_var="flag",
        condition_operator="==",
        condition_value=1,
        target_true_id="missing-id",
        target_true_index=99,
    )
    ok, goto_id, consumed = r._jump_if(s)
    assert ok is True
    assert goto_id is None
    assert consumed == 0


def test_end_loop_counter_and_infinite_behavior():
    r = MacroRunner([], repeat=RepeatConfig(), dry_run=True)

    missing = StepData(id="e0", name="end0", type="end_loop", start_loop_id="missing")
    assert r._end_loop(missing) == (False, None)

    r._loop_counters["loop1"] = 2
    count_step = StepData(id="e1", name="end1", type="end_loop", start_loop_id="loop1")
    assert r._end_loop(count_step) == (True, "loop1")
    assert r._loop_counters["loop1"] == 1
    assert r._end_loop(count_step) == (True, None)
    assert "loop1" not in r._loop_counters

    r._loop_counters["inf"] = 0
    inf_step = StepData(id="e2", name="end2", type="end_loop", start_loop_id="inf")
    assert r._end_loop(inf_step) == (True, "inf")

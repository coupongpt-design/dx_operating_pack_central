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

    def fake_load_data_rows(path):
        called["path"] = path
        return True, [{"a": "1"}], None

    monkeypatch.setattr("app.core.runner.load_data_rows", fake_load_data_rows)
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


def test_process_dynamic_string_replaces_data_and_columns():
    r = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    r._data_list = ["alpha", "beta"]
    r._data_index = 1
    r._data_columns = ["name", "level"]
    r._data_row_values = [["alice", "10"], ["beta", "20"]]

    out = r._process_dynamic_string("loot {data} {name} {level}")
    assert out == "loot beta beta 20"


def test_load_data_file_fails_on_missing_required_column(monkeypatch):
    load = StepData(id="d1", name="Load", type="load_data_file", data_file_path="dummy.csv")
    send = StepData(id="k1", name="Send", type="keyboard", key_string="{email}")
    r = MacroRunner([load, send], repeat=RepeatConfig(), dry_run=True)

    monkeypatch.setattr(
        "app.core.runner.load_data_rows",
        lambda path: (True, [{"name": "alice"}], None),
    )

    ok = r._load_data_file(load)
    assert ok is False


def test_runner_emits_step_started_and_succeeded_with_source_uuid(monkeypatch):
    import app.core.runner as runner_mod

    class DummyMSS:
        def __init__(self, *a, **k):
            self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    step = StepData(id="r1", name="Comment", type="comment")
    step.source_step_id = "step-src-1"
    r = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True)

    started = []
    succeeded = []
    failed = []
    r.stepStarted.connect(lambda sid, name: started.append((sid, name)))
    r.stepSucceeded.connect(lambda sid: succeeded.append(sid))
    r.stepFailed.connect(lambda sid, name, msg: failed.append((sid, name, msg)))

    r.run()

    assert started == [("step-src-1", "Comment")]
    assert succeeded == ["step-src-1"]
    assert failed == []


def test_runner_emits_step_failed_with_source_uuid_on_failure(monkeypatch):
    import app.core.runner as runner_mod

    class DummyMSS:
        def __init__(self, *a, **k):
            self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    bad = StepData(id="bad-runtime", name="Bad", type="unknown_type")
    bad.source_step_id = "bad-source-uuid"
    r = MacroRunner([bad], repeat=RepeatConfig(repeat_count=1), dry_run=True)

    failed = []
    r.stepFailed.connect(lambda sid, name, msg: failed.append((sid, name, msg)))

    r.run()

    assert len(failed) == 1
    assert failed[0][0] == "bad-source-uuid"
    assert failed[0][1] == "Bad"


def test_image_click_applies_click_anchor(monkeypatch, patched_runner):
    runner_mod, _pg = patched_runner
    step = StepData(
        id="img-anchor",
        name="Anchor",
        type="image_click",
        timeout_ms=100,
        poll_ms=1,
        click_anchor="top-left",
    )
    runner = MacroRunner([step], repeat=RepeatConfig(), dry_run=False)
    clicked: dict[str, tuple[int, int]] = {}

    monkeypatch.setattr(
        runner._matcher,
        "find_best_optimized",
        lambda frame, s: SimpleNamespace(ok=True, x=10, y=10, score=0.99, w=20, h=10),
    )
    monkeypatch.setattr(runner, "_perform_click", lambda x, y, s: clicked.setdefault("xy", (x, y)))

    class _Grab:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class _MSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

        def grab(self, region):
            return _Grab(int(region["width"]), int(region["height"]))

    sct = _MSS()
    mon = sct.monitors[0]
    ok, goto_id, consumed = runner._image_click(sct, mon, step, 0)

    assert ok is True
    assert goto_id is None
    assert consumed == 0
    assert clicked.get("xy") == (0, 5)


def test_wait_for_image_matches_without_click(monkeypatch, patched_runner):
    runner_mod, _pg = patched_runner
    step = StepData(
        id="wf1",
        name="Wait Image",
        type="wait_for_image",
        timeout_ms=100,
        poll_ms=1,
        on_match_goto_id="next-step",
    )
    runner = MacroRunner([step], repeat=RepeatConfig(), dry_run=False)
    click_calls = {"count": 0}

    monkeypatch.setattr(
        runner._matcher,
        "find_best_optimized",
        lambda frame, s: SimpleNamespace(ok=True, x=8, y=8, score=0.92, w=6, h=6),
    )
    monkeypatch.setattr(runner, "_perform_click", lambda *args, **kwargs: click_calls.__setitem__("count", click_calls["count"] + 1))

    class _Grab:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class _MSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

        def grab(self, region):
            return _Grab(int(region["width"]), int(region["height"]))

    sct = _MSS()
    mon = sct.monitors[0]
    ok, goto_id, consumed = runner._wait_for_image(sct, mon, step, 0)

    assert ok is True
    assert goto_id == "next-step"
    assert consumed == 0
    assert click_calls["count"] == 0


def test_wait_for_image_times_out(monkeypatch, patched_runner):
    runner_mod, _pg = patched_runner
    step = StepData(
        id="wf2",
        name="Wait Timeout",
        type="wait_for_image",
        timeout_ms=0,
        poll_ms=1,
    )
    runner = MacroRunner([step], repeat=RepeatConfig(), dry_run=False)

    monkeypatch.setattr(
        runner._matcher,
        "find_best_optimized",
        lambda frame, s: SimpleNamespace(ok=False, x=0, y=0, score=0.0, w=0, h=0),
    )

    class _Grab:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class _MSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

        def grab(self, region):
            return _Grab(int(region["width"]), int(region["height"]))

    sct = _MSS()
    mon = sct.monitors[0]
    ok, goto_id, consumed = runner._wait_for_image(sct, mon, step, 0)

    assert ok is False
    assert goto_id is None
    assert consumed == 0


def test_normalize_step_template_path_uses_macro_base(tmp_path):
    macro_path = tmp_path / "macros" / "main.json"
    macro_path.parent.mkdir(parents=True, exist_ok=True)
    macro_path.write_text("{}", encoding="utf-8")

    step = StepData(id="wf-path", name="Path", type="wait_for_image", anchor_image_path="images/a.png")
    runner = MacroRunner([step], repeat=RepeatConfig(), dry_run=True, current_file_path=str(macro_path))
    runner._normalize_step_template_path(step)

    expected = (macro_path.parent / "images" / "a.png").resolve()
    assert step.anchor_image_path == str(expected)


def test_normalize_step_template_path_uses_macro_base_for_relative_target(tmp_path):
    macro_path = tmp_path / "macros" / "main.json"
    macro_path.parent.mkdir(parents=True, exist_ok=True)
    macro_path.write_text("{}", encoding="utf-8")

    step = StepData(
        id="wf-rel-path",
        name="Path",
        type="image_click",
        relative_target_enabled=True,
        relative_target_image_path="images/target.png",
    )
    runner = MacroRunner([step], repeat=RepeatConfig(), dry_run=True, current_file_path=str(macro_path))
    runner._normalize_step_template_path(step)

    expected = (macro_path.parent / "images" / "target.png").resolve()
    assert step.relative_target_image_path == str(expected)


def test_image_click_relative_target_search_clicks_target(monkeypatch, patched_runner):
    _runner_mod, _pg = patched_runner
    step = StepData(
        id="img-relative",
        name="Relative",
        type="image_click",
        timeout_ms=100,
        poll_ms=1,
        relative_target_enabled=True,
        relative_target_image_path="target.png",
        relative_target_png_bytes=b"target-bytes",
        relative_search_right=100,
        relative_search_bottom=30,
    )
    runner = MacroRunner([step], repeat=RepeatConfig(), dry_run=False)
    clicked: dict[str, tuple[int, int]] = {}

    def fake_match(frame, current_step):
        current_path = str(getattr(current_step, "anchor_image_path", "") or "")
        if current_path.endswith("target.png"):
            return SimpleNamespace(ok=True, x=60, y=10, score=0.97, w=12, h=8)
        return SimpleNamespace(ok=True, x=25, y=20, score=0.99, w=10, h=6)

    monkeypatch.setattr(runner._matcher, "find_best_optimized", fake_match)
    monkeypatch.setattr(runner, "_perform_click", lambda x, y, s: clicked.setdefault("xy", (x, y)))

    class _Grab:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class _MSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 200, "height": 100}]

        def grab(self, region):
            return _Grab(int(region["width"]), int(region["height"]))

    sct = _MSS()
    mon = sct.monitors[0]
    ok, goto_id, consumed = runner._image_click(sct, mon, step, 0)

    assert ok is True
    assert goto_id is None
    assert consumed == 0
    assert clicked.get("xy") == (80, 27)


def test_image_click_relative_target_search_clicks_target_from_embedded_bytes(monkeypatch, patched_runner):
    _runner_mod, _pg = patched_runner
    step = StepData(
        id="img-relative-bytes",
        name="Relative Bytes",
        type="image_click",
        timeout_ms=100,
        poll_ms=1,
        relative_target_enabled=True,
        relative_target_png_bytes=b"target-bytes-only",
        relative_search_right=100,
        relative_search_bottom=30,
    )
    runner = MacroRunner([step], repeat=RepeatConfig(), dry_run=False)
    clicked: dict[str, tuple[int, int]] = {}

    def fake_match(frame, current_step):
        if getattr(current_step, "png_bytes", None) == b"target-bytes-only":
            return SimpleNamespace(ok=True, x=60, y=10, score=0.97, w=12, h=8)
        return SimpleNamespace(ok=True, x=25, y=20, score=0.99, w=10, h=6)

    monkeypatch.setattr(runner._matcher, "find_best_optimized", fake_match)
    monkeypatch.setattr(runner, "_perform_click", lambda x, y, s: clicked.setdefault("xy", (x, y)))

    class _Grab:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.rgb = b"\x00" * (width * height * 3)

    class _MSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 200, "height": 100}]

        def grab(self, region):
            return _Grab(int(region["width"]), int(region["height"]))

    sct = _MSS()
    mon = sct.monitors[0]
    ok, goto_id, consumed = runner._image_click(sct, mon, step, 0)

    assert ok is True
    assert goto_id is None
    assert consumed == 0
    assert clicked.get("xy") == (80, 27)


def test_text_paste_auto_enter_enabled(monkeypatch, patched_runner):
    runner_mod, pg = patched_runner
    step = StepData(id="t1", name="Text", type="text", key_string="hello")
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=False, auto_enter_after_text=True)
    copied = []
    monkeypatch.setattr(r, "_get_clipboard_text", lambda: "prev")
    monkeypatch.setattr(r, "_set_clipboard_text", lambda text: copied.append(text) or True)

    ok = r._text_paste(step)

    assert ok is True
    pg.hotkey.assert_called_with("ctrl", "v")
    pg.press.assert_called_with("enter")
    assert copied[0] == "hello"
    assert copied[-1] == "prev"


def test_text_paste_auto_enter_disabled(monkeypatch, patched_runner):
    runner_mod, pg = patched_runner
    step = StepData(id="t2", name="Text", type="text", key_string="hello")
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=False, auto_enter_after_text=False)
    monkeypatch.setattr(r, "_get_clipboard_text", lambda: "prev")
    monkeypatch.setattr(r, "_set_clipboard_text", lambda text: True)

    ok = r._text_paste(step)

    assert ok is True
    assert not pg.press.called


def test_key_text_mode_does_not_auto_enter_for_non_text_step(monkeypatch, patched_runner):
    runner_mod, pg = patched_runner
    step = StepData(id="k1", name="KeyAsText", type="key", key_string="abc")
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=False, auto_enter_after_text=True)

    ok, _ = r._key_press(step)

    assert ok is True
    assert not pg.press.called

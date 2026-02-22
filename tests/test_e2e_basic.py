import os
import sys
import types
import json
import tempfile
import pytest

# Headless Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTime

from app.core.models import StepData, RepeatConfig, TriggerData
from app.core.runner import MacroRunner
from app.core.trigger_engine import TriggerWatcher
from app.core.scheduler import MacroScheduler
from app.io.macro_io import MacroIO
from app.ui.dialogs import BranchStepDialog
from app.utils.matcher import MatchResult


class _DummyMSS:
    """Lightweight stand-in for mss.mss to avoid real screen capture."""

    def __init__(self):
        self.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def grab(self, region):
        w = int(region.get("width", 1) or 1)
        h = int(region.get("height", 1) or 1)

        class _Grab:
            width = w
            height = h
            rgb = b"\x00" * (w * h * 3)

        return _Grab()


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _patch_clipboard(monkeypatch):
    # Stub pyperclip and Qt clipboard to avoid real clipboard access
    buf = {"text": ""}
    dummy_clip = types.SimpleNamespace(copy=lambda t: buf.__setitem__("text", t), paste=lambda: buf["text"])
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ["QT_QPA_PLATFORM"])
    monkeypatch.setitem(sys.modules, "pyperclip", dummy_clip)
    try:
        from PyQt5 import QtWidgets
    except Exception:
        return
    cb = QtWidgets.QApplication.clipboard()
    monkeypatch.setattr(cb, "setText", lambda t: buf.__setitem__("text", t), raising=False)
    monkeypatch.setattr(cb, "text", lambda: buf["text"], raising=False)


def _patch_pyautogui(monkeypatch):
    import app.core.runner as runner_mod
    dummy = types.SimpleNamespace(
        hotkey=lambda *a, **k: None,
        keyDown=lambda *a, **k: None,
        keyUp=lambda *a, **k: None,
        press=lambda *a, **k: None,
        moveTo=lambda *a, **k: None,
        mouseDown=lambda *a, **k: None,
        mouseUp=lambda *a, **k: None,
        doubleClick=lambda *a, **k: None,
        click=lambda *a, **k: None,
        hscroll=lambda *a, **k: None,
        scroll=lambda *a, **k: None,
        typewrite=lambda *a, **k: None,
    )
    monkeypatch.setattr(runner_mod, "pyautogui", dummy, raising=False)


def _patch_mss(monkeypatch):
    import app.core.runner as runner_mod
    import app.core.trigger_engine as trig_mod
    monkeypatch.setattr(runner_mod.mss, "mss", _DummyMSS, raising=False)
    monkeypatch.setattr(trig_mod.mss, "mss", _DummyMSS, raising=False)


@pytest.fixture
def patched_env(monkeypatch):
    _patch_clipboard(monkeypatch)
    _patch_pyautogui(monkeypatch)
    _patch_mss(monkeypatch)


def test_e2e_1_macro_save_load_run_loop(monkeypatch, patched_env, qapp, tmp_path):
    """1) Save -> Load -> Run with loop config."""
    steps = [
        StepData(id="s1", name="Text", type="text", key_string="hello", key_times=1),
        StepData(id="s2", name="Wait", type="wait", wait_ms=5),
    ]
    rc = RepeatConfig(repeat_count=2, repeat_cooldown_ms=0, stop_on_fail=True, max_duration_ms=1000)

    macro_path = tmp_path / "case1.macro"
    MacroIO.save_macro(str(macro_path), steps, rc)
    loaded_steps, loaded_rc = MacroIO.load_macro(str(macro_path))
    assert len(loaded_steps) == 2
    assert loaded_rc.repeat_count == 2

    runner = MacroRunner(loaded_steps, repeat=loaded_rc, dry_run=True, start_index=0, capture_on_fail=False, parent=None)
    runner.run()
    assert runner._stop is False


def test_e2e_2_branch_dialog_roundtrip(patched_env, qapp):
    """2) Branch dialog: add/rename/sort and apply back to step."""
    step = StepData(id="s1", name="Branch Step", type="image_branch", timeout_ms=2000, pre_delay_ms=100)
    step.conditional_targets = [{
        "id": "t1",
        "name": "Target 1",
        "goto_id": None,
        "png_bytes": None,
        "threshold": 0.9,
    }]
    all_steps = [step, StepData(id="s2", name="Next", type="wait")]

    dlg = BranchStepDialog(step, all_steps, parent=None)
    dlg._sort_targets(True)
    dlg.accept()
    updated = dlg.get_step_data()

    assert updated.type == "image_branch"
    assert len(updated.conditional_targets) == 1
    assert updated.conditional_targets[0].get("name") in ("Target 1",)


def test_e2e_3_trigger_watcher(monkeypatch, patched_env, qapp):
    """3) Trigger watcher fires when matcher reports success."""
    # Patch matcher to always find a match
    import app.core.trigger_engine as trig_mod

    def _ok(frame, step):
        return MatchResult(True, 0, 0, 1.0)

    monkeypatch.setattr(trig_mod.Matcher, "find_best_optimized", lambda self, frame, step: _ok(frame, step), raising=False)

    cond_step = StepData(id="c1", name="Cond", type="image_click", threshold=0.8, timeout_ms=100)
    trigger = TriggerData(id="t1", name="Trig", enabled=True, condition_step=cond_step)
    watcher = TriggerWatcher([trigger])
    fired = watcher._check_condition(_DummyMSS(), _DummyMSS().monitors[0], trigger)
    assert fired is True


def test_e2e_4_scheduler_requests_run(patched_env, qapp):
    """4) Scheduler enqueues macro at scheduled time."""
    sched = MacroScheduler()
    collected = []
    sched.requestRunMacro.connect(lambda p: collected.append(p))

    sched.set_macro_queue(["/tmp/a.macro"])
    sched.set_target_time(QTime.currentTime())
    sched.running = True
    sched.ran_today = False
    sched._check_time()
    assert collected


def test_e2e_5_record_done_appends(qapp):
    """5) Simulate record finished callback appending steps."""
    from app.main import MainWindow

    win = MainWindow()
    initial = len(win.steps)
    new_steps = [
        StepData(id="r1", name="Rec Click", type="click_point", click_x=1, click_y=1),
        StepData(id="r2", name="Rec Key", type="text", key_string="hi"),
    ]
    win._on_record_done(new_steps)
    assert len(win.steps) == initial + 2
    win.close()


def test_e2e_6_screenshot_roi(monkeypatch, patched_env, qapp, tmp_path):
    """6) Screenshot ROI saves a file."""
    runner = MacroRunner([], repeat=RepeatConfig(), dry_run=True, start_index=0, capture_on_fail=False, parent=None)
    step = StepData(
        id="sc1",
        name="Shot",
        type="screenshot_roi",
        screenshot_roi_x=0,
        screenshot_roi_y=0,
        screenshot_roi_w=2,
        screenshot_roi_h=2,
        screenshot_filepath=str(tmp_path / "shot.png"),
    )
    ok = runner._screenshot_roi(_DummyMSS(), step)
    assert ok
    assert os.path.exists(step.screenshot_filepath)


def test_e2e_7_text_paste(monkeypatch, patched_env, qapp):
    """7) Text action with non-ASCII uses clipboard path without exception."""
    steps = [StepData(id="t1", name="Text", type="text", key_string="안녕", key_times=2)]
    runner = MacroRunner(steps, repeat=RepeatConfig(repeat_count=1), dry_run=False, start_index=0, capture_on_fail=False, parent=None)
    runner.run()
    assert runner._stop is False


def test_e2e_8_load_data_file(monkeypatch, patched_env, qapp, tmp_path):
    """8) Load data file step populates runner data lists."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("name,age\nAlice,30\nBob,25", encoding="utf-8")
    step = StepData(id="d1", name="Load", type="load_data_file", data_file_path=str(csv_path))
    runner = MacroRunner([], repeat=RepeatConfig(), dry_run=True, start_index=0, capture_on_fail=False, parent=None)
    ok = runner._load_data_file(step)
    assert ok
    assert runner._data_list == ["Alice", "Bob"]


def test_e2e_9_ocr(monkeypatch, patched_env, qapp):
    """9) OCR check succeeds when pytesseract returns expected text."""
    # Patch pytesseract
    class _PyT:
        @staticmethod
        def image_to_string(img, lang=None, config=None):
            return "Hello World"
    monkeypatch.setitem(sys.modules, "pytesseract", _PyT)

    steps = [StepData(
        id="o1", name="OCR", type="ocr_check_text",
        ocr_expected_text="Hello", ocr_lang="eng", ocr_preprocess_mode="none",
        ocr_roi_x=0, ocr_roi_y=0, ocr_roi_w=2, ocr_roi_h=2,
        on_match_goto_id=None,
    )]
    runner = MacroRunner(steps, repeat=RepeatConfig(repeat_count=1), dry_run=True, start_index=0, capture_on_fail=False, parent=None)
    ok, goto = runner._ocr_check_text(_DummyMSS(), _DummyMSS().monitors[0], steps[0])
    assert ok is True

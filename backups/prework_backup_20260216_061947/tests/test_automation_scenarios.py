import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSettings

from app.core.models import StepData, RepeatConfig
from app.core.runner import MacroRunner
from app.core.trigger_engine import TriggerWatcher
from app.main import MainWindow


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
def dummy_mss():
    class DummyMSS:
        def __init__(self, *a, **k):
            self.monitors = [{"left": 0, "top": 0, "width": 100, "height": 100}]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def grab(self, region):
            import numpy as np

            w = int(region.get("width", 1) or 1)
            h = int(region.get("height", 1) or 1)
            # BGRA zeros
            return np.zeros((h, w, 4), dtype=np.uint8)

    return DummyMSS


@pytest.fixture
def patched_runner(monkeypatch, dummy_mss):
    import app.core.runner as runner_mod

    # mock pyautogui completely
    pg = MagicMock()
    monkeypatch.setattr(runner_mod, "pyautogui", pg, raising=False)
    monkeypatch.setattr(runner_mod.mss, "mss", dummy_mss, raising=False)
    return runner_mod, pg


def test_hotkey_signals(monkeypatch, qapp):
    # prevent global hotkey registration
    from app.ui import hotkeys as hk_mod

    monkeypatch.setattr(hk_mod.SystemHotkeys, "install", lambda self: None, raising=False)
    monkeypatch.setattr(hk_mod.SystemHotkeys, "uninstall", lambda self: None, raising=False)
    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    win.run_macro = MagicMock()
    win.stop_macro = MagicMock()
    win._act_run_from_hotkey()
    win._act_stop_from_hotkey()
    assert win.run_macro.called
    assert win.stop_macro.called
    win.close()


def test_trigger_watcher_resilience(monkeypatch, dummy_mss):
    # Patch mss
    import app.core.trigger_engine as trig_mod

    monkeypatch.setattr(trig_mod.mss, "mss", dummy_mss, raising=False)
    # Dummy trigger
    from app.core.models import TriggerData, StepData

    cond = StepData(id="c", name="Cond", type="image_click")
    trig = TriggerData(id="t1", name="Trig", condition_step=cond)
    tw = TriggerWatcher([trig])
    logs = []
    tw.log.connect(logs.append)

    def boom(*a, **k):
        tw._stop = True
        raise Exception("boom")

    monkeypatch.setattr(tw, "_check_condition", boom)

    # run synchronously to capture log deterministically
    tw.run()
    assert any("boom" in msg for msg in logs)


def test_macro_runner_screenshot(patched_runner, tmp_path):
    runner_mod, pg = patched_runner
    r = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    step = StepData(
        id="sc",
        name="shot",
        type="screenshot_roi",
        screenshot_roi_x=0,
        screenshot_roi_y=0,
        screenshot_roi_w=2,
        screenshot_roi_h=2,
        screenshot_filepath=str(tmp_path / "shot.png"),
    )
    ok = r._screenshot_roi(runner_mod.mss.mss(), step)
    assert ok
    assert os.path.exists(step.screenshot_filepath)


def test_macro_runner_ocr(monkeypatch, patched_runner):
    runner_mod, pg = patched_runner

    class DummyTesseract:
        @staticmethod
        def image_to_string(img, lang=None, config=None):
            return "123"

    sys.modules["pytesseract"] = DummyTesseract
    import app.core.vision as vision
    monkeypatch.setattr(vision.ImageProcessor, "extract_number", lambda self, img, psm_mode=6: 123, raising=False)
    step = StepData(
        id="o",
        name="OCR",
        type="ocr_check_text",
        ocr_expected_text="123",
        ocr_lang="eng",
        ocr_preprocess_mode="none",
        ocr_roi_x=0,
        ocr_roi_y=0,
        ocr_roi_w=2,
        ocr_roi_h=2,
        on_match_goto_id="t1",
    )
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=True)
    ok, goto = r._ocr_check_text(runner_mod.mss.mss(), runner_mod.mss.mss().monitors[0], step)
    assert ok is True
    assert goto == "t1"


def test_macro_runner_screen_check_ocr_goto(monkeypatch, patched_runner):
    runner_mod, pg = patched_runner
    import app.core.vision as vision

    monkeypatch.setattr(vision.ImageProcessor, "extract_number", lambda self, img, psm_mode=6: 50, raising=False)
    step = StepData(
        id="sc1",
        name="ScreenCheck",
        type="screen_check",
        screen_check_mode="ocr_check_text",
        ocr_expected_text="50",
        ocr_lang="eng",
        ocr_preprocess_mode="none",
        ocr_roi_x=0,
        ocr_roi_y=0,
        ocr_roi_w=2,
        ocr_roi_h=2,
        on_match_goto_id="t2",
    )
    r = MacroRunner([step], repeat=RepeatConfig(), dry_run=True)
    ok, goto = r._screen_check(runner_mod.mss.mss(), runner_mod.mss.mss().monitors[0], step)
    assert ok is True
    assert goto == "t2"


def test_macro_runner_dynamic_and_loop(patched_runner):
    runner_mod, pg = patched_runner
    import random

    random.seed(0)
    steps = [
        StepData(id="start", name="StartLoop", type="start_loop", loop_count=2),
        StepData(id="click", name="Click", type="click_point", click_x=1, click_y=2, click_btn="left"),
        StepData(id="end", name="EndLoop", type="end_loop", start_loop_id="start"),
    ]
    r = MacroRunner(steps, repeat=RepeatConfig(), dry_run=False)
    r.run()
    # click should be called twice due to loop_count=2
    assert pg.moveTo.call_count >= 2
    assert pg.click.call_count >= 2


def test_load_data_and_dynamic_strings(patched_runner, tmp_path):
    runner_mod, pg = patched_runner
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("name,age\nAlice,30\nBob,25", encoding="utf-8")
    step = StepData(id="d1", name="Load", type="load_data_file", data_file_path=str(csv_path))
    r = MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    ok = r._load_data_file(step)
    assert ok
    # dynamic tokens in text
    s = StepData(id="t1", name="Text", type="text", key_string="Hello {seq}")
    out1 = r._process_dynamic_string(s.key_string)
    out2 = r._process_dynamic_string(s.key_string)
    assert out1 != out2

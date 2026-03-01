"""
Standalone backend sanity tests (no UI).

Run with:
    python test_core_logic.py

Covers:
- Dynamic string tokens (#/@/?/{seq}/{counter})
- CSV data loading
- OCR stub path (pytesseract + ROI handling)

These tests monkeypatch external deps (mss/pyautogui/pytesseract)
to avoid GUI/screen access.
"""

import os
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def patch_deps():
    """Patch runner deps to avoid real screen/clipboard access."""
    import app.core.runner as runner

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
            # BGRA array to satisfy cv2.cvtColor expectations in runner
            return np.zeros((h, w, 4), dtype=np.uint8)

    # Stub pyautogui
    runner.pyautogui = SimpleNamespace(
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
    # Stub mss
    runner.mss.mss = DummyMSS
    return runner


@pytest.fixture
def runner():
    return patch_deps()


def test_dynamic_strings(runner):
    from app.core.models import StepData, RepeatConfig

    steps = [
        StepData(id="t1", name="Text", type="text", key_string="#@?{seq}{seq:name}-{counter:x}"),
    ]
    rc = RepeatConfig(repeat_count=2, repeat_cooldown_ms=0, stop_on_fail=True, max_duration_ms=100)
    r = runner.MacroRunner(steps, repeat=rc, dry_run=True)
    # First pass
    s = steps[0]
    out1 = r._process_dynamic_string(s.key_string)
    out2 = r._process_dynamic_string(s.key_string)
    print("Dynamic string outputs:", out1, out2)
    assert out1 != out2  # random parts differ
    assert out1.split("-")[1].isdigit()


def test_load_data_file(runner):
    from app.core.models import StepData, RepeatConfig

    csv_path = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    csv_path.write(b"name,age\nAlice,30\nBob,25")
    csv_path.close()
    step = StepData(id="d1", name="Load", type="load_data_file", data_file_path=csv_path.name)
    r = runner.MacroRunner([], repeat=RepeatConfig(), dry_run=True)
    ok = r._load_data_file(step)
    print("Load data ok:", ok, "list:", r._data_list)
    assert ok and r._data_list == ["Alice", "Bob"]
    os.unlink(csv_path.name)


def test_ocr_stub(runner, monkeypatch):
    from app.core.models import StepData, RepeatConfig

    class DummyTesseract:
        @staticmethod
        def image_to_string(img, lang=None, config=None):
            return "123"

    sys.modules["pytesseract"] = DummyTesseract
    # Force ImageProcessor to return numeric value without real OCR
    import app.core.vision as vision
    monkeypatch.setattr(vision.ImageProcessor, "extract_number", lambda self, img, psm_mode=6: 123, raising=False)
    step = StepData(
        id="o1",
        name="OCR",
        type="ocr_check_text",
        ocr_expected_text="123",
        ocr_lang="eng",
        ocr_preprocess_mode="none",
        ocr_roi_x=0,
        ocr_roi_y=0,
        ocr_roi_w=2,
        ocr_roi_h=2,
    )
    r = runner.MacroRunner([step], repeat=RepeatConfig(), dry_run=True)
    ok, goto = r._ocr_check_text(runner.mss.mss(), {"left": 0, "top": 0, "width": 100, "height": 100}, step)
    print("OCR ok:", ok, "goto:", goto)
    assert ok is True


def main():
    runner = patch_deps()
    test_dynamic_strings(runner)
    test_load_data_file(runner)
    test_ocr_stub(runner)
    print("All core logic tests completed.")


if __name__ == "__main__":
    main()

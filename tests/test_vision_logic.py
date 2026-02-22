import os
import sys
import numpy as np
import cv2
import pytest
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.vision import ImageProcessor


def _make_text_image(text: str, fg=(0, 0, 0), bg=(255, 255, 255), size=(60, 160)):
    h, w = size
    img = np.full((h, w, 3), bg, dtype=np.uint8)
    cv2.putText(img, text, (5, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, fg, 2, cv2.LINE_AA)
    return img


def test_preprocess_scales_and_thresholds():
    proc = ImageProcessor(scale_factor=2.0, invert=False)
    img = _make_text_image("123")
    pre = proc.preprocess_for_ocr(img, psm_mode=6)
    assert pre.shape[0] > img.shape[0] and pre.shape[1] > img.shape[1]
    # should be single channel
    assert len(pre.shape) == 2


def test_extract_number_basic(monkeypatch):
    proc = ImageProcessor()

    def fake_ocr(img, lang=None, config=None):
        return "HP: 1234 / 5000"

    monkeypatch.setattr("app.core.vision.pytesseract.image_to_string", fake_ocr)
    img = _make_text_image("dummy")
    val = proc.extract_number(img)
    assert val == 1234.0


def test_extract_number_percent(monkeypatch):
    proc = ImageProcessor()

    def fake_ocr(img, lang=None, config=None):
        return "45%"

    monkeypatch.setattr("app.core.vision.pytesseract.image_to_string", fake_ocr)
    img = _make_text_image("dummy")
    val = proc.extract_number(img)
    assert val == 45.0


def test_extract_number_commas(monkeypatch):
    proc = ImageProcessor()

    def fake_ocr(img, lang=None, config=None):
        return "HP 1,234 / 5,000"

    monkeypatch.setattr("app.core.vision.pytesseract.image_to_string", fake_ocr)
    img = _make_text_image("dummy")
    val = proc.extract_number(img)
    assert val == 1234.0


def test_extract_number_none(monkeypatch):
    proc = ImageProcessor()

    def fake_ocr(img, lang=None, config=None):
        return "No digits here"

    monkeypatch.setattr("pytesseract.image_to_string", fake_ocr)
    img = _make_text_image("dummy")
    val = proc.extract_number(img)
    assert val is None


@pytest.mark.parametrize("mode", ["none", "blur", "adaptive", "unknown"])
def test_preprocess_threshold_modes(mode):
    proc = ImageProcessor(scale_factor=1.0, invert=False, threshold_mode=mode)
    img = _make_text_image("88")
    pre = proc.preprocess_for_ocr(img, psm_mode=6)
    assert len(pre.shape) == 2
    assert pre.shape[0] == img.shape[0]
    assert pre.shape[1] == img.shape[1]


def test_preprocess_invalid_input_raises():
    proc = ImageProcessor()
    with pytest.raises(ValueError):
        proc.preprocess_for_ocr(None)


def test_ensure_tesseract_path_uses_env(monkeypatch):
    env_path = r"C:\custom\tesseract.exe"
    called = {"count": 0}
    def fake_configure(*a, **k):
        called["count"] += 1
        sys.modules["app.core.vision"].pytesseract.pytesseract.tesseract_cmd = env_path
        return env_path, "env"
    monkeypatch.setattr(
        "app.core.vision.configure_tesseract_cmd",
        fake_configure,
    )
    proc = ImageProcessor()
    assert proc is not None
    assert called["count"] == 1
    assert sys.modules["app.core.vision"].pytesseract.pytesseract.tesseract_cmd == env_path


def test_template_cache_clear_roundtrip():
    proc = ImageProcessor()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
    try:
        img = np.zeros((8, 8, 3), dtype=np.uint8)
        cv2.imwrite(tmp_path, img)
        first = proc._load_template_from_disk(tmp_path)
        second = proc._load_template_from_disk(tmp_path)
        assert first is not None and second is not None
        assert proc._load_template_from_disk.cache_info().hits >= 1
        proc.clear_cache()
        assert proc._load_template_from_disk.cache_info().currsize == 0
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

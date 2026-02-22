import cv2
import numpy as np

from app.core.models import RepeatConfig, StepData
from app.core.runner import MacroRunner


def _write_png(path, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(path))


def test_compare_images_mse(tmp_path):
    img_a = np.zeros((16, 16, 3), dtype=np.uint8)
    img_b = img_a.copy()
    p_a = tmp_path / "a.png"
    p_b = tmp_path / "b.png"
    _write_png(p_a, img_a)
    _write_png(p_b, img_b)

    step = StepData(
        id="c1",
        name="Compare",
        type="compare_images",
        image_a_path=str(p_a),
        image_b_path=str(p_b),
        compare_mode="mse",
        compare_threshold=0.0,
    )
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True)
    ok, _ = runner._compare_images(step)
    assert ok is True

    img_b[:] = 255
    _write_png(p_b, img_b)
    ok, _ = runner._compare_images(step)
    assert ok is False


def test_compare_images_ssim(tmp_path):
    img_a = np.zeros((16, 16, 3), dtype=np.uint8)
    img_b = img_a.copy()
    p_a = tmp_path / "a.png"
    p_b = tmp_path / "b.png"
    _write_png(p_a, img_a)
    _write_png(p_b, img_b)

    step = StepData(
        id="c2",
        name="Compare",
        type="compare_images",
        image_a_path=str(p_a),
        image_b_path=str(p_b),
        compare_mode="ssim",
        compare_threshold=0.99,
    )
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True)
    ok, _ = runner._compare_images(step)
    assert ok is True

    img_b[:] = 255
    _write_png(p_b, img_b)
    ok, _ = runner._compare_images(step)
    assert ok is False


def test_compare_images_hash(tmp_path):
    grad = np.tile(np.linspace(0, 255, 16, dtype=np.uint8), (16, 1))
    img_a = np.dstack([grad, grad, grad])
    img_b = img_a.copy()
    p_a = tmp_path / "a.png"
    p_b = tmp_path / "b.png"
    _write_png(p_a, img_a)
    _write_png(p_b, img_b)

    step = StepData(
        id="c3",
        name="Compare",
        type="compare_images",
        image_a_path=str(p_a),
        image_b_path=str(p_b),
        compare_mode="hash",
        compare_threshold=0.0,
    )
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True)
    ok, _ = runner._compare_images(step)
    assert ok is True

    img_b = np.flip(img_a, axis=1)
    _write_png(p_b, img_b)
    ok, _ = runner._compare_images(step)
    assert ok is False

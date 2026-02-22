import numpy as np
import pytest

from app.core.models import StepData
from app.utils import matcher as matcher_mod


def test_high_quality_prefers_best_score(monkeypatch):
    def fake_apply_preprocess(img_bgr, step, overrides=None):
        tag = 0.85
        if overrides:
            if overrides.get("pre_edge"):
                tag = 0.95
            elif overrides.get("pre_clahe"):
                tag = 0.9
            elif overrides.get("force_gray"):
                tag = 0.86
        return np.array([[tag]], dtype=np.float32)

    def fake_match_template_with_color(img_like, tpl_like, step, mask=None):
        val = float(tpl_like[0, 0])
        return np.array([[val]], dtype=np.float32)

    monkeypatch.setattr(matcher_mod, "_apply_preprocess", fake_apply_preprocess)
    monkeypatch.setattr(matcher_mod, "match_template_with_color", fake_match_template_with_color)

    m = matcher_mod.Matcher()
    step = StepData(id="s1", name="img", type="image_click", match_quality="high", threshold=0.8)
    step._tpl_bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    frame = np.zeros((1, 1, 3), dtype=np.uint8)

    mr = m.find_best_optimized(frame, step)
    assert mr.ok
    assert mr.score == pytest.approx(0.95, abs=1e-6)


def test_high_quality_skips_forced_gray_when_color_enabled(monkeypatch):
    def fake_apply_preprocess(img_bgr, step, overrides=None):
        tag = 0.7
        if overrides and overrides.get("force_gray"):
            tag = 0.99
        return np.array([[tag]], dtype=np.float32)

    def fake_match_template_with_color(img_like, tpl_like, step, mask=None):
        val = float(tpl_like[0, 0])
        return np.array([[val]], dtype=np.float32)

    monkeypatch.setattr(matcher_mod, "_apply_preprocess", fake_apply_preprocess)
    monkeypatch.setattr(matcher_mod, "match_template_with_color", fake_match_template_with_color)

    m = matcher_mod.Matcher()
    step = StepData(
        id="s2",
        name="img",
        type="image_click",
        match_quality="high",
        match_color=True,
        threshold=0.6,
    )
    step._tpl_bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    frame = np.zeros((1, 1, 3), dtype=np.uint8)

    mr = m.find_best_optimized(frame, step)
    assert mr.ok
    assert mr.score == pytest.approx(0.7, abs=1e-6)


def test_high_quality_color_mode_can_enable_gray_fallback(monkeypatch):
    def fake_apply_preprocess(img_bgr, step, overrides=None):
        tag = 0.72
        if overrides:
            if overrides.get("pre_edge"):
                tag = 0.95
            elif overrides.get("pre_clahe"):
                tag = 0.9
            elif overrides.get("force_gray"):
                tag = 0.86
        return np.array([[tag]], dtype=np.float32)

    def fake_match_template_with_color(img_like, tpl_like, step, mask=None):
        val = float(tpl_like[0, 0])
        return np.array([[val]], dtype=np.float32)

    monkeypatch.setattr(matcher_mod, "_apply_preprocess", fake_apply_preprocess)
    monkeypatch.setattr(matcher_mod, "match_template_with_color", fake_match_template_with_color)

    m = matcher_mod.Matcher()
    step = StepData(
        id="s3",
        name="img",
        type="image_click",
        match_quality="high",
        match_color=True,
        hq_color_bg_robust=True,
        threshold=0.6,
    )
    step._tpl_bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    frame = np.zeros((1, 1, 3), dtype=np.uint8)

    mr = m.find_best_optimized(frame, step)
    assert mr.ok
    assert mr.score == pytest.approx(0.95, abs=1e-6)
    assert str(mr.stage).endswith("edge_fallback")


def test_high_quality_color_fallback_bypasses_color_gate(monkeypatch):
    def fake_apply_preprocess(img_bgr, step, overrides=None):
        if overrides and overrides.get("force_gray"):
            return np.array([[0.9]], dtype=np.float32)
        return np.array([[0.5]], dtype=np.float32)

    def fake_match_template_with_color(img_like, tpl_like, step, mask=None):
        val = float(tpl_like[0, 0])
        return np.array([[val]], dtype=np.float32)

    monkeypatch.setattr(matcher_mod, "_apply_preprocess", fake_apply_preprocess)
    monkeypatch.setattr(matcher_mod, "match_template_with_color", fake_match_template_with_color)

    m = matcher_mod.Matcher()
    m._color_gate_passed = lambda img_like, tpl_like, x, y, step, mask_like=None: False
    step = StepData(
        id="s4",
        name="img",
        type="image_click",
        match_quality="high",
        match_color=True,
        hq_color_bg_robust=True,
        threshold=0.6,
    )
    step._tpl_bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    frame = np.zeros((1, 1, 3), dtype=np.uint8)

    mr = m.find_best_optimized(frame, step)
    assert mr.ok
    assert mr.score == pytest.approx(0.9, abs=1e-6)


def test_match_template_with_color_uses_mask_aware_method(monkeypatch):
    calls = []

    def fake_match_template(src, tpl, method, mask=None):
        calls.append((method, mask is not None, len(getattr(src, "shape", ()))))
        return np.array([[0.9]], dtype=np.float32)

    monkeypatch.setattr(matcher_mod.cv2, "matchTemplate", fake_match_template)

    step = StepData(id="m1", name="img", type="image_click", match_color=False)
    gray_img = np.zeros((4, 4), dtype=np.uint8)
    gray_tpl = np.zeros((2, 2), dtype=np.uint8)
    mask = np.ones((2, 2), dtype=np.uint8) * 255
    matcher_mod.match_template_with_color(gray_img, gray_tpl, step, mask=mask)
    assert calls[-1][0] == matcher_mod.cv2.TM_CCORR_NORMED
    assert calls[-1][1] is True

    calls.clear()
    step.match_color = True
    color_img = np.zeros((4, 4, 3), dtype=np.uint8)
    color_tpl = np.zeros((2, 2, 3), dtype=np.uint8)
    matcher_mod.match_template_with_color(color_img, color_tpl, step, mask=mask)
    assert len(calls) == 3
    assert all(method == matcher_mod.cv2.TM_CCORR_NORMED for method, _, _ in calls)
    assert all(masked is True for _, masked, _ in calls)


def test_color_gate_uses_mask_pixels_only():
    m = matcher_mod.Matcher()
    step = StepData(
        id="m2",
        name="img",
        type="image_click",
        match_color=True,
        color_match_tolerance=1,
    )
    tpl = np.array(
        [
            [[255, 255, 255], [0, 0, 0]],
            [[0, 0, 0], [0, 0, 0]],
        ],
        dtype=np.uint8,
    )
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    frame[1:3, 1:3] = np.array(
        [
            [[255, 255, 255], [20, 20, 20]],
            [[20, 20, 20], [20, 20, 20]],
        ],
        dtype=np.uint8,
    )
    mask = np.array([[255, 0], [0, 0]], dtype=np.uint8)

    assert m._color_gate_passed(frame, tpl, 1, 1, step, mask_like=mask) is True
    assert m._color_gate_passed(frame, tpl, 1, 1, step, mask_like=None) is False


def test_auto_foreground_mask_generated_without_alpha():
    m = matcher_mod.Matcher()
    step = StepData(
        id="m3",
        name="img",
        type="image_click",
        alpha_mask_enable=False,
        auto_fg_mask_enable=True,
    )
    tpl = np.zeros((9, 9, 3), dtype=np.uint8)
    tpl[:, :, :] = 20
    tpl[3:6, 3:6, :] = 240
    step._tpl_bgr = tpl
    step._tpl_mask = None

    mask = m._get_base_mask(step)
    assert mask is not None
    assert mask.shape == (9, 9)
    assert int(mask[4, 4]) == 255
    assert int(mask[0, 0]) == 0


def test_auto_foreground_mask_is_passed_to_matching(monkeypatch):
    captured = []

    def fake_apply_preprocess(img_bgr, step, overrides=None):
        return img_bgr

    def fake_match_template_with_color(img_like, tpl_like, step, mask=None):
        captured.append(mask)
        return np.array([[0.95]], dtype=np.float32)

    monkeypatch.setattr(matcher_mod, "_apply_preprocess", fake_apply_preprocess)
    monkeypatch.setattr(matcher_mod, "match_template_with_color", fake_match_template_with_color)

    m = matcher_mod.Matcher()
    step = StepData(
        id="m4",
        name="img",
        type="image_click",
        alpha_mask_enable=False,
        auto_fg_mask_enable=True,
        threshold=0.6,
    )
    tpl = np.zeros((9, 9, 3), dtype=np.uint8)
    tpl[:, :, :] = 20
    tpl[3:6, 3:6, :] = 240
    step._tpl_bgr = tpl
    step._tpl_mask = None
    frame = np.zeros((20, 20, 3), dtype=np.uint8)

    mr = m.find_best_optimized(frame, step)
    assert mr.ok
    assert captured
    assert captured[0] is not None


def test_auto_foreground_mask_min_distance_tuning(monkeypatch):
    m = matcher_mod.Matcher()
    step = StepData(
        id="m5",
        name="img",
        type="image_click",
        alpha_mask_enable=False,
        auto_fg_mask_enable=True,
        auto_fg_mask_bg_percentile=70.0,
        auto_fg_mask_dynamic_scale=0.6,
        auto_fg_mask_min_distance=1.0,
    )
    tpl = np.zeros((9, 9, 3), dtype=np.uint8)
    tpl[:, :, :] = 20
    tpl[3:6, 3:6, :] = 25
    step._tpl_bgr = tpl
    step._tpl_mask = None

    mask_low = m._get_base_mask(step)
    assert mask_low is not None
    assert int(mask_low[4, 4]) == 255

    # Disable edge fallback to isolate distance-threshold behavior.
    monkeypatch.setattr(matcher_mod.cv2, "Canny", lambda img, t1, t2: np.zeros(img.shape[:2], dtype=np.uint8))
    step._tpl_cache = {}
    step.auto_fg_mask_min_distance = 20.0
    mask_high = m._get_base_mask(step)
    assert mask_high is None


def test_auto_foreground_mask_dynamic_scale_tuning(monkeypatch):
    m = matcher_mod.Matcher()
    step = StepData(
        id="m6",
        name="img",
        type="image_click",
        alpha_mask_enable=False,
        auto_fg_mask_enable=True,
        auto_fg_mask_bg_percentile=70.0,
        auto_fg_mask_dynamic_scale=0.2,
        auto_fg_mask_min_distance=1.0,
    )
    tpl = np.zeros((10, 10, 3), dtype=np.uint8)
    tpl[:, :, :] = 20
    tpl[2:8, 2:8, :] = 80
    step._tpl_bgr = tpl
    step._tpl_mask = None

    mask_low_scale = m._get_base_mask(step)
    assert mask_low_scale is not None
    assert np.mean(mask_low_scale > 0) > 0.2

    # Disable edge fallback to isolate dynamic-scale behavior.
    monkeypatch.setattr(matcher_mod.cv2, "Canny", lambda img, t1, t2: np.zeros(img.shape[:2], dtype=np.uint8))
    step._tpl_cache = {}
    step.auto_fg_mask_dynamic_scale = 2.0
    mask_high_scale = m._get_base_mask(step)
    assert mask_high_scale is None

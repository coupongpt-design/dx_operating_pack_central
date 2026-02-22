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

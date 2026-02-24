from pathlib import Path

import numpy as np

from app.core.smart_recorder import SmartProposal, SmartStep, SmartTransformer


def _key_event(ts: float, key_code: str, modifiers=None):
    return {
        "timestamp": ts,
        "type": "key",
        "phase": "press",
        "key_code": key_code,
        "modifiers": modifiers or [],
        "x": None,
        "y": None,
        "button": None,
        "hwnd": 1234,
    }


def _click_release(ts: float, x: int, y: int, button: str = "left"):
    return {
        "timestamp": ts,
        "type": "click",
        "phase": "release",
        "x": x,
        "y": y,
        "button": button,
        "key_code": None,
        "modifiers": [],
        "hwnd": 1234,
    }


def test_text_keystrokes_merge_into_single_type_text_step():
    tf = SmartTransformer(typed_gap=1.5)
    out = []
    base = 1000.0
    for i, ch in enumerate("Hello"):
        out.extend(tf.process_event(_key_event(base + (i * 0.05), ch)))
    out.extend(tf.finalize())

    text_steps = [s for s in out if isinstance(s, SmartStep) and s.step_type == "type_text"]
    assert len(text_steps) == 1
    assert text_steps[0].text == "Hello"


def test_text_flush_on_arrow_and_resume_for_next_printable():
    tf = SmartTransformer(typed_gap=1.5)
    out = []
    base = 2000.0
    for i, ch in enumerate("Hello"):
        out.extend(tf.process_event(_key_event(base + (i * 0.05), ch)))
    out.extend(tf.process_event(_key_event(base + 0.5, "left")))
    out.extend(tf.process_event(_key_event(base + 0.6, "!")))
    out.extend(tf.finalize())

    assert [s.step_type for s in out if isinstance(s, SmartStep)] == ["type_text", "key_press", "type_text"]
    text_steps = [s for s in out if isinstance(s, SmartStep) and s.step_type == "type_text"]
    key_steps = [s for s in out if isinstance(s, SmartStep) and s.step_type == "key_press"]
    assert [s.text for s in text_steps] == ["Hello", "!"]
    assert [s.key for s in key_steps] == ["left"]


def test_click_generates_dual_proposal_with_image_capture(tmp_path: Path):
    def _capture(_l: int, _t: int, w: int, h: int):
        return np.full((h, w, 3), 255, dtype=np.uint8)

    tf = SmartTransformer(
        typed_gap=1.5,
        click_capture_size=60,
        image_dir=tmp_path / "images",
        capture_provider=_capture,
    )
    out = tf.process_event(_click_release(3000.0, 120, 240))
    assert len(out) == 1
    proposal = out[0]
    assert isinstance(proposal, SmartProposal)
    assert proposal.click_step.type == "click_point"
    assert proposal.image_step is not None
    assert proposal.image_step.type == "image_click"
    assert proposal.image_path is not None
    assert Path(proposal.image_path).exists()

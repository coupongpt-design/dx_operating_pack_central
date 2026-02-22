import json
import cv2
import numpy as np
from app.core.models import StepData


def test_legacy_jump_fields_map_to_target_ids():
    s = StepData(
        id="s1",
        name="Jump",
        type="jump_if",
        jump_to_step_id="legacy_id",
        jump_to_index=5,
    )
    assert s.target_true_id == "legacy_id"
    assert s.target_true_index == 5


def test_to_dict_is_json_serializable_and_excludes_cache():
    s = StepData(id="x1", name="Test", type="comment", match_quality="high", top_k=3)
    d = s.to_dict()
    # should not raise JSON serialization error
    json.dumps(d)
    assert d.get("comment", "") == ""
    assert d.get("match_quality") == "high"
    assert d.get("top_k") == 3
    assert "_tpl_cache" not in d
    assert "_tpl_bgr" not in d
    assert "_tpl_mask" not in d


def test_ensure_tpl_extracts_alpha_mask():
    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    rgba[0, 0, :3] = 255
    rgba[0, 0, 3] = 255
    ok, enc = cv2.imencode(".png", rgba)
    assert ok is True

    s = StepData(id="x2", name="Mask", type="image_click", png_bytes=enc.tobytes())
    tpl = s.ensure_tpl()

    assert tpl is not None
    assert tpl.shape == (2, 2, 3)
    assert s._tpl_mask is not None
    assert int(s._tpl_mask[0, 0]) == 255
    assert int(s._tpl_mask[1, 1]) == 0


def test_ensure_tpl_loads_from_anchor_image_path(tmp_path):
    rgba = np.zeros((3, 3, 4), dtype=np.uint8)
    rgba[:, :, :3] = 120
    rgba[:, :, 3] = 255
    ok, enc = cv2.imencode(".png", rgba)
    assert ok is True

    anchor = tmp_path / "anchor.png"
    anchor.write_bytes(enc.tobytes())

    s = StepData(id="x3", name="PathTpl", type="wait_for_image", anchor_image_path=str(anchor))
    tpl = s.ensure_tpl()

    assert tpl is not None
    assert tpl.shape == (3, 3, 3)
    assert s.png_bytes is not None

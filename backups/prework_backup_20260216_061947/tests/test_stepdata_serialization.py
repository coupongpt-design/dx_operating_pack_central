import json
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

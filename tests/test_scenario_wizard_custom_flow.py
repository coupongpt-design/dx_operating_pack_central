import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_plan_custom_flow_template(tmp_path, monkeypatch):
    from app.core import scenario_wizard as sw

    user_file = tmp_path / "scenario_wizard_user_templates.json"
    monkeypatch.setattr(sw, "USER_TEMPLATE_FILE", user_file)

    custom = {
        "id": "user_custom_flow_case",
        "title": "Custom Flow",
        "summary": "custom flow test",
        "fields": [],
        "mode": "custom_flow",
        "steps_blueprint": [
            {"step_uuid": "a", "name": "A", "type": "start_loop", "loop_count": 2},
            {"step_uuid": "b", "name": "B", "type": "comment"},
            {"step_uuid": "c", "name": "C", "type": "end_loop", "start_loop_id": "a"},
        ],
    }
    ok, errors = sw.upsert_user_template(custom)
    assert ok is True
    assert errors == []

    planned = sw.plan_template("user_custom_flow_case", {})
    assert not planned["errors"]
    assert [s.type for s in planned["steps"]] == ["start_loop", "comment", "end_loop"]
    assert planned["steps"][-1].start_loop_id == planned["steps"][0].id
    assert getattr(planned["steps"][0], "source_step_id", None) == "a"
    assert getattr(planned["steps"][1], "source_step_id", None) == "b"
    assert getattr(planned["steps"][2], "source_step_id", None) == "c"


def test_plan_custom_flow_with_orphan_reference_errors(tmp_path, monkeypatch):
    from app.core import scenario_wizard as sw

    user_file = tmp_path / "scenario_wizard_user_templates.json"
    monkeypatch.setattr(sw, "USER_TEMPLATE_FILE", user_file)

    custom = {
        "id": "user_custom_flow_bad_ref",
        "title": "Bad Flow",
        "summary": "bad ref",
        "fields": [],
        "mode": "custom_flow",
        "steps_blueprint": [
            {"step_uuid": "x1", "name": "Jump", "type": "jump_if", "target_true_id": "missing"},
            {"step_uuid": "x2", "name": "Tail", "type": "comment"},
        ],
    }
    ok, errors = sw.upsert_user_template(custom)
    assert ok is True
    assert errors == []

    planned = sw.plan_template("user_custom_flow_bad_ref", {})
    assert planned["errors"]

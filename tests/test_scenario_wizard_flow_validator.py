import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_flow_validator_detects_duplicate_ids():
    from app.core.models import StepData
    from app.core.scenario_wizard_flow import validate_custom_flow_steps

    steps = [
        StepData(id="dup", name="A", type="comment"),
        StepData(id="dup", name="B", type="comment"),
    ]
    errors, _warnings = validate_custom_flow_steps(steps)
    assert errors


def test_flow_validator_detects_orphan_reference():
    from app.core.models import StepData
    from app.core.scenario_wizard_flow import validate_custom_flow_steps

    steps = [
        StepData(id="s1", name="Jump", type="jump_if", target_true_id="missing"),
        StepData(id="s2", name="B", type="comment"),
    ]
    errors, _warnings = validate_custom_flow_steps(steps)
    assert any("참조 대상이 없습니다" in row for row in errors)


def test_flow_validator_detects_loop_pairing_error():
    from app.core.models import StepData
    from app.core.scenario_wizard_flow import validate_custom_flow_steps

    steps = [
        StepData(id="l1", name="LoopStart", type="start_loop"),
        StepData(id="c1", name="Body", type="comment"),
    ]
    errors, _warnings = validate_custom_flow_steps(steps)
    assert any("대응하는 end_loop" in row for row in errors)


def test_materialize_custom_flow_steps_remaps_ids_and_refs():
    from app.core.scenario_wizard_flow import materialize_custom_flow_steps

    blueprint = [
        {"step_uuid": "a", "name": "Start", "type": "start_loop", "loop_count": 2},
        {"step_uuid": "b", "name": "Body", "type": "comment"},
        {"step_uuid": "c", "name": "End", "type": "end_loop", "start_loop_id": "a"},
    ]

    steps = materialize_custom_flow_steps(blueprint)
    assert len(steps) == 3
    assert {s.id for s in steps} != {"a", "b", "c"}
    end = steps[2]
    assert end.start_loop_id == steps[0].id


def test_atomic_write_json_replaces_file(tmp_path):
    from app.core.scenario_wizard_flow import atomic_write_json

    target = tmp_path / "flow.json"
    atomic_write_json(target, {"a": 1})
    atomic_write_json(target, {"a": 2, "b": 3})
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["a"] == 2
    assert data["b"] == 3
    leftovers = list(Path(tmp_path).glob("*.tmp"))
    assert leftovers == []


def test_validate_custom_flow_blueprint_returns_detailed_issues():
    from app.core.scenario_wizard_flow import validate_custom_flow_blueprint

    report = validate_custom_flow_blueprint(
        [
            {"step_uuid": "a", "name": "A", "type": "jump_if", "target_true_id": "missing"},
            {"step_uuid": "b", "name": "B", "type": "comment"},
        ]
    )
    assert report["errors"]
    assert any(item.code == "ORPHAN_REFERENCE" for item in report["errors"])


def test_find_references_and_delete_with_lazy_repair():
    from app.core.scenario_wizard_flow import delete_step_with_lazy_repair, find_references_in_blueprint

    steps = [
        {"step_uuid": "s1", "name": "Start", "type": "comment"},
        {"step_uuid": "s2", "name": "Jump", "type": "jump_if", "target_true_id": "s3"},
        {"step_uuid": "s3", "name": "Target", "type": "comment"},
        {"step_uuid": "s4", "name": "Tail", "type": "comment"},
    ]
    refs = find_references_in_blueprint(steps, "s3")
    assert len(refs) == 1
    assert refs[0]["step_id"] == "s2"

    updated, rewired, warnings = delete_step_with_lazy_repair(steps, "s3")
    assert len(updated) == 3
    assert rewired
    assert not warnings

    jump = next(row for row in updated if row.get("step_uuid") == "s2")
    assert jump.get("target_true_id") == "s4"


def test_delete_with_lazy_repair_sets_none_when_no_next():
    from app.core.scenario_wizard_flow import delete_step_with_lazy_repair

    steps = [
        {"step_uuid": "s1", "name": "A", "type": "jump_if", "target_true_id": "s2"},
        {"step_uuid": "s2", "name": "B", "type": "comment"},
    ]
    updated, rewired, warnings = delete_step_with_lazy_repair(steps, "s2")
    assert len(updated) == 1
    assert rewired[0]["new_target"] == ""
    assert warnings
    assert updated[0]["target_true_id"] is None

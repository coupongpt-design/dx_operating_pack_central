import copy
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _field_default(template: dict, name: str):
    for field in template.get("fields", []):
        if str(field.get("name")) == name:
            return field.get("default")
    return None


def test_user_template_clone_edit_delete_flow(tmp_path, monkeypatch):
    from app.core import scenario_wizard as sw

    user_file = tmp_path / "scenario_wizard_user_templates.json"
    monkeypatch.setattr(sw, "USER_TEMPLATE_FILE", user_file)

    created, errors = sw.create_user_template_from_base(
        "chat_repeater",
        title="사용자 채팅 반복",
        summary="개인 설정 템플릿",
        tags=["개인", "채팅"],
        field_defaults={"message_text": "hello", "repeat_count": 3, "delay_ms": 150},
    )
    assert created is not None
    assert not errors

    ok, save_errors = sw.upsert_user_template(created)
    assert ok
    assert save_errors == []

    user_id = str(created.get("id"))
    loaded = sw.get_template(user_id)
    assert loaded is not None
    assert sw.is_user_template(loaded) is True
    assert loaded.get("title") == "사용자 채팅 반복"
    assert _field_default(loaded, "message_text") == "hello"

    planned = sw.plan_template(user_id, {})
    assert not planned["errors"]
    assert planned["values"]["message_text"] == "hello"
    assert planned["values"]["repeat_count"] == 3

    edited, edit_errors = sw.create_user_template_from_base(
        user_id,
        title="사용자 채팅 반복 v2",
        field_defaults={"repeat_count": 5},
        user_template_id=user_id,
    )
    assert edited is not None
    assert not edit_errors
    ok, save_errors = sw.upsert_user_template(edited)
    assert ok
    assert not save_errors

    loaded2 = sw.get_template(user_id)
    assert loaded2 is not None
    assert loaded2.get("title") == "사용자 채팅 반복 v2"
    assert _field_default(loaded2, "repeat_count") == 5

    deleted, delete_error = sw.delete_user_template(user_id)
    assert deleted is True
    assert delete_error is None
    assert sw.get_template(user_id) is None


def test_user_template_save_rejects_builtin_id(tmp_path, monkeypatch):
    from app.core import scenario_wizard as sw

    user_file = tmp_path / "scenario_wizard_user_templates.json"
    monkeypatch.setattr(sw, "USER_TEMPLATE_FILE", user_file)

    base = sw.get_template("chat_repeater", include_user=False)
    assert base is not None
    invalid = copy.deepcopy(base)
    invalid["id"] = "chat_repeater"

    ok, errors = sw.upsert_user_template(invalid)
    assert ok is False
    assert errors

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_wizard_template_catalog_has_expected_entries():
    from app.core.scenario_wizard import list_templates

    templates = list_templates()
    ids = {t.get("id") for t in templates}
    assert "chat_repeater" in ids
    assert "data_driven_submacro_loop" in ids
    assert "ocr_threshold_guard_key" in ids


def test_wizard_plan_requires_message_text():
    from app.core.scenario_wizard import plan_template

    planned = plan_template(
        "chat_repeater",
        {
            "scenario_name": "test",
            "message_text": "",
            "submit_key": "enter",
            "repeat_count": 3,
        },
    )

    assert planned["steps"] == []
    assert planned["errors"]


def test_wizard_chat_repeater_builds_linked_loop():
    from app.core.scenario_wizard import plan_template

    planned = plan_template(
        "chat_repeater",
        {
            "scenario_name": "chat",
            "message_text": "hello",
            "submit_key": "enter",
            "repeat_count": 2,
            "delay_ms": 10,
        },
    )

    assert not planned["errors"]
    steps = planned["steps"]
    assert [s.type for s in steps] == ["start_loop", "keyboard", "key", "wait", "end_loop"]
    assert steps[0].loop_count == 2
    assert steps[-1].start_loop_id == steps[0].id


def test_wizard_data_driven_submacro_builds_load_and_loop():
    from app.core.scenario_wizard import plan_template

    planned = plan_template(
        "data_driven_submacro_loop",
        {
            "scenario_name": "data-run",
            "data_file_path": r"C:\tmp\data.csv",
            "sub_macro_path": r"C:\tmp\sub.macro",
            "row_delay_ms": 50,
        },
    )

    assert not planned["errors"]
    steps = planned["steps"]
    assert [s.type for s in steps] == ["load_data_file", "start_loop", "run_macro", "wait", "end_loop"]
    assert steps[0].data_file_path == r"C:\tmp\data.csv"
    assert steps[2].target_macro_path == r"C:\tmp\sub.macro"
    assert steps[-1].start_loop_id == steps[1].id


def test_wizard_ocr_guard_jump_targets_skip_step():
    from app.core.scenario_wizard import plan_template

    planned = plan_template(
        "ocr_threshold_guard_key",
        {
            "scenario_name": "guard",
            "variable_name": "hp",
            "ocr_roi_x": 10,
            "ocr_roi_y": 20,
            "ocr_roi_w": 30,
            "ocr_roi_h": 40,
            "safe_operator": ">",
            "threshold_value": 55,
            "guard_key": "f1",
            "guard_cooldown_ms": 0,
            "ocr_lang": "eng",
            "ocr_preprocess_mode": "otsu",
            "ocr_invert": False,
        },
    )

    assert not planned["errors"]
    steps = planned["steps"]
    assert [s.type for s in steps] == ["ocr_store", "jump_if", "key", "comment"]
    assert steps[1].target_true_id == steps[-1].id
    assert steps[1].condition_var == "hp"
    assert steps[1].condition_value == 55.0


def test_wizard_periodic_capture_warns_without_increment_token():
    from app.core.scenario_wizard import plan_template

    planned = plan_template(
        "periodic_screenshot_capture",
        {
            "scenario_name": "capture",
            "save_path_pattern": r"C:\tmp\capture.png",
            "capture_count": 3,
            "interval_ms": 1000,
            "roi_x": 0,
            "roi_y": 0,
            "roi_w": 0,
            "roi_h": 0,
        },
    )

    assert not planned["errors"]
    assert planned["warnings"]

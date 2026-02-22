import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _sample_value(field: dict, tmp_path: Path):
    ftype = str(field.get("type", "str"))
    name = str(field.get("name") or "value")

    if ftype == "choice":
        options = field.get("options") or []
        if not options:
            return field.get("default", "")
        first = options[0]
        if isinstance(first, dict):
            return first.get("value")
        return first

    if ftype == "bool":
        return True

    if ftype == "int":
        min_val = field.get("min")
        if min_val is not None:
            return int(min_val)
        return 1

    if ftype == "float":
        min_val = field.get("min")
        if min_val is not None:
            return float(min_val)
        return 1.0

    if ftype == "path":
        p = tmp_path / f"{name}.txt"
        p.write_text("x", encoding="utf-8")
        return str(p)

    if ftype == "multiline":
        return f"sample_{name}\nline2"

    return f"sample_{name}"


def test_wizard_all_templates_plan_with_valid_sample_inputs(tmp_path):
    from app.core.scenario_wizard import list_templates, plan_template

    templates = list_templates()
    assert templates

    for template in templates:
        raw_values = {}
        for field in template.get("fields", []):
            name = str(field.get("name", "")).strip()
            if not name:
                continue
            # Fill all fields with type-valid values to detect builder/field mismatch early.
            raw_values[name] = _sample_value(field, tmp_path)

        planned = plan_template(str(template.get("id")), raw_values)
        assert not planned["errors"], f"{template.get('id')}: {planned['errors']}"
        assert planned["steps"], f"{template.get('id')}: no generated steps"

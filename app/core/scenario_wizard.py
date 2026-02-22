from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from .models import StepData
from .scenario_wizard_flow import atomic_write_json, materialize_custom_flow_steps, validate_custom_flow_steps
from ..io.data_loader import inspect_data_file
from ..utils.runtime_paths import get_resource_path, get_writable_app_dir

TEMPLATE_SCHEMA_VERSION = 1
TEMPLATE_FILE = Path(get_resource_path("app/core/scenario_wizard_templates.json"))
USER_TEMPLATE_FILE = get_writable_app_dir() / "scenario_wizard_user_templates.json"
USER_TEMPLATE_ID_PREFIX = "user_"


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def _new_step(name: str, step_type: str, **kwargs: Any) -> StepData:
    step = StepData(id=_new_id(), name=name, type=step_type)
    for key, value in kwargs.items():
        setattr(step, key, value)
    return step


def _validate_catalog_data(data: Any, *, source_name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{source_name}: template catalog must be an object.")

    version = int(data.get("schema_version", 0))
    if version != TEMPLATE_SCHEMA_VERSION:
        raise ValueError(
            f"{source_name}: unsupported template schema {version} "
            f"(expected {TEMPLATE_SCHEMA_VERSION})."
        )

    templates = data.get("templates")
    if not isinstance(templates, list):
        raise ValueError(f"{source_name}: template catalog must contain a 'templates' array.")

    for idx, item in enumerate(templates):
        if not isinstance(item, dict):
            raise ValueError(f"{source_name}: template at index {idx} must be an object.")
        for required_key in ("id", "title", "summary", "fields"):
            if required_key not in item:
                raise ValueError(f"{source_name}: template '{item.get('id', idx)}' missing '{required_key}'.")
        if not isinstance(item.get("fields"), list):
            raise ValueError(f"{source_name}: template '{item.get('id', idx)}' has non-list 'fields'.")

    return data


def _load_catalog_from_path(path: Path, *, source_name: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return _validate_catalog_data(data, source_name=source_name)


def load_template_catalog(path: str | Path | None = None) -> dict[str, Any]:
    template_path = Path(path) if path is not None else TEMPLATE_FILE
    return _load_catalog_from_path(template_path, source_name="builtin")


def load_user_template_catalog(path: str | Path | None = None) -> dict[str, Any]:
    template_path = Path(path) if path is not None else USER_TEMPLATE_FILE
    if not template_path.exists():
        return {"schema_version": TEMPLATE_SCHEMA_VERSION, "templates": []}
    return _load_catalog_from_path(template_path, source_name="user")


def _template_with_source(template: dict[str, Any], source: str) -> dict[str, Any]:
    item = copy.deepcopy(template)
    item["template_source"] = source
    return item


def list_user_templates() -> list[dict[str, Any]]:
    templates = load_user_template_catalog().get("templates", [])
    return copy.deepcopy(templates)


def list_templates(include_user: bool = True) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in load_template_catalog().get("templates", []):
        tid = str(item.get("id") or "").strip()
        if not tid or tid in seen_ids:
            continue
        merged.append(_template_with_source(item, "builtin"))
        seen_ids.add(tid)

    if include_user:
        for item in load_user_template_catalog().get("templates", []):
            tid = str(item.get("id") or "").strip()
            if not tid or tid in seen_ids:
                continue
            merged.append(_template_with_source(item, "user"))
            seen_ids.add(tid)

    return merged


def get_template(template_id: str, include_user: bool = True) -> dict[str, Any] | None:
    for item in list_templates(include_user=include_user):
        if str(item.get("id")) == str(template_id):
            return item
    return None


def _coerce_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        norm = raw.strip().lower()
        if norm in {"1", "true", "yes", "y", "on"}:
            return True
        if norm in {"0", "false", "no", "n", "off"}:
            return False
    return bool(raw)


def _coerce_value(field: dict[str, Any], raw: Any) -> Any:
    ftype = str(field.get("type", "str"))
    if raw is None or raw == "":
        if "default" in field:
            raw = field.get("default")
        else:
            raw = None

    if ftype in {"str", "path"}:
        if raw is None:
            return ""
        return str(raw).strip()
    if ftype == "multiline":
        if raw is None:
            return ""
        return str(raw)
    if ftype == "int":
        if raw is None:
            return None
        return int(raw)
    if ftype == "float":
        if raw is None:
            return None
        return float(raw)
    if ftype == "bool":
        return _coerce_bool(raw)
    if ftype == "choice":
        options = field.get("options") or []
        values = []
        for option in options:
            if isinstance(option, dict):
                values.append(option.get("value"))
            else:
                values.append(option)
        if raw in values:
            return raw
        if "default" in field and field.get("default") in values:
            return field.get("default")
        return values[0] if values else raw
    return raw


def _normalize_tags(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        values = [x.strip() for x in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        values = [str(x).strip() for x in raw]
    else:
        values = [str(raw).strip()]

    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not item or item in seen:
            continue
        result.append(item)
        seen.add(item)
    return result


def _builtin_template_ids() -> set[str]:
    return {str(t.get("id") or "").strip() for t in load_template_catalog().get("templates", [])}


def _sanitize_template_for_catalog(template: dict[str, Any]) -> dict[str, Any]:
    item = copy.deepcopy(template)
    item.pop("template_source", None)
    return item


def _write_user_template_catalog(templates: list[dict[str, Any]]) -> None:
    clean_templates = [_sanitize_template_for_catalog(t) for t in templates]
    payload = {
        "schema_version": TEMPLATE_SCHEMA_VERSION,
        "templates": clean_templates,
    }
    _validate_catalog_data(payload, source_name="user-save")
    atomic_write_json(USER_TEMPLATE_FILE, payload)


def is_user_template(template: dict[str, Any] | None) -> bool:
    if not isinstance(template, dict):
        return False
    source = str(template.get("template_source") or "").strip().lower()
    tid = str(template.get("id") or "").strip()
    return source == "user" or tid.startswith(USER_TEMPLATE_ID_PREFIX)


def _new_user_template_id(base_template_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(base_template_id or "template"))
    return f"{USER_TEMPLATE_ID_PREFIX}{safe}_{_new_id()}"


def create_user_template_from_base(
    base_template_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    tags: Any = None,
    field_defaults: dict[str, Any] | None = None,
    user_template_id: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    base = get_template(base_template_id, include_user=True)
    if base is None:
        return None, [f"기준 템플릿을 찾을 수 없습니다: {base_template_id}"]

    source = str(base.get("template_source") or "builtin")
    base_id = str(base.get("id") or "").strip()

    if user_template_id is None:
        user_template_id = _new_user_template_id(base_id)
    user_template_id = str(user_template_id or "").strip()
    if not user_template_id:
        errors.append("사용자 템플릿 ID가 비어 있습니다.")
    if not user_template_id.startswith(USER_TEMPLATE_ID_PREFIX):
        errors.append(f"사용자 템플릿 ID는 '{USER_TEMPLATE_ID_PREFIX}'로 시작해야 합니다.")
    if user_template_id in _builtin_template_ids():
        errors.append("기본 템플릿 ID와 중복될 수 없습니다.")
    if source == "builtin" and user_template_id == base_id:
        errors.append("기본 템플릿은 직접 수정할 수 없습니다. 복제 후 저장하세요.")

    template_title = str(title if title is not None else base.get("title") or "").strip()
    if not template_title:
        errors.append("템플릿 제목은 비워둘 수 없습니다.")
    template_summary = str(summary if summary is not None else base.get("summary") or "").strip()
    template_tags = _normalize_tags(tags if tags is not None else base.get("tags"))
    default_overrides = dict(field_defaults or {})

    cloned = _sanitize_template_for_catalog(base)
    builder_key = str(base.get("builder") or base_id or "").strip()
    cloned["id"] = user_template_id
    cloned["title"] = template_title
    cloned["summary"] = template_summary
    cloned["tags"] = template_tags
    cloned["recommended"] = False
    if builder_key:
        cloned["builder"] = builder_key

    for field in cloned.get("fields", []):
        field_name = str(field.get("name") or "").strip()
        if not field_name:
            continue
        if field_name in default_overrides:
            try:
                field["default"] = _coerce_value(field, default_overrides[field_name])
            except Exception:
                errors.append(f"기본값 변환 실패: {field_name}")

    if errors:
        return None, errors
    return cloned, []


def upsert_user_template(template: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(template, dict):
        return False, ["저장할 템플릿 형식이 올바르지 않습니다."]

    payload = _sanitize_template_for_catalog(template)
    tid = str(payload.get("id") or "").strip()
    if not tid:
        errors.append("템플릿 ID가 비어 있습니다.")
    if not tid.startswith(USER_TEMPLATE_ID_PREFIX):
        errors.append(f"사용자 템플릿 ID는 '{USER_TEMPLATE_ID_PREFIX}'로 시작해야 합니다.")
    if tid in _builtin_template_ids():
        errors.append("기본 템플릿 ID와 중복될 수 없습니다.")

    try:
        _validate_catalog_data(
            {"schema_version": TEMPLATE_SCHEMA_VERSION, "templates": [payload]},
            source_name="user-save",
        )
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        return False, errors

    users = list_user_templates()
    replaced = False
    for idx, item in enumerate(users):
        if str(item.get("id") or "").strip() == tid:
            users[idx] = payload
            replaced = True
            break
    if not replaced:
        users.append(payload)

    _write_user_template_catalog(users)
    return True, []


def delete_user_template(template_id: str) -> tuple[bool, str | None]:
    tid = str(template_id or "").strip()
    if not tid.startswith(USER_TEMPLATE_ID_PREFIX):
        return False, "사용자 템플릿만 삭제할 수 있습니다."

    users = list_user_templates()
    filtered = [t for t in users if str(t.get("id") or "").strip() != tid]
    if len(filtered) == len(users):
        return False, "삭제할 사용자 템플릿을 찾을 수 없습니다."

    _write_user_template_catalog(filtered)
    return True, None


def validate_template_inputs(
    template: dict[str, Any],
    raw_values: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    raw_values = raw_values or {}
    values: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []

    for field in template.get("fields", []):
        name = str(field.get("name", "")).strip()
        if not name:
            continue
        try:
            value = _coerce_value(field, raw_values.get(name))
        except Exception:
            value = None
            errors.append(f"{field.get('label', name)} 값을 해석할 수 없습니다.")
            values[name] = value
            continue

        values[name] = value
        ftype = str(field.get("type", "str"))
        label = str(field.get("label") or name)
        required = bool(field.get("required", False))

        if required:
            if ftype in {"str", "path", "multiline", "choice"} and str(value or "").strip() == "":
                errors.append(f"{label}: 필수 값입니다.")
            elif ftype in {"int", "float"} and value is None:
                errors.append(f"{label}: 숫자 값이 필요합니다.")

        if value is None:
            continue

        if ftype in {"int", "float"}:
            min_val = field.get("min")
            max_val = field.get("max")
            if min_val is not None and value < min_val:
                errors.append(f"{label}: 최소값은 {min_val} 입니다.")
            if max_val is not None and value > max_val:
                errors.append(f"{label}: 최대값은 {max_val} 입니다.")

        if ftype == "path":
            text = str(value).strip()
            if text and field.get("must_exist"):
                try:
                    if not Path(text).expanduser().exists():
                        warnings.append(f"{label}: 경로가 현재 존재하지 않습니다. ({text})")
                except Exception:
                    warnings.append(f"{label}: 경로 점검 중 오류가 발생했습니다. ({text})")

    tid = str(template.get("id", ""))
    ocr_required_templates = {
        "ocr_threshold_guard_key",
        "ocr_store_only",
        "ocr_jump_guard_key",
    }
    if tid in ocr_required_templates:
        if int(values.get("ocr_roi_w") or 0) <= 0 or int(values.get("ocr_roi_h") or 0) <= 0:
            errors.append("OCR ROI 크기(W/H)는 1 이상이어야 합니다.")
    for repeat_key in ("repeat_count", "retry_count", "cycle_count", "loop_count"):
        if repeat_key in values:
            try:
                repeat_value = int(values.get(repeat_key) or 0)
            except Exception:
                repeat_value = -1
            if repeat_value == 0:
                warnings.append("반복 횟수 0은 무한 반복입니다. 강제 종료 키를 반드시 준비하세요.")
                break
    if tid == "periodic_screenshot_capture":
        save_path = str(values.get("save_path_pattern") or "")
        if save_path and "{seq" not in save_path and "{counter" not in save_path:
            warnings.append("파일명 패턴에 증가 토큰이 없어 캡처 파일이 덮어쓰기 될 수 있습니다.")

    return values, errors, warnings


def _build_chat_repeater(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Chat Repeater").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 0),
    )
    text_step = _new_step(
        f"{prefix} - Type Text",
        "keyboard",
        keyboard_mode="text",
        key_string=str(v.get("message_text") or ""),
    )
    submit_step = _new_step(
        f"{prefix} - Submit",
        "key",
        key_string=str(v.get("submit_key") or "enter"),
    )
    steps = [loop_start, text_step, submit_step]
    delay_ms = int(v.get("delay_ms") or 0)
    if delay_ms > 0:
        steps.append(
            _new_step(
                f"{prefix} - Delay",
                "wait",
                wait_ms=delay_ms,
            )
        )
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_data_driven_submacro_loop(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Data Loop").strip()
    load_step = _new_step(
        f"{prefix} - Load Data",
        "load_data_file",
        data_file_path=str(v.get("data_file_path") or ""),
    )
    loop_start = _new_step(
        f"{prefix} - Row Loop Start",
        "start_loop",
        loop_count=0,
    )
    run_step = _new_step(
        f"{prefix} - Run Sub Macro",
        "run_macro",
        target_macro_path=str(v.get("sub_macro_path") or ""),
    )
    steps = [load_step, loop_start, run_step]
    row_delay_ms = int(v.get("row_delay_ms") or 0)
    if row_delay_ms > 0:
        steps.append(_new_step(f"{prefix} - Row Delay", "wait", wait_ms=row_delay_ms))
    steps.append(
        _new_step(
            f"{prefix} - Row Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_ocr_threshold_guard_key(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "OCR Guard").strip()
    variable_name = str(v.get("variable_name") or "value")
    skip_step = _new_step(
        f"{prefix} - Skip Guard",
        "comment",
        comment="condition true path",
    )
    store_step = _new_step(
        f"{prefix} - OCR Store",
        "ocr_store",
        ocr_store_var=variable_name,
        ocr_roi_x=int(v.get("ocr_roi_x") or 0),
        ocr_roi_y=int(v.get("ocr_roi_y") or 0),
        ocr_roi_w=int(v.get("ocr_roi_w") or 0),
        ocr_roi_h=int(v.get("ocr_roi_h") or 0),
        ocr_lang=str(v.get("ocr_lang") or "eng"),
        ocr_preprocess_mode=str(v.get("ocr_preprocess_mode") or "otsu"),
        ocr_invert=bool(v.get("ocr_invert")),
    )
    jump_step = _new_step(
        f"{prefix} - Jump If Safe",
        "jump_if",
        condition_var=variable_name,
        condition_operator=str(v.get("safe_operator") or ">"),
        condition_value=float(v.get("threshold_value") or 0.0),
        target_true_id=skip_step.id,
    )
    guard_step = _new_step(
        f"{prefix} - Guard Key",
        "key",
        key_string=str(v.get("guard_key") or "f1"),
    )
    steps = [store_step, jump_step, guard_step]
    cooldown_ms = int(v.get("guard_cooldown_ms") or 0)
    if cooldown_ms > 0:
        steps.append(_new_step(f"{prefix} - Guard Cooldown", "wait", wait_ms=cooldown_ms))
    steps.append(skip_step)
    return steps


def _build_periodic_screenshot_capture(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Capture Loop").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("capture_count") or 1),
    )
    shot_step = _new_step(
        f"{prefix} - Screenshot",
        "screenshot_roi",
        screenshot_save_path=str(v.get("save_path_pattern") or ""),
        screenshot_roi_x=int(v.get("roi_x") or 0),
        screenshot_roi_y=int(v.get("roi_y") or 0),
        screenshot_roi_w=int(v.get("roi_w") or 0),
        screenshot_roi_h=int(v.get("roi_h") or 0),
    )
    steps = [loop_start, shot_step]
    interval_ms = int(v.get("interval_ms") or 0)
    if interval_ms > 0:
        steps.append(_new_step(f"{prefix} - Interval", "wait", wait_ms=interval_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_submacro_retry_loop(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Retry Loop").strip()
    loop_start = _new_step(
        f"{prefix} - Retry Start",
        "start_loop",
        loop_count=int(v.get("retry_count") or 0),
    )
    run_step = _new_step(
        f"{prefix} - Run Sub Macro",
        "run_macro",
        target_macro_path=str(v.get("sub_macro_path") or ""),
    )
    steps = [loop_start, run_step]
    interval_ms = int(v.get("retry_interval_ms") or 0)
    if interval_ms > 0:
        steps.append(_new_step(f"{prefix} - Retry Delay", "wait", wait_ms=interval_ms))
    steps.append(
        _new_step(
            f"{prefix} - Retry End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_keyboard_combo_sequence(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Keyboard Sequence").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 1),
    )
    before_text = _new_step(
        f"{prefix} - Type Before",
        "keyboard",
        keyboard_mode="text",
        key_string=str(v.get("before_text") or ""),
    )
    hotkey_step = _new_step(
        f"{prefix} - Hotkey",
        "key",
        key_string=str(v.get("hotkey") or ""),
    )
    steps = [loop_start, before_text, hotkey_step]
    after_text = str(v.get("after_text") or "")
    if after_text:
        steps.append(
            _new_step(
                f"{prefix} - Type After",
                "keyboard",
                keyboard_mode="text",
                key_string=after_text,
            )
        )
    cycle_wait_ms = int(v.get("cycle_wait_ms") or 0)
    if cycle_wait_ms > 0:
        steps.append(_new_step(f"{prefix} - Cycle Delay", "wait", wait_ms=cycle_wait_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_click_repeat(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Click Repeat").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 1),
    )
    click_step = _new_step(
        f"{prefix} - Click",
        "click_point",
        click_x=int(v.get("click_x") or 0),
        click_y=int(v.get("click_y") or 0),
        click_btn=str(v.get("click_btn") or "left"),
        click_double=bool(v.get("double_click")),
    )
    steps = [loop_start, click_step]
    interval_ms = int(v.get("interval_ms") or 0)
    if interval_ms > 0:
        steps.append(_new_step(f"{prefix} - Interval", "wait", wait_ms=interval_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_click_two_points_loop(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Two Point Click").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 1),
    )
    click_a = _new_step(
        f"{prefix} - Click A",
        "click_point",
        click_x=int(v.get("point1_x") or 0),
        click_y=int(v.get("point1_y") or 0),
        click_btn="left",
        click_double=False,
    )
    click_b = _new_step(
        f"{prefix} - Click B",
        "click_point",
        click_x=int(v.get("point2_x") or 0),
        click_y=int(v.get("point2_y") or 0),
        click_btn="left",
        click_double=False,
    )
    steps = [loop_start, click_a, click_b]
    interval_ms = int(v.get("interval_ms") or 0)
    if interval_ms > 0:
        steps.append(_new_step(f"{prefix} - Interval", "wait", wait_ms=interval_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_click_then_hotkey(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Click Hotkey").strip()
    click_step = _new_step(
        f"{prefix} - Click",
        "click_point",
        click_x=int(v.get("click_x") or 0),
        click_y=int(v.get("click_y") or 0),
        click_btn=str(v.get("click_btn") or "left"),
        click_double=bool(v.get("double_click")),
    )
    steps = [click_step]
    wait_ms = int(v.get("wait_ms") or 0)
    if wait_ms > 0:
        steps.append(_new_step(f"{prefix} - Wait", "wait", wait_ms=wait_ms))
    steps.append(
        _new_step(
            f"{prefix} - Hotkey",
            "key",
            key_string=str(v.get("hotkey") or "enter"),
        )
    )
    return steps


def _build_hotkey_repeat(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Hotkey Repeat").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 1),
    )
    key_step = _new_step(
        f"{prefix} - Hotkey",
        "key",
        key_string=str(v.get("hotkey") or ""),
    )
    steps = [loop_start, key_step]
    interval_ms = int(v.get("interval_ms") or 0)
    if interval_ms > 0:
        steps.append(_new_step(f"{prefix} - Interval", "wait", wait_ms=interval_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_key_hold_repeat(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Key Hold Repeat").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 1),
    )
    hold_step = _new_step(
        f"{prefix} - Hold Key",
        "key_hold",
        key_string=str(v.get("hotkey") or ""),
        hold_ms=int(v.get("hold_ms") or 300),
    )
    steps = [loop_start, hold_step]
    interval_ms = int(v.get("interval_ms") or 0)
    if interval_ms > 0:
        steps.append(_new_step(f"{prefix} - Interval", "wait", wait_ms=interval_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_text_then_hotkey(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Text Hotkey").strip()
    text_step = _new_step(
        f"{prefix} - Type Text",
        "keyboard",
        keyboard_mode="text",
        key_string=str(v.get("text") or ""),
    )
    steps = [text_step]
    wait_ms = int(v.get("wait_ms") or 0)
    if wait_ms > 0:
        steps.append(_new_step(f"{prefix} - Wait", "wait", wait_ms=wait_ms))
    steps.append(
        _new_step(
            f"{prefix} - Hotkey",
            "key",
            key_string=str(v.get("hotkey") or "enter"),
        )
    )
    return steps


def _build_text_submit_once(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Text Submit").strip()
    text_step = _new_step(
        f"{prefix} - Type Text",
        "keyboard",
        keyboard_mode="text",
        key_string=str(v.get("text") or ""),
    )
    submit_step = _new_step(
        f"{prefix} - Submit",
        "key",
        key_string=str(v.get("submit_key") or "enter"),
    )
    steps = [text_step, submit_step]
    after_wait_ms = int(v.get("after_wait_ms") or 0)
    if after_wait_ms > 0:
        steps.append(_new_step(f"{prefix} - Wait", "wait", wait_ms=after_wait_ms))
    return steps


def _build_run_macro_once(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Run Macro Once").strip()
    return [
        _new_step(
            f"{prefix} - Run Macro",
            "run_macro",
            target_macro_path=str(v.get("sub_macro_path") or ""),
        )
    ]


def _build_run_two_macros(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Run Macros").strip()
    steps = [
        _new_step(
            f"{prefix} - Run A",
            "run_macro",
            target_macro_path=str(v.get("macro_path_a") or ""),
        )
    ]
    wait_between_ms = int(v.get("wait_between_ms") or 0)
    if wait_between_ms > 0:
        steps.append(_new_step(f"{prefix} - Wait", "wait", wait_ms=wait_between_ms))
    steps.append(
        _new_step(
            f"{prefix} - Run B",
            "run_macro",
            target_macro_path=str(v.get("macro_path_b") or ""),
        )
    )
    return steps


def _build_csv_text_submit_loop(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "CSV Text Submit").strip()
    load_step = _new_step(
        f"{prefix} - Load Data",
        "load_data_file",
        data_file_path=str(v.get("data_file_path") or ""),
    )
    loop_start = _new_step(
        f"{prefix} - Row Loop Start",
        "start_loop",
        loop_count=0,
    )
    type_step = _new_step(
        f"{prefix} - Type Row Text",
        "keyboard",
        keyboard_mode="text",
        key_string=str(v.get("text_pattern") or "{data}"),
    )
    submit_step = _new_step(
        f"{prefix} - Submit",
        "key",
        key_string=str(v.get("submit_key") or "enter"),
    )
    steps = [load_step, loop_start, type_step, submit_step]
    row_delay_ms = int(v.get("row_delay_ms") or 0)
    if row_delay_ms > 0:
        steps.append(_new_step(f"{prefix} - Row Delay", "wait", wait_ms=row_delay_ms))
    steps.append(
        _new_step(
            f"{prefix} - Row Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_ocr_store_only(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "OCR Store").strip()
    return [
        _new_step(
            f"{prefix} - OCR Store",
            "ocr_store",
            ocr_store_var=str(v.get("variable_name") or "value"),
            ocr_roi_x=int(v.get("ocr_roi_x") or 0),
            ocr_roi_y=int(v.get("ocr_roi_y") or 0),
            ocr_roi_w=int(v.get("ocr_roi_w") or 0),
            ocr_roi_h=int(v.get("ocr_roi_h") or 0),
            ocr_lang=str(v.get("ocr_lang") or "eng"),
            ocr_preprocess_mode=str(v.get("ocr_preprocess_mode") or "otsu"),
            ocr_invert=bool(v.get("ocr_invert")),
        )
    ]


def _build_ocr_jump_guard_key(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "OCR Jump Guard").strip()
    skip_step = _new_step(
        f"{prefix} - Skip Guard",
        "comment",
        comment="condition true path",
    )
    ocr_jump_step = _new_step(
        f"{prefix} - OCR Jump",
        "ocr_jump_if",
        ocr_roi_x=int(v.get("ocr_roi_x") or 0),
        ocr_roi_y=int(v.get("ocr_roi_y") or 0),
        ocr_roi_w=int(v.get("ocr_roi_w") or 0),
        ocr_roi_h=int(v.get("ocr_roi_h") or 0),
        ocr_lang=str(v.get("ocr_lang") or "eng"),
        ocr_preprocess_mode=str(v.get("ocr_preprocess_mode") or "otsu"),
        ocr_invert=bool(v.get("ocr_invert")),
        condition_operator=str(v.get("condition_operator") or "<="),
        condition_value=float(v.get("condition_value") or 0.0),
        target_true_id=skip_step.id,
    )
    guard_step = _new_step(
        f"{prefix} - Guard Key",
        "key",
        key_string=str(v.get("guard_key") or "f1"),
    )
    steps = [ocr_jump_step, guard_step]
    guard_cooldown_ms = int(v.get("guard_cooldown_ms") or 0)
    if guard_cooldown_ms > 0:
        steps.append(_new_step(f"{prefix} - Guard Cooldown", "wait", wait_ms=guard_cooldown_ms))
    steps.append(skip_step)
    return steps


def _build_pixel_guard_key(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Pixel Guard").strip()
    skip_step = _new_step(
        f"{prefix} - Skip Guard",
        "comment",
        comment="pixel success path",
    )
    guard_step = _new_step(
        f"{prefix} - Guard Key",
        "key",
        key_string=str(v.get("guard_key") or "f1"),
    )
    pixel_step = _new_step(
        f"{prefix} - Pixel Check",
        "pixel_check",
        pixel_x=int(v.get("pixel_x") or 0),
        pixel_y=int(v.get("pixel_y") or 0),
        pixel_color_hex=str(v.get("pixel_color_hex") or "#FFFFFF"),
        pixel_color_tolerance=int(v.get("pixel_color_tolerance") or 10),
        pixel_success_goto_id=skip_step.id,
        branch_on_fail_goto_id=guard_step.id,
    )
    steps = [pixel_step, guard_step]
    guard_cooldown_ms = int(v.get("guard_cooldown_ms") or 0)
    if guard_cooldown_ms > 0:
        steps.append(_new_step(f"{prefix} - Guard Cooldown", "wait", wait_ms=guard_cooldown_ms))
    steps.append(skip_step)
    return steps


def _build_screenshot_once(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Screenshot").strip()
    return [
        _new_step(
            f"{prefix} - Screenshot",
            "screenshot_roi",
            screenshot_save_path=str(v.get("save_path") or ""),
            screenshot_roi_x=int(v.get("roi_x") or 0),
            screenshot_roi_y=int(v.get("roi_y") or 0),
            screenshot_roi_w=int(v.get("roi_w") or 0),
            screenshot_roi_h=int(v.get("roi_h") or 0),
        )
    ]


def _build_scroll_repeat(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Scroll Repeat").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 1),
    )
    scroll_step = _new_step(
        f"{prefix} - Scroll",
        "scroll",
        scroll_dx=int(v.get("scroll_dx") or 0),
        scroll_dy=int(v.get("scroll_dy") or -300),
        scroll_times=int(v.get("scroll_times") or 1),
        scroll_interval_ms=int(v.get("scroll_step_interval_ms") or 0),
    )
    steps = [loop_start, scroll_step]
    cycle_wait_ms = int(v.get("cycle_wait_ms") or 0)
    if cycle_wait_ms > 0:
        steps.append(_new_step(f"{prefix} - Cycle Wait", "wait", wait_ms=cycle_wait_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_drag_once(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Drag Once").strip()
    return [
        _new_step(
            f"{prefix} - Drag",
            "drag",
            drag_from_x=int(v.get("drag_from_x") or 0),
            drag_from_y=int(v.get("drag_from_y") or 0),
            drag_to_x=int(v.get("drag_to_x") or 0),
            drag_to_y=int(v.get("drag_to_y") or 0),
            drag_duration_ms=int(v.get("drag_duration_ms") or 200),
        )
    ]


def _build_wait_hotkey_repeat(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Wait Hotkey Repeat").strip()
    loop_start = _new_step(
        f"{prefix} - Loop Start",
        "start_loop",
        loop_count=int(v.get("repeat_count") or 1),
    )
    wait_step = _new_step(
        f"{prefix} - Wait Before",
        "wait",
        wait_ms=int(v.get("wait_ms") or 300),
    )
    key_step = _new_step(
        f"{prefix} - Hotkey",
        "key",
        key_string=str(v.get("hotkey") or ""),
    )
    steps = [loop_start, wait_step, key_step]
    post_wait_ms = int(v.get("post_wait_ms") or 0)
    if post_wait_ms > 0:
        steps.append(_new_step(f"{prefix} - Wait After", "wait", wait_ms=post_wait_ms))
    steps.append(
        _new_step(
            f"{prefix} - Loop End",
            "end_loop",
            start_loop_id=loop_start.id,
        )
    )
    return steps


def _build_click_then_text(template: dict[str, Any], v: dict[str, Any]) -> list[StepData]:
    prefix = str(v.get("scenario_name") or template.get("title") or "Click Then Text").strip()
    click_step = _new_step(
        f"{prefix} - Click",
        "click_point",
        click_x=int(v.get("click_x") or 0),
        click_y=int(v.get("click_y") or 0),
        click_btn=str(v.get("click_btn") or "left"),
        click_double=bool(v.get("double_click")),
    )
    steps = [click_step]
    wait_ms = int(v.get("wait_ms") or 0)
    if wait_ms > 0:
        steps.append(_new_step(f"{prefix} - Wait", "wait", wait_ms=wait_ms))
    steps.append(
        _new_step(
            f"{prefix} - Type Text",
            "keyboard",
            keyboard_mode="text",
            key_string=str(v.get("text") or ""),
        )
    )
    return steps


TEMPLATE_BUILDERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], list[StepData]]] = {
    "chat_repeater": _build_chat_repeater,
    "data_driven_submacro_loop": _build_data_driven_submacro_loop,
    "ocr_threshold_guard_key": _build_ocr_threshold_guard_key,
    "periodic_screenshot_capture": _build_periodic_screenshot_capture,
    "submacro_retry_loop": _build_submacro_retry_loop,
    "keyboard_combo_sequence": _build_keyboard_combo_sequence,
    "click_repeat": _build_click_repeat,
    "click_two_points_loop": _build_click_two_points_loop,
    "click_then_hotkey": _build_click_then_hotkey,
    "hotkey_repeat": _build_hotkey_repeat,
    "key_hold_repeat": _build_key_hold_repeat,
    "text_then_hotkey": _build_text_then_hotkey,
    "text_submit_once": _build_text_submit_once,
    "run_macro_once": _build_run_macro_once,
    "run_two_macros": _build_run_two_macros,
    "csv_text_submit_loop": _build_csv_text_submit_loop,
    "ocr_store_only": _build_ocr_store_only,
    "ocr_jump_guard_key": _build_ocr_jump_guard_key,
    "pixel_guard_key": _build_pixel_guard_key,
    "screenshot_once": _build_screenshot_once,
    "scroll_repeat": _build_scroll_repeat,
    "drag_once": _build_drag_once,
    "wait_hotkey_repeat": _build_wait_hotkey_repeat,
    "click_then_text": _build_click_then_text,
}


def validate_generated_steps(steps: list[StepData]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not steps:
        errors.append("생성된 스텝이 없습니다.")
        return errors, warnings

    ids = [str(getattr(step, "id", "") or "") for step in steps]
    id_set = set(ids)
    if "" in id_set or len(id_set) != len(ids):
        errors.append("스텝 ID가 비어있거나 중복되었습니다.")

    loop_start_ids = {step.id for step in steps if step.type == "start_loop"}

    for step in steps:
        if step.type == "end_loop" and step.start_loop_id not in loop_start_ids:
            errors.append(f"end_loop '{step.name}' 의 start_loop_id가 유효하지 않습니다.")
        if step.type in {"jump_if", "ocr_jump_if"}:
            target_true_id = getattr(step, "target_true_id", None)
            if target_true_id and target_true_id not in id_set:
                errors.append(f"점프 타겟이 존재하지 않습니다. ({step.name})")
        if step.type == "run_macro" and not str(getattr(step, "target_macro_path", "") or "").strip():
            errors.append(f"run_macro 경로가 비어 있습니다. ({step.name})")
        if step.type == "load_data_file" and not str(getattr(step, "data_file_path", "") or "").strip():
            errors.append(f"load_data_file 경로가 비어 있습니다. ({step.name})")
        if step.type == "screenshot_roi":
            save_path = str(getattr(step, "screenshot_save_path", "") or "")
            if save_path and not save_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                warnings.append(
                    f"screenshot 저장 확장자를 확인하세요. ({step.name}: {save_path})"
                )

    data_errors, data_warnings = _validate_data_bindings(steps)
    errors.extend(data_errors)
    warnings.extend(data_warnings)
    return errors, warnings


def _extract_data_tokens_from_steps(steps: list[StepData]) -> set[str]:
    tokens: set[str] = set()
    pattern = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
    builtins = {"data", "seq"}
    fields_to_scan = ("key_string", "ocr_expected_text")

    for step in steps:
        for field_name in fields_to_scan:
            raw = getattr(step, field_name, None)
            if not isinstance(raw, str) or "{" not in raw:
                continue
            for token in pattern.findall(raw):
                if token in builtins:
                    continue
                tokens.add(token)
    return tokens


def _validate_data_bindings(steps: list[StepData]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    data_paths = [
        str(getattr(step, "data_file_path", "") or "").strip()
        for step in steps
        if step.type == "load_data_file"
    ]
    data_paths = [path for path in data_paths if path]
    if not data_paths:
        return errors, warnings

    path = data_paths[0]
    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        warnings.append(f"데이터 파일 경로가 존재하지 않아 컬럼 검증을 건너뜁니다. ({path})")
        return errors, warnings

    ok, info, err = inspect_data_file(str(path_obj))
    if not ok:
        warnings.append(f"데이터 파일 파싱 실패로 컬럼 검증을 건너뜁니다. ({err})")
        return errors, warnings

    columns = [str(col) for col in info.get("columns", []) if str(col).strip()]
    if not columns:
        warnings.append("데이터 파일 헤더(컬럼)가 비어 있어 컬럼 매핑 검증을 건너뜁니다.")
        return errors, warnings

    required = _extract_data_tokens_from_steps(steps)
    missing = sorted(token for token in required if token not in set(columns))
    if missing:
        errors.append(
            "데이터 컬럼 누락: "
            + ", ".join(missing)
            + f" (파일 컬럼: {', '.join(columns)})"
        )

    row_count = int(info.get("row_count") or 0)
    if row_count <= 0:
        warnings.append("데이터 파일에 실행 가능한 행이 없습니다.")

    empty_rows = int(info.get("empty_row_count") or 0)
    if empty_rows > 0:
        warnings.append(f"데이터 파일의 빈 행 {empty_rows}개는 실행 시 자동으로 건너뜁니다.")

    return errors, warnings


def plan_template(template_id: str, raw_values: dict[str, Any] | None) -> dict[str, Any]:
    template = get_template(template_id)
    if template is None:
        return {
            "template": None,
            "values": {},
            "steps": [],
            "errors": [f"템플릿을 찾을 수 없습니다: {template_id}"],
            "warnings": [],
        }

    values, errors, warnings = validate_template_inputs(template, raw_values)
    steps: list[StepData] = []
    template_mode = str(template.get("mode") or "builder").strip().lower()
    if not errors:
        if template_mode == "custom_flow":
            try:
                steps = materialize_custom_flow_steps(template.get("steps_blueprint") or [])
            except Exception as exc:
                errors.append(f"custom_flow 스텝 생성 실패: {exc}")
                steps = []
        else:
            builder_key = str(template.get("builder") or template_id)
            builder = TEMPLATE_BUILDERS.get(builder_key)
            if builder is None:
                errors.append(f"템플릿 빌더가 없습니다: {builder_key}")
            else:
                try:
                    steps = builder(template, values)
                except Exception as exc:
                    errors.append(f"템플릿 스텝 생성 실패: {exc}")
                    steps = []

    if steps:
        if template_mode == "custom_flow":
            flow_errors, flow_warnings = validate_custom_flow_steps(steps)
            errors.extend(flow_errors)
            warnings.extend(flow_warnings)
        step_errors, step_warnings = validate_generated_steps(steps)
        errors.extend(step_errors)
        warnings.extend(step_warnings)

    return {
        "template": template,
        "values": values,
        "steps": steps,
        "errors": errors,
        "warnings": warnings,
    }


def summarize_steps(steps: list[StepData]) -> list[str]:
    lines: list[str] = []
    for idx, step in enumerate(steps, start=1):
        detail = ""
        if step.type == "keyboard":
            mode = getattr(step, "keyboard_mode", "text")
            detail = f" mode={mode} key='{getattr(step, 'key_string', '')}'"
        elif step.type in {"key", "key_down", "key_up", "key_hold"}:
            detail = f" key='{getattr(step, 'key_string', '')}'"
        elif step.type == "wait":
            detail = f" wait_ms={int(getattr(step, 'wait_ms', 0) or 0)}"
        elif step.type == "start_loop":
            detail = f" loop_count={int(getattr(step, 'loop_count', 0) or 0)}"
        elif step.type == "end_loop":
            detail = f" start_loop_id={getattr(step, 'start_loop_id', '')}"
        elif step.type == "load_data_file":
            detail = f" path='{getattr(step, 'data_file_path', '')}'"
        elif step.type == "run_macro":
            detail = f" path='{getattr(step, 'target_macro_path', '')}'"
        elif step.type == "ocr_store":
            detail = (
                f" var='{getattr(step, 'ocr_store_var', '')}'"
                f" roi=({getattr(step, 'ocr_roi_x', 0)},{getattr(step, 'ocr_roi_y', 0)},"
                f"{getattr(step, 'ocr_roi_w', 0)},{getattr(step, 'ocr_roi_h', 0)})"
            )
        elif step.type == "jump_if":
            detail = (
                f" if {getattr(step, 'condition_var', '')} "
                f"{getattr(step, 'condition_operator', '==')} "
                f"{getattr(step, 'condition_value', '')}"
                f" -> {getattr(step, 'target_true_id', '')}"
            )
        elif step.type == "screenshot_roi":
            detail = f" save='{getattr(step, 'screenshot_save_path', '')}'"
        lines.append(f"{idx}. [{step.type}] {step.name}{detail}")
    return lines

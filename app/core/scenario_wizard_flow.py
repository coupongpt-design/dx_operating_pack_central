from __future__ import annotations

import copy
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import StepData


REFERENCE_FIELDS = (
    "target_true_id",
    "target_false_id",
    "branch_on_fail_goto_id",
    "on_match_goto_id",
    "pixel_success_goto_id",
    "start_loop_id",
    "jump_to_step_id",
)


@dataclass
class ValidationIssue:
    level: str  # error | warning
    code: str
    message: str
    step_id: str | None = None


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())

    try:
        os.replace(str(tmp), str(target))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def _iter_step_references(step: StepData) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for field in REFERENCE_FIELDS:
        raw = getattr(step, field, None)
        if raw is None:
            continue
        target = str(raw).strip()
        if not target:
            continue
        refs.append((field, target))
    return refs


def _blueprint_step_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("step_uuid") or "").strip()


def _iter_blueprint_references(row: dict[str, Any]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for field in REFERENCE_FIELDS:
        raw = row.get(field)
        if raw is None:
            continue
        target = str(raw).strip()
        if not target:
            continue
        refs.append((field, target))
    return refs


def _step_from_blueprint(row: dict[str, Any]) -> StepData:
    if not isinstance(row, dict):
        raise ValueError("steps_blueprint 항목은 object(dict)여야 합니다.")

    payload = copy.deepcopy(row)
    step_id = str(payload.get("id") or payload.get("step_uuid") or "").strip()
    if not step_id:
        step_id = _new_id()
    payload["id"] = step_id
    payload.pop("step_uuid", None)
    return StepData(**payload)


def materialize_custom_flow_steps(steps_blueprint: list[dict[str, Any]]) -> list[StepData]:
    if not isinstance(steps_blueprint, list):
        raise ValueError("custom_flow 템플릿의 steps_blueprint는 list여야 합니다.")

    source_steps: list[StepData] = []
    seen_ids: set[str] = set()
    for row in steps_blueprint:
        step = _step_from_blueprint(row)
        if step.id in seen_ids:
            raise ValueError(f"중복 step id가 있습니다: {step.id}")
        seen_ids.add(step.id)
        source_steps.append(step)

    id_map: dict[str, str] = {step.id: _new_id() for step in source_steps}
    runtime_steps: list[StepData] = []
    for source in source_steps:
        data = source.to_serializable()
        data["id"] = id_map[source.id]
        step = StepData(**data)
        # Keep source blueprint id/name for runtime observability and failure mapping.
        step.source_step_id = source.id
        step.source_step_name = source.name
        for field, old_target in _iter_step_references(step):
            if old_target in id_map:
                setattr(step, field, id_map[old_target])
        runtime_steps.append(step)
    return runtime_steps


def _issue(level: str, code: str, message: str, step_id: str | None = None) -> ValidationIssue:
    return ValidationIssue(level=level, code=code, message=message, step_id=step_id)


def validate_custom_flow_steps_detailed(steps: list[StepData]) -> dict[str, list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    if not steps:
        errors.append(_issue("error", "EMPTY_FLOW", "custom_flow 스텝이 비어 있습니다."))
        return {"errors": errors, "warnings": warnings}

    ids = [str(getattr(step, "id", "") or "") for step in steps]
    if any(not sid for sid in ids):
        errors.append(_issue("error", "EMPTY_ID", "빈 step id가 존재합니다."))
        return {"errors": errors, "warnings": warnings}

    if len(set(ids)) != len(ids):
        errors.append(_issue("error", "DUPLICATE_ID", "중복 step id가 존재합니다."))

    id_set = set(ids)
    id_to_index = {sid: idx for idx, sid in enumerate(ids)}

    start_ids = {step.id for step in steps if step.type == "start_loop"}
    end_refs = [str(getattr(step, "start_loop_id", "") or "").strip() for step in steps if step.type == "end_loop"]
    for sid in start_ids:
        if sid not in end_refs:
            errors.append(
                _issue(
                    "error",
                    "LOOP_PAIR_MISSING",
                    f"start_loop({sid})에 대응하는 end_loop가 없습니다.",
                    step_id=sid,
                )
            )

    for step in steps:
        for field, target in _iter_step_references(step):
            if target == step.id:
                errors.append(
                    _issue(
                        "error",
                        "SELF_REFERENCE",
                        f"{step.name}: 자기 자신을 참조합니다. ({field})",
                        step_id=step.id,
                    )
                )
                continue
            if target not in id_set:
                errors.append(
                    _issue(
                        "error",
                        "ORPHAN_REFERENCE",
                        f"{step.name}: 참조 대상이 없습니다. ({field} -> {target})",
                        step_id=step.id,
                    )
                )
                continue

            src_idx = id_to_index.get(step.id, -1)
            dst_idx = id_to_index.get(target, -1)
            if src_idx >= 0 and dst_idx >= 0 and dst_idx < src_idx and field != "start_loop_id":
                warnings.append(
                    _issue(
                        "warning",
                        "BACKWARD_JUMP",
                        f"{step.name}: 뒤로 점프 참조가 있습니다. 탈출 조건을 확인하세요.",
                        step_id=step.id,
                    )
                )

    edges: dict[str, set[str]] = {sid: set() for sid in ids}
    for idx, step in enumerate(steps):
        sid = step.id
        if idx + 1 < len(steps):
            edges[sid].add(steps[idx + 1].id)
        for _, target in _iter_step_references(step):
            if target in id_set:
                edges[sid].add(target)

    start = steps[0].id
    visited: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        stack.extend(list(edges.get(cur, set())))

    unreachable = [step for step in steps if step.id not in visited]
    if unreachable:
        names = ", ".join(step.name for step in unreachable)
        warnings.append(_issue("warning", "UNREACHABLE", "도달 불가능한 스텝이 있습니다: " + names))

    for step in steps:
        if step.type == "start_loop" and int(getattr(step, "loop_count", 0) or 0) == 0:
            warnings.append(
                _issue(
                    "warning",
                    "INFINITE_LOOP_RISK",
                    f"{step.name}: loop_count=0(무한 반복)입니다. 종료 조건을 확인하세요.",
                    step_id=step.id,
                )
            )

    return {"errors": errors, "warnings": warnings}


def validate_custom_flow_steps(steps: list[StepData]) -> tuple[list[str], list[str]]:
    result = validate_custom_flow_steps_detailed(steps)
    errors = [row.message for row in result["errors"]]
    warnings = [row.message for row in result["warnings"]]
    return errors, warnings


def validate_custom_flow_blueprint(steps_blueprint: list[dict[str, Any]]) -> dict[str, list[ValidationIssue]]:
    try:
        steps = [_step_from_blueprint(row) for row in steps_blueprint]
    except Exception as exc:
        return {"errors": [_issue("error", "INVALID_BLUEPRINT", str(exc))], "warnings": []}
    return validate_custom_flow_steps_detailed(steps)


def find_references_in_blueprint(steps_blueprint: list[dict[str, Any]], target_step_id: str) -> list[dict[str, str]]:
    target = str(target_step_id or "").strip()
    if not target:
        return []
    results: list[dict[str, str]] = []
    for row in steps_blueprint:
        sid = _blueprint_step_id(row)
        if sid == target:
            continue
        for field, ref in _iter_blueprint_references(row):
            if ref == target:
                results.append(
                    {
                        "step_id": sid,
                        "step_name": str(row.get("name") or sid or ""),
                        "field": field,
                        "target_id": ref,
                    }
                )
    return results


def delete_step_with_lazy_repair(
    steps_blueprint: list[dict[str, Any]],
    target_step_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    target = str(target_step_id or "").strip()
    copied = [copy.deepcopy(row) for row in steps_blueprint]

    delete_index = -1
    for idx, row in enumerate(copied):
        if _blueprint_step_id(row) == target:
            delete_index = idx
            break
    if delete_index < 0:
        return copied, [], [f"삭제 대상 스텝을 찾을 수 없습니다: {target}"]

    next_id = ""
    if delete_index + 1 < len(copied):
        next_id = _blueprint_step_id(copied[delete_index + 1])

    rewired: list[dict[str, str]] = []
    warnings: list[str] = []
    for row in copied:
        sid = _blueprint_step_id(row)
        if sid == target:
            continue
        for field, ref in _iter_blueprint_references(row):
            if ref != target:
                continue
            old_target = ref
            if field == "start_loop_id":
                row[field] = None
                new_target = ""
                warnings.append(f"{row.get('name') or sid}: loop 참조가 끊겨 수동 수정이 필요합니다.")
            else:
                row[field] = next_id or None
                new_target = next_id
                if not next_id:
                    warnings.append(f"{row.get('name') or sid}: 대상 스텝 삭제 후 연결 대상이 없어 None 처리되었습니다.")
            rewired.append(
                {
                    "step_id": sid,
                    "step_name": str(row.get("name") or sid or ""),
                    "field": field,
                    "old_target": old_target,
                    "new_target": new_target,
                }
            )

    copied.pop(delete_index)
    return copied, rewired, warnings

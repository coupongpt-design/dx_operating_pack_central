from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence
import json


DEFAULT_SCHEMA_VERSION = 1
DEFAULT_ROLE_ORDER = ("planner", "implementer", "reviewer", "tester", "documenter")
COMPACT_ROLE_ORDER = ("planner", "implementer", "reviewer")
PRECISION_FILE_MARKERS = (
    "stepdata",
    "models.py",
    "serial",
    "runner",
    "signal",
)


@dataclass(frozen=True)
class RoleDefinition:
    role_id: str
    title: str
    objective: str
    guidance: str


@dataclass
class RoleTurn:
    role_id: str
    title: str
    prompt: str
    response: str

    def to_dict(self) -> dict[str, str]:
        return {
            "role_id": self.role_id,
            "title": self.title,
            "prompt": self.prompt,
            "response": self.response,
        }


@dataclass
class OrchestrationResult:
    task: str
    context: str
    mode: str
    role_ids: list[str]
    turns: list[RoleTurn]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "context": self.context,
            "mode": self.mode,
            "role_ids": list(self.role_ids),
            "turns": [turn.to_dict() for turn in self.turns],
            "summary": self.summary,
        }


class RoleBackend(Protocol):
    def generate(self, role: RoleDefinition, prompt: str, *, max_output_chars: int) -> str:
        ...


def _clip_tail(text: str, max_chars: int, label: str) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    return f"[{label} truncated; tail only]\n{tail}"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _short_line(text: str) -> str:
    lines = [row.strip() for row in text.splitlines() if row.strip()]
    return lines[0] if lines else ""


def default_roles() -> list[RoleDefinition]:
    return [
        RoleDefinition(
            role_id="planner",
            title="Planner",
            objective="Split the task into practical execution phases.",
            guidance=(
                "Return concrete phases with sequence and success criteria. "
                "Keep assumptions explicit."
            ),
        ),
        RoleDefinition(
            role_id="implementer",
            title="Implementer",
            objective="Describe exact implementation actions and files.",
            guidance=(
                "Focus on code-level edits, edge cases, and rollback notes. "
                "Prefer minimal-risk change sets."
            ),
        ),
        RoleDefinition(
            role_id="reviewer",
            title="Reviewer",
            objective="Find likely regressions and logic flaws.",
            guidance=(
                "Prioritize high-severity risks first, then medium risks. "
                "Point to verification actions."
            ),
        ),
        RoleDefinition(
            role_id="tester",
            title="Tester",
            objective="Propose targeted test strategy and gates.",
            guidance=(
                "List must-pass tests and failure diagnostics. "
                "Cover positive and negative paths."
            ),
        ),
        RoleDefinition(
            role_id="documenter",
            title="Documenter",
            objective="Summarize doc updates for users and maintainers.",
            guidance=(
                "Highlight changed behavior and usage examples. "
                "Keep changelog-ready bullet format."
            ),
        ),
    ]


class HeuristicRoleBackend:
    """Offline fallback backend for deterministic multi-role runs."""

    def generate(self, role: RoleDefinition, prompt: str, *, max_output_chars: int) -> str:
        task = self._extract(prompt, "TASK:")
        context = self._extract(prompt, "CONTEXT:")
        previous = self._extract(prompt, "PREVIOUS_OUTPUTS:")
        seed = _short_line(task) or "No task provided."
        has_context = bool(_clean_text(context))
        has_prev = bool(_clean_text(previous))

        if role.role_id == "planner":
            text = (
                f"1) Goal: {seed}\n"
                "2) Break into setup -> implementation -> validation.\n"
                "3) Define done condition: tests pass and behavior is verified.\n"
                f"4) Context attached: {'yes' if has_context else 'no'}."
            )
        elif role.role_id == "implementer":
            text = (
                "1) Implement smallest safe slice first.\n"
                "2) Add/adjust tests for the changed path.\n"
                "3) Keep interfaces backward compatible when possible.\n"
                f"4) Planning input detected: {'yes' if has_prev else 'no'}."
            )
        elif role.role_id == "reviewer":
            text = (
                "1) Check regression points around changed files.\n"
                "2) Verify error handling and null/empty input behavior.\n"
                "3) Confirm no hidden side effects in existing flows.\n"
                f"4) Task focus: {seed}"
            )
        elif role.role_id == "tester":
            text = (
                "1) Run fast unit tests for touched modules.\n"
                "2) Run integration path for end-to-end behavior.\n"
                "3) Add one negative test per critical branch.\n"
                f"4) Shared context available: {'yes' if has_context else 'no'}."
            )
        elif role.role_id == "documenter":
            text = (
                "1) Update spec/status/changelog documents.\n"
                "2) Document user-visible behavior changes.\n"
                "3) Add usage example for newly added workflow.\n"
                f"4) Primary task headline: {seed}"
            )
        else:
            text = (
                f"Role '{role.role_id}' executed with fallback output.\n"
                f"Task headline: {seed}"
            )

        return _clip_tail(text, max_output_chars, "response")

    @staticmethod
    def _extract(prompt: str, marker: str) -> str:
        idx = prompt.find(marker)
        if idx < 0:
            return ""
        start = idx + len(marker)
        tail = prompt[start:]
        next_markers = ("\nTASK:", "\nCONTEXT:", "\nPREVIOUS_OUTPUTS:", "\nROLE_GUIDANCE:")
        end = len(tail)
        for row in next_markers:
            hit = tail.find(row)
            if hit >= 0:
                end = min(end, hit)
        return tail[:end].strip()


class MultiRoleAIOrchestrator:
    def __init__(
        self,
        backend: RoleBackend | None = None,
        *,
        roles: Sequence[RoleDefinition] | None = None,
        max_context_chars: int = 3000,
        compact_output_chars: int = 700,
        precision_output_chars: int = 1300,
    ) -> None:
        self.backend: RoleBackend = backend or HeuristicRoleBackend()
        if roles is not None and len(roles) == 0:
            raise ValueError("at least one role is required")
        self.roles: dict[str, RoleDefinition] = {
            role.role_id: role for role in (roles or default_roles())
        }
        if not self.roles:
            raise ValueError("at least one role is required")
        self.max_context_chars = max(500, int(max_context_chars))
        self.compact_output_chars = max(200, int(compact_output_chars))
        self.precision_output_chars = max(self.compact_output_chars, int(precision_output_chars))

    def select_mode(
        self,
        task: str,
        context: str = "",
        changed_files: Sequence[str] | None = None,
    ) -> str:
        task_text = _clean_text(task).lower()
        context_text = _clean_text(context).lower()
        changed_list = [str(row or "").strip().lower() for row in (changed_files or []) if str(row or "").strip()]
        score = 0

        # AGENTS-aligned hard triggers
        if len(changed_list) >= 5:
            return "precision"
        if any(any(marker in path for marker in PRECISION_FILE_MARKERS) for path in changed_list):
            return "precision"

        if len(task_text) >= 180:
            score += 1
        if len(context_text) >= 400:
            score += 1

        precision_keywords = (
            "architecture",
            "refactor",
            "migration",
            "concurrency",
            "security",
            "e2e",
            "rollback",
            "아키텍처",
            "리팩터",
            "마이그레이션",
            "동시성",
            "보안",
            "검증",
            "회귀",
            "테스트",
        )
        if any(key in task_text for key in precision_keywords):
            score += 2
        if any(key in context_text for key in precision_keywords):
            score += 1

        return "precision" if score >= 2 else "compact"

    def run(
        self,
        *,
        task: str,
        context: str = "",
        mode: str = "auto",
        role_ids: Sequence[str] | None = None,
        changed_files: Sequence[str] | None = None,
    ) -> OrchestrationResult:
        task_text = _clean_text(task)
        if not task_text:
            raise ValueError("task is required")

        mode_value = self._resolve_mode(mode, task_text, context, changed_files=changed_files)
        selected_role_ids = self._resolve_role_ids(mode_value, role_ids)
        output_limit = (
            self.precision_output_chars if mode_value == "precision" else self.compact_output_chars
        )

        transcript = ""
        turns: list[RoleTurn] = []

        for role_id in selected_role_ids:
            role = self.roles[role_id]
            prompt = self._build_prompt(
                role=role,
                task=task_text,
                context=context,
                previous_outputs=transcript,
            )
            response = _clean_text(
                self.backend.generate(role, prompt, max_output_chars=output_limit)
            ) or "(empty response)"
            response = _clip_tail(response, output_limit, "response")
            turn = RoleTurn(
                role_id=role.role_id,
                title=role.title,
                prompt=prompt,
                response=response,
            )
            turns.append(turn)
            transcript = self._append_transcript(transcript, turn)

        summary = self._build_summary(mode_value, turns)
        return OrchestrationResult(
            task=task_text,
            context=_clean_text(context),
            mode=mode_value,
            role_ids=list(selected_role_ids),
            turns=turns,
            summary=summary,
        )

    def _resolve_mode(
        self,
        mode: str,
        task: str,
        context: str,
        *,
        changed_files: Sequence[str] | None = None,
    ) -> str:
        raw = _clean_text(mode).lower()
        if raw in ("", "auto"):
            return self.select_mode(task, context, changed_files=changed_files)
        if raw not in ("compact", "precision"):
            raise ValueError(f"unsupported mode: {mode}")
        return raw

    def _resolve_role_ids(self, mode: str, role_ids: Sequence[str] | None) -> list[str]:
        if role_ids is None:
            default_ids = COMPACT_ROLE_ORDER if mode == "compact" else DEFAULT_ROLE_ORDER
            available = [role_id for role_id in default_ids if role_id in self.roles]
            if available:
                return available
            return list(self.roles.keys())

        cleaned = [row.strip() for row in role_ids if _clean_text(row)]
        if not cleaned:
            raise ValueError("role_ids is empty")
        for role_id in cleaned:
            if role_id not in self.roles:
                raise ValueError(f"unknown role_id: {role_id}")
        return cleaned

    def _build_prompt(
        self,
        *,
        role: RoleDefinition,
        task: str,
        context: str,
        previous_outputs: str,
    ) -> str:
        clipped_context = _clip_tail(_clean_text(context), self.max_context_chars, "context")
        clipped_previous = _clip_tail(
            _clean_text(previous_outputs), self.max_context_chars, "previous outputs"
        )
        return "\n".join(
            [
                f"ROLE: {role.role_id} ({role.title})",
                f"ROLE_OBJECTIVE:\n{role.objective}",
                f"TASK:\n{task}",
                f"CONTEXT:\n{clipped_context}",
                f"PREVIOUS_OUTPUTS:\n{clipped_previous}",
                f"ROLE_GUIDANCE:\n{role.guidance}",
            ]
        )

    def _append_transcript(self, transcript: str, turn: RoleTurn) -> str:
        snippet = f"[{turn.role_id}] {turn.response}"
        merged = snippet if not transcript else f"{transcript}\n{snippet}"
        return _clip_tail(merged, self.max_context_chars, "previous outputs")

    @staticmethod
    def _build_summary(mode: str, turns: Sequence[RoleTurn]) -> str:
        lines: list[str] = [f"mode={mode}"]
        for turn in turns:
            head = _short_line(turn.response) or "(empty)"
            lines.append(f"- {turn.role_id}: {head}")
        return "\n".join(lines)


def load_roles_from_json(path: str | Path) -> list[RoleDefinition]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("roles file must be an object")
    schema_version = int(raw.get("schema_version", 0) or 0)
    if schema_version != DEFAULT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported roles schema_version: {schema_version} (expected {DEFAULT_SCHEMA_VERSION})"
        )
    rows = raw.get("roles")
    if not isinstance(rows, list) or not rows:
        raise ValueError("roles list is required")

    roles: list[RoleDefinition] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each role must be an object")
        role = RoleDefinition(
            role_id=_clean_text(row.get("role_id")),
            title=_clean_text(row.get("title")),
            objective=_clean_text(row.get("objective")),
            guidance=_clean_text(row.get("guidance")),
        )
        if not role.role_id:
            raise ValueError("role_id is required")
        if role.role_id in seen:
            raise ValueError(f"duplicate role_id: {role.role_id}")
        seen.add(role.role_id)
        if not role.title:
            raise ValueError(f"title is required for role_id={role.role_id}")
        if not role.objective:
            raise ValueError(f"objective is required for role_id={role.role_id}")
        if not role.guidance:
            raise ValueError(f"guidance is required for role_id={role.role_id}")
        roles.append(role)
    return roles


def render_result_markdown(result: OrchestrationResult) -> str:
    lines = [
        f"# Multi-Role AI Result ({result.mode})",
        "",
        "## Task",
        result.task,
        "",
        "## Summary",
        result.summary,
        "",
    ]
    for turn in result.turns:
        lines.extend(
            [
                f"## {turn.title} ({turn.role_id})",
                turn.response,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"

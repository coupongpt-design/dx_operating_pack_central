from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evaluator import ConditionEvaluator
from .models import StepData


@dataclass
class SimulationTransition:
    step_index: int
    next_index: int
    reason: str


@dataclass
class SimulationReport:
    visited_indices: list[int] = field(default_factory=list)
    transitions: list[SimulationTransition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    terminated_reason: str = "completed"


class LogicPathSimulator:
    """Static path predictor for macro steps without performing real I/O."""

    SENSOR_STEP_TYPES = {
        "image_click",
        "wait_for_image",
        "pixel_check",
        "ocr_check_text",
        "screen_check",
        "compare_images",
    }

    def __init__(
        self,
        steps: list[StepData],
        context: dict[str, Any] | None,
        evaluator: ConditionEvaluator | None = None,
        *,
        max_hops: int = 160,
        assume_sensor_match: bool = False,
    ):
        self.steps = list(steps or [])
        self.context = dict(context or {})
        self.evaluator = evaluator or ConditionEvaluator()
        self.max_hops = max(1, int(max_hops))
        self.assume_sensor_match = bool(assume_sensor_match)
        self._id_to_index = {
            str(getattr(s, "id", "") or ""): i for i, s in enumerate(self.steps)
        }
        self._loop_counters: dict[str, int] = {}

    def _resolve_target_index(self, target_id: Any) -> int | None:
        if not target_id:
            return None
        return self._id_to_index.get(str(target_id))

    def _jump_target(self, step: StepData) -> int | None:
        return self._resolve_target_index(
            getattr(step, "target_true_id", None) or getattr(step, "jump_to_step_id", None)
        )

    def _jump_false_target(self, step: StepData) -> int | None:
        return self._resolve_target_index(
            getattr(step, "target_false_id", None)
            or getattr(step, "branch_on_fail_goto_id", None)
        )

    def _simulate_jump_if(self, step: StepData) -> tuple[int | None, str]:
        var_name = str(getattr(step, "condition_var", "") or "").strip()
        actual = self.context.get(var_name) if var_name else None
        result, _ = self.evaluator.evaluate(step, self.context, actual_value=actual)
        if result:
            return self._jump_target(step), "jump_if:true"
        false_target = self._jump_false_target(step)
        if false_target is not None:
            return false_target, "jump_if:false-target"
        return None, "jump_if:false"

    def _simulate_ocr_jump_if(self, step: StepData) -> tuple[int | None, str]:
        var_name = str(getattr(step, "condition_var", "") or "").strip()
        if var_name and var_name in self.context:
            result, _ = self.evaluator.evaluate(step, self.context, actual_value=self.context.get(var_name))
            if result:
                return self._jump_target(step), "ocr_jump_if:eval-true"
            false_target = self._jump_false_target(step)
            if false_target is not None:
                return false_target, "ocr_jump_if:eval-false-target"
            return None, "ocr_jump_if:eval-false"

        if self.assume_sensor_match:
            return self._jump_target(step), "ocr_jump_if:sensor-true"
        false_target = self._jump_false_target(step)
        if false_target is not None:
            return false_target, "ocr_jump_if:sensor-false-target"
        return None, "ocr_jump_if:sensor-false"

    def _simulate_image_branch(self, step: StepData) -> tuple[int | None, str]:
        branch_mode = str(getattr(step, "branch_mode", "image") or "image").lower()
        if branch_mode == "variable":
            var_name = str(getattr(step, "branch_var", "") or "").strip()
            actual = self.context.get(var_name) if var_name else None
            result, _ = self.evaluator.evaluate(step, self.context, actual_value=actual)
            if result:
                target = self._resolve_target_index(
                    getattr(step, "target_true_id", None) or getattr(step, "branch_true_goto_id", None)
                )
                return target, "image_branch:variable-true"
            target = self._resolve_target_index(
                getattr(step, "target_false_id", None) or getattr(step, "branch_false_goto_id", None)
            )
            return target, "image_branch:variable-false"

        if self.assume_sensor_match:
            target = self._resolve_target_index(
                getattr(step, "target_true_id", None) or getattr(step, "branch_true_goto_id", None)
            )
            return target, "image_branch:image-true"
        target = self._resolve_target_index(
            getattr(step, "target_false_id", None) or getattr(step, "branch_false_goto_id", None)
        )
        return target, "image_branch:image-false"

    def _simulate_sensor_step(self, step: StepData) -> tuple[int | None, str]:
        if self.assume_sensor_match:
            return self._resolve_target_index(getattr(step, "on_match_goto_id", None)), "sensor:true"
        return self._resolve_target_index(getattr(step, "branch_on_fail_goto_id", None)), "sensor:false"

    def _simulate_end_loop(self, step: StepData) -> tuple[int | None, str]:
        start_id = str(getattr(step, "start_loop_id", "") or "").strip()
        if not start_id:
            return None, "end_loop:no-start"
        if start_id not in self._loop_counters:
            return None, "end_loop:no-counter"
        count = self._loop_counters[start_id]
        if count == 0:
            return self._resolve_target_index(start_id), "end_loop:infinite"
        if count > 1:
            self._loop_counters[start_id] = count - 1
            return self._resolve_target_index(start_id), "end_loop:repeat"
        self._loop_counters.pop(start_id, None)
        return None, "end_loop:complete"

    def _next_index(self, idx: int) -> tuple[int | None, str]:
        step = self.steps[idx]
        stype = str(getattr(step, "type", "") or "").lower()

        if stype == "start_loop":
            sid = str(getattr(step, "id", "") or "").strip()
            if sid and sid not in self._loop_counters:
                self._loop_counters[sid] = max(0, int(getattr(step, "loop_count", 0) or 0))
            return idx + 1, "start_loop"

        if stype == "end_loop":
            target, reason = self._simulate_end_loop(step)
            if target is None:
                return idx + 1, reason
            return target, reason

        if stype == "jump_if":
            target, reason = self._simulate_jump_if(step)
            if target is None:
                return idx + 1, reason
            return target, reason

        if stype == "ocr_jump_if":
            target, reason = self._simulate_ocr_jump_if(step)
            if target is None:
                return idx + 1, reason
            return target, reason

        if stype == "image_branch":
            target, reason = self._simulate_image_branch(step)
            if target is None:
                return idx + 1, reason
            return target, reason

        if stype in self.SENSOR_STEP_TYPES:
            target, reason = self._simulate_sensor_step(step)
            if target is None:
                return idx + 1, reason
            return target, reason

        return idx + 1, "next"

    def simulate(self, start_index: int = 0) -> SimulationReport:
        report = SimulationReport()
        if not self.steps:
            report.terminated_reason = "empty"
            return report

        idx = max(0, int(start_index))
        if idx >= len(self.steps):
            report.terminated_reason = "start_out_of_range"
            report.warnings.append("start index out of range")
            return report

        for _ in range(self.max_hops):
            if idx < 0 or idx >= len(self.steps):
                report.terminated_reason = "out_of_range"
                report.warnings.append(f"index out of range: {idx}")
                break

            report.visited_indices.append(idx)
            next_idx, reason = self._next_index(idx)
            if next_idx is None:
                report.terminated_reason = reason
                break

            if next_idx < 0 or next_idx >= len(self.steps):
                report.transitions.append(
                    SimulationTransition(step_index=idx, next_index=next_idx, reason=f"{reason}:dangling")
                )
                report.terminated_reason = "dangling"
                report.warnings.append(f"dangling jump from #{idx + 1} to {next_idx}")
                break

            report.transitions.append(SimulationTransition(step_index=idx, next_index=next_idx, reason=reason))
            idx = next_idx
        else:
            report.terminated_reason = "max_hops"
            report.warnings.append(f"max_hops reached ({self.max_hops})")

        return report

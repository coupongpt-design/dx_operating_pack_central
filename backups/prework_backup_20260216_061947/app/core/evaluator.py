import operator
from typing import Any, Dict, Tuple

from .models import StepData


class ConditionEvaluator:
    """
    Centralized condition evaluation for jump/branch steps.
    Handles variable comparisons and accepts a pre-fetched actual value
    (e.g., from OCR) when provided.
    """

    def __init__(self, image_processor: Any = None):
        self.image_processor = image_processor
        self._op_map = {
            ">": operator.gt,
            "<": operator.lt,
            "==": operator.eq,
            "!=": operator.ne,
            ">=": operator.ge,
            "<=": operator.le,
        }

    # ---- Helpers ---------------------------------------------------------
    def _to_number(self, val: Any) -> Any:
        """Try to coerce to float/int for numeric comparison; fallback to original."""
        try:
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                text = val.strip()
                if not text:
                    return val
                text = text.replace(",", "").replace(" ", "")
                if text.endswith("%"):
                    text = text[:-1]
                try:
                    f = float(text)
                    return int(f) if f.is_integer() else f
                except Exception:
                    return val
            f = float(val)
            # if integral, keep as int for nicer equality semantics
            return int(f) if f.is_integer() else f
        except Exception:
            return val

    def _resolve_field(self, step: StepData, keys: Tuple[str, ...]) -> Any:
        for k in keys:
            val = None
            if hasattr(step, k):
                val = getattr(step, k)
            elif isinstance(step, dict) and k in step:
                val = step[k]
            if val not in (None, ""):
                return val
        return None

    # ---- Public API ------------------------------------------------------
    def evaluate(self, step: StepData, context: Dict[str, Any], actual_value: Any = None) -> Tuple[bool, Any]:
        """
        Evaluate a condition for jump/branch.
        - step: StepData or dict-like object containing operator/operand info.
        - context: variable context for lookups.
        - actual_value: pre-fetched value (e.g., OCR result) if available.
        Returns (result, value_used).
        """
        step_type = getattr(step, "type", None) or (step.get("type") if isinstance(step, dict) else None)
        # Determine operator/operands with preference per step type
        if step_type in ("jump_if", "ocr_jump_if"):
            op_token = self._resolve_field(step, ("condition_operator", "condition_op", "branch_op"))
            compare_to = self._resolve_field(step, ("condition_value", "branch_value"))
            var_name = self._resolve_field(step, ("condition_var", "branch_var"))
        else:
            op_token = self._resolve_field(step, ("branch_op", "condition_operator", "condition_op"))
            compare_to = self._resolve_field(step, ("branch_value", "condition_value"))
            var_name = self._resolve_field(step, ("branch_var", "condition_var"))

        # Determine source value
        value = actual_value
        if value is None and var_name:
            value = context.get(var_name)

        # Normalize
        value_num = self._to_number(value)
        compare_num = self._to_number(compare_to)

        # Fallback: unknown operator
        if op_token not in self._op_map:
            return False, value

        try:
            result = self._op_map[op_token](value_num, compare_num)
        except Exception:
            result = False
        return result, value

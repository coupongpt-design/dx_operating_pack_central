from __future__ import annotations

from tools.task_finish import build_template_text


def test_build_template_text_includes_gate_summaries() -> None:
    record = {
        "targeted_pass": True,
        "targeted_summary": "15 passed in 0.12s",
        "full_suite_required": True,
        "full_suite_pass": True,
        "full_suite_summary": "483 passed, 1 skipped in 21.66s",
    }
    text = build_template_text("feat: demo", record)
    assert text.startswith("feat: demo")
    assert "- targeted: PASS (15 passed in 0.12s)" in text
    assert "- full suite: PASS (483 passed, 1 skipped in 21.66s)" in text


def test_build_template_text_non_risk_marks_not_required() -> None:
    record = {
        "targeted_pass": True,
        "targeted_summary": "1 passed in 0.02s",
        "full_suite_required": False,
        "full_suite_pass": True,
    }
    text = build_template_text("chore: demo", record)
    assert "- full suite: not required (no risk trigger)" in text

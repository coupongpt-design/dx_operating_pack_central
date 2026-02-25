from __future__ import annotations

from tools.task_finish import build_template_text
from tools.task_finish import _confirm_doc_sync
from tools.task_finish import _needs_doc_sync_confirmation
from tools.task_finish import parse_args


def test_build_template_text_includes_gate_summaries() -> None:
    record = {
        "targeted_pass": True,
        "targeted_summary": "15 passed in 0.12s",
        "full_suite_required": True,
        "full_suite_pass": True,
        "full_suite_summary": "483 passed, 1 skipped in 21.66s",
    }
    text = build_template_text("feat: demo", record, "feature")
    assert text.startswith("feat: demo")
    assert "Scope: feature" in text
    assert "- targeted: PASS (15 passed in 0.12s)" in text
    assert "- full suite: PASS (483 passed, 1 skipped in 21.66s)" in text


def test_build_template_text_non_risk_marks_not_required() -> None:
    record = {
        "targeted_pass": True,
        "targeted_summary": "1 passed in 0.02s",
        "full_suite_required": False,
        "full_suite_pass": True,
    }
    text = build_template_text("chore: demo", record, "docs")
    assert "Scope: docs" in text
    assert "- full suite: not required (no risk trigger)" in text


def test_parse_args_scope_and_targeted() -> None:
    subject, targeted, scope, confirm_doc_sync, run_audit = parse_args(
        ["--subject", "feat: x", "--scope", "rule", "--targeted", "auto"]
    )
    assert subject == "feat: x"
    assert targeted == "auto"
    assert scope == "rule"
    assert confirm_doc_sync is False
    assert run_audit is False


def test_parse_args_targeted_with_scope_after_it() -> None:
    subject, targeted, scope, confirm_doc_sync, run_audit = parse_args(
        ["--subject", "feat: y", "--targeted", "python", "-m", "pytest", "-q", "tests/test_a.py", "--scope", "test"]
    )
    assert subject == "feat: y"
    assert targeted == "python -m pytest -q tests/test_a.py"
    assert scope == "test"
    assert confirm_doc_sync is False
    assert run_audit is False


def test_parse_args_flags() -> None:
    _, _, _, confirm_doc_sync, run_audit = parse_args(
        ["--confirm-doc-sync", "--run-audit"]
    )
    assert confirm_doc_sync is True
    assert run_audit is True


def test_needs_doc_sync_confirmation_when_partial_docs_touched() -> None:
    needs, touched, missing = _needs_doc_sync_confirmation(
        ["PROJECT_STATUS.md", "app/core/runner.py"]
    )
    assert needs is True
    assert touched == ["PROJECT_STATUS.md"]
    assert missing == ["DEV_LOG.md", "now_spec.md"]


def test_confirm_doc_sync_passes_with_explicit_flag() -> None:
    assert _confirm_doc_sync(["PROJECT_STATUS.md"], confirmed_flag=True) is True


def test_confirm_doc_sync_blocks_partial_without_flag() -> None:
    assert _confirm_doc_sync(["PROJECT_STATUS.md"], confirmed_flag=False) is False

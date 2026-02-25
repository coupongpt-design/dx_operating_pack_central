from __future__ import annotations

import time

from tools.git_hook_guards import compute_staged_hash
from tools.git_hook_guards import extract_tests_lines
from tools.git_hook_guards import is_artifact_cleanup_only
from tools.git_hook_guards import is_risk_triggered
from tools.git_hook_guards import parse_numstat
from tools.git_hook_guards import parse_name_status
from tools.git_hook_guards import validate_commit_message
from tools.git_hook_guards import validate_gate_record
from tools.git_hook_guards import validate_message_against_gate_record
from tools.git_hook_guards import validate_scope_limits
from tools.git_hook_guards import validate_staged_entries


def test_validate_commit_message_accepts_required_sections() -> None:
    message = """feat: sample

Summary:
- short summary

Changes:
- file.py changed

Tests:
- targeted: PASS
- full suite: 470 passed, 1 skipped in 22.29s

Risks/Follow-up:
- none
"""
    assert validate_commit_message(message) == []


def test_validate_commit_message_rejects_missing_targeted() -> None:
    message = """feat: sample

Summary:
- short summary
Changes:
- file.py changed
Tests:
- full suite: 470 passed, 1 skipped in 22.29s
Risks/Follow-up:
- none
"""
    errors = validate_commit_message(message)
    assert any("targeted" in err for err in errors)


def test_extract_tests_lines_returns_values() -> None:
    message = """Tests:
- targeted: PASS (12 passed in 0.13s)
- full suite: 480 passed, 1 skipped in 22.06s
"""
    lines = extract_tests_lines(message)
    assert lines["targeted"] == "PASS (12 passed in 0.13s)"
    assert lines["full_suite"] == "480 passed, 1 skipped in 22.06s"


def test_parse_name_status_handles_rename() -> None:
    parsed = parse_name_status("R100\tAGENTS.md\tAGENTS2.md\nM\tapp/main.py\n")
    assert parsed[0].status == "R100"
    assert parsed[0].paths == ("AGENTS.md", "AGENTS2.md")
    assert parsed[1].status == "M"
    assert parsed[1].paths == ("app/main.py",)


def test_validate_staged_entries_blocks_constitutional_rename() -> None:
    entries = parse_name_status("R100\tAGENTS.md\tAGENTS2.md\n")
    errors = validate_staged_entries(entries)
    assert any("constitutional file" in err for err in errors)


def test_validate_staged_entries_blocks_runtime_log_artifact() -> None:
    entries = parse_name_status("A\tlogs/any_runtime_log.jsonl\n")
    errors = validate_staged_entries(entries)
    assert any("blocked staged artifact" in err for err in errors)


def test_validate_staged_entries_allows_artifact_deletion() -> None:
    entries = parse_name_status("D\tlogs/old_run.jsonl\n")
    assert validate_staged_entries(entries) == []


def test_validate_staged_entries_allows_normal_code_change() -> None:
    entries = parse_name_status("M\tapp/main.py\nA\ttests/test_new_feature.py\n")
    assert validate_staged_entries(entries) == []


def test_is_risk_triggered_only_on_high_risk_paths() -> None:
    low = parse_name_status("M\tapp/ui/widgets.py\n")
    high = parse_name_status("M\tapp/core/runner.py\n")
    assert is_risk_triggered(low) is False
    assert is_risk_triggered(high) is True


def test_parse_numstat_and_scope_limits() -> None:
    files, changed = parse_numstat("10\t2\tapp/main.py\n3\t1\tapp/ui/widgets.py\n")
    assert files == 2
    assert changed == 16

    errors = validate_scope_limits(file_count=25, line_count=2000)
    assert any("staged files too large" in err for err in errors)
    assert any("staged changed lines too large" in err for err in errors)


def test_is_artifact_cleanup_only_true_for_deletes() -> None:
    entries = parse_name_status("D\tlogs/run_1.jsonl\nD\tapp/__pycache__/x.pyc\n")
    assert is_artifact_cleanup_only(entries) is True


def test_is_artifact_cleanup_only_false_for_non_delete() -> None:
    entries = parse_name_status("A\tlogs/run_1.jsonl\n")
    assert is_artifact_cleanup_only(entries) is False


def test_validate_staged_entries_blocks_backups_path() -> None:
    entries = parse_name_status("M\tbackups/snapshot.py\n")
    errors = validate_staged_entries(entries)
    assert any("blocked protected path change" in err for err in errors)


def test_validate_staged_entries_blocks_constitutional_mixed_changes() -> None:
    entries = parse_name_status("M\tAGENTS.md\nM\tapp/main.py\n")
    errors = validate_staged_entries(entries)
    assert any("must be isolated" in err for err in errors)


def test_validate_gate_record_accepts_valid_record() -> None:
    entries = parse_name_status("M\tapp/main.py\n")
    staged_hash = compute_staged_hash(entries)
    now = time.time()
    record = {
        "created_at": now,
        "head": "abc123",
        "staged_hash": staged_hash,
        "targeted_pass": True,
        "risk": True,
        "full_suite_pass": True,
    }
    errors = validate_gate_record(
        record,
        current_head="abc123",
        current_staged_hash=staged_hash,
        now_ts=now + 1,
    )
    assert errors == []


def test_validate_gate_record_rejects_mismatch_and_missing_full_suite() -> None:
    entries = parse_name_status("M\tapp/main.py\n")
    staged_hash = compute_staged_hash(entries)
    now = time.time()
    record = {
        "created_at": now - (4 * 60 * 60),
        "head": "old",
        "staged_hash": "other",
        "targeted_pass": True,
        "risk": True,
        "full_suite_pass": False,
    }
    errors = validate_gate_record(
        record,
        current_head="new",
        current_staged_hash=staged_hash,
        now_ts=now,
    )
    assert any("head mismatch" in err for err in errors)
    assert any("staged hash mismatch" in err for err in errors)
    assert any("full suite PASS missing" in err for err in errors)
    assert any("stale" in err for err in errors)


def test_validate_message_against_gate_record_accepts_risk_record() -> None:
    message = """Tests:
- targeted: PASS (12 passed in 0.13s)
- full suite: PASS (480 passed, 1 skipped in 22.06s)
"""
    record = {
        "targeted_pass": True,
        "targeted_summary": "12 passed in 0.13s",
        "risk": True,
        "full_suite_pass": True,
        "full_suite_summary": "480 passed, 1 skipped in 22.06s",
    }
    assert validate_message_against_gate_record(message, record) == []


def test_validate_message_against_gate_record_rejects_mismatch() -> None:
    message = """Tests:
- targeted: PASS (11 passed)
- full suite: PASS (470 passed)
"""
    record = {
        "targeted_pass": True,
        "targeted_summary": "12 passed in 0.13s",
        "risk": True,
        "full_suite_pass": True,
        "full_suite_summary": "480 passed, 1 skipped in 22.06s",
    }
    errors = validate_message_against_gate_record(message, record)
    assert any("targeted line mismatch" in err for err in errors)
    assert any("full suite line mismatch" in err for err in errors)

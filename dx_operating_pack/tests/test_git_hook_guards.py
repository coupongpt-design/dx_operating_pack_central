from __future__ import annotations

import subprocess
import time

from tools.git_hook_guards import compute_staged_hash
from tools.git_hook_guards import run_pre_commit_guard
from tools.git_hook_guards import extract_tests_lines
from tools.git_hook_guards import is_artifact_cleanup_only
from tools.git_hook_guards import is_risk_triggered
from tools.git_hook_guards import parse_numstat
from tools.git_hook_guards import parse_name_status
from tools.git_hook_guards import validate_commit_message
from tools.git_hook_guards import validate_gate_record
from tools.git_hook_guards import validate_message_against_gate_record
from tools.git_hook_guards import collect_scope_warnings
from tools.git_hook_guards import validate_scope_limits
from tools.git_hook_guards import validate_staged_entries


def test_validate_commit_message_accepts_required_sections() -> None:
    message = """feat: sample

Scope: feature

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

Scope: feature

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


def test_validate_commit_message_rejects_invalid_scope() -> None:
    message = """feat: sample

Scope: unknown

Summary:
- short summary

Changes:
- file.py changed

Tests:
- targeted: PASS
- full suite: not required (no risk trigger)

Risks/Follow-up:
- none
"""
    errors = validate_commit_message(message)
    assert any("invalid scope value" in err for err in errors)


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


def test_is_risk_triggered_ignores_artifact_paths() -> None:
    artifact_only = parse_name_status("D\ttests/__pycache__/test_signal_and_logic.cpython-313.pyc\n")
    assert is_risk_triggered(artifact_only) is False


def test_parse_numstat_and_scope_limits() -> None:
    files, changed = parse_numstat("10\t2\tapp/main.py\n3\t1\tapp/ui/widgets.py\n")
    assert files == 2
    assert changed == 16

    errors = validate_scope_limits(file_count=25, line_count=2000)
    assert any("staged files too large" in err for err in errors)
    assert any("staged changed lines too large" in err for err in errors)


def test_collect_scope_warnings_on_threshold_excess() -> None:
    warns = collect_scope_warnings(file_count=8, line_count=550)
    assert any("Scope too large (files)" in w for w in warns)
    assert any("Scope too large (lines)" in w for w in warns)


def test_is_artifact_cleanup_only_true_for_deletes() -> None:
    entries = parse_name_status("D\tlogs/run_1.jsonl\nD\tapp/__pycache__/x.pyc\n")
    assert is_artifact_cleanup_only(entries) is True


def test_is_artifact_cleanup_only_false_for_non_delete() -> None:
    entries = parse_name_status("A\tlogs/run_1.jsonl\n")
    assert is_artifact_cleanup_only(entries) is False


def test_validate_staged_entries_blocks_large_cleanup_mixed_commit() -> None:
    staged = "".join([f"D\tlogs/run_{i}.jsonl\n" for i in range(10)])
    staged += "M\tapp/main.py\n"
    entries = parse_name_status(staged)
    errors = validate_staged_entries(entries)
    assert any("chore(cleanup)" in err for err in errors)


def test_validate_staged_entries_allows_large_cleanup_only_commit() -> None:
    staged = "".join([f"D\tlogs/run_{i}.jsonl\n" for i in range(10)])
    entries = parse_name_status(staged)
    errors = validate_staged_entries(entries)
    assert all("chore(cleanup)" not in err for err in errors)


def test_validate_staged_entries_blocks_backups_path() -> None:
    entries = parse_name_status("M\tbackups/snapshot.py\n")
    errors = validate_staged_entries(entries)
    assert any("blocked protected path change" in err for err in errors)


def test_validate_staged_entries_blocks_constitutional_mixed_changes() -> None:
    entries = parse_name_status("M\tAGENTS.md\nM\tapp/main.py\n")
    errors = validate_staged_entries(entries)
    assert any("must be isolated" in err for err in errors)


def test_run_pre_commit_guard_emits_scope_warning(monkeypatch, capsys) -> None:
    ctx = run_pre_commit_guard.__globals__

    staged_text = "".join([f"M\tapp/ui/file_{i}.py\n" for i in range(8)])
    entries = parse_name_status(staged_text)
    staged_hash = compute_staged_hash(entries)

    def fake_git(*args: str) -> str:
        if args == ("diff", "--cached", "--name-status"):
            return staged_text
        if args == ("diff", "--cached", "--numstat"):
            return "".join([f"1\t0\tapp/ui/file_{i}.py\n" for i in range(8)])
        if args == ("rev-parse", "HEAD"):
            return "abc123\n"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setitem(ctx, "_git", fake_git)
    monkeypatch.setitem(
        ctx,
        "_load_gate_record",
        lambda: {
            "timestamp": time.time(),
            "head": "abc123",
            "staged_hash": staged_hash,
            "targeted_pass": True,
            "risk": False,
            "full_suite_pass": True,
        },
    )

    rc = run_pre_commit_guard()
    out = capsys.readouterr().out
    assert rc == 0
    assert "[pre-commit] warnings:" in out
    assert "Scope too large (files)" in out


def test_validate_gate_record_accepts_valid_record() -> None:
    entries = parse_name_status("M\tapp/main.py\n")
    staged_hash = compute_staged_hash(entries)
    now = time.time()
    record = {
        "timestamp": now,
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


def test_validate_gate_record_rejects_over_30min_old_timestamp() -> None:
    entries = parse_name_status("M\tapp/main.py\n")
    staged_hash = compute_staged_hash(entries)
    now = time.time()
    record = {
        "timestamp": now - (31 * 60),
        "head": "abc123",
        "staged_hash": staged_hash,
        "targeted_pass": True,
        "risk": False,
        "full_suite_pass": True,
    }
    errors = validate_gate_record(
        record,
        current_head="abc123",
        current_staged_hash=staged_hash,
        now_ts=now,
    )
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


def test_run_pre_commit_guard_allows_initial_commit_without_head(monkeypatch) -> None:
    ctx = run_pre_commit_guard.__globals__

    staged_text = "M\ttools/task_finish.py\n"
    entries = parse_name_status(staged_text)
    staged_hash = compute_staged_hash(entries)

    def fake_git(*args: str) -> str:
        if args == ("diff", "--cached", "--name-status"):
            return staged_text
        if args == ("diff", "--cached", "--numstat"):
            return "1\t0\ttools/task_finish.py\n"
        if args == ("rev-parse", "HEAD"):
            raise subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setitem(ctx, "_git", fake_git)
    monkeypatch.setitem(
        ctx,
        "_load_gate_record",
        lambda: {
            "timestamp": time.time(),
            "head": "",
            "staged_hash": staged_hash,
            "targeted_pass": True,
            "risk": False,
            "full_suite_pass": True,
        },
    )

    assert run_pre_commit_guard() == 0

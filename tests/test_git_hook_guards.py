from __future__ import annotations

from tools.git_hook_guards import parse_name_status
from tools.git_hook_guards import validate_commit_message
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
    entries = parse_name_status("A\tlogs/run_events_20260224_123000_x.jsonl\n")
    errors = validate_staged_entries(entries)
    assert any("blocked staged artifact" in err for err in errors)


def test_validate_staged_entries_allows_normal_code_change() -> None:
    entries = parse_name_status("M\tapp/main.py\nA\ttests/test_new_feature.py\n")
    assert validate_staged_entries(entries) == []

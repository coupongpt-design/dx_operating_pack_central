from __future__ import annotations

import os
import subprocess
import sys
from typing import Iterable

try:
    from tools.git_hook_guards import extract_tests_lines
    from tools.git_hook_guards import is_risk_triggered
    from tools.git_hook_guards import parse_name_status
    from tools.git_hook_guards import validate_commit_message
    from tools.git_hook_guards import validate_staged_entries
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from git_hook_guards import extract_tests_lines
    from git_hook_guards import is_risk_triggered
    from git_hook_guards import parse_name_status
    from git_hook_guards import validate_commit_message
    from git_hook_guards import validate_staged_entries


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _commit_range() -> tuple[str, str]:
    base = os.getenv("CI_BASE_SHA", "").strip()
    head = os.getenv("CI_HEAD_SHA", "").strip()
    if base and head:
        return base, head
    head = _git("rev-parse", "HEAD").strip()
    base = _git("rev-parse", "HEAD~1").strip()
    return base, head


def _iter_commits(base: str, head: str) -> Iterable[str]:
    out = _git("rev-list", "--reverse", f"{base}..{head}").strip()
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _commit_message(commit: str) -> str:
    return _git("show", "-s", "--format=%B", commit)


def _commit_entries(commit: str):
    text = _git("diff-tree", "--no-commit-id", "--name-status", "-r", commit)
    return parse_name_status(text)


def _validate_commit_tests_semantics(message: str, risk: bool) -> list[str]:
    errors: list[str] = []
    lines = extract_tests_lines(message)
    targeted = lines.get("targeted", "")
    full_suite = lines.get("full_suite", "")

    if targeted and not (targeted.startswith("PASS") or targeted.startswith("FAIL")):
        errors.append("targeted tests line must start with PASS/FAIL")
    if not full_suite:
        errors.append("full suite tests line missing")
        return errors

    low = full_suite.lower()
    if risk:
        if not (full_suite.startswith("PASS") or full_suite.startswith("FAIL")):
            errors.append("risk commit must provide full suite PASS/FAIL line")
    else:
        if (
            "not required" not in low
            and "skip" not in low
            and not (full_suite.startswith("PASS") or full_suite.startswith("FAIL"))
        ):
            errors.append("non-risk commit full suite line must be PASS/FAIL or not required/skip")
    return errors


def main() -> int:
    base, head = _commit_range()
    commits = list(_iter_commits(base, head))
    if not commits:
        print("governance guard: no commits in range")
        return 0

    all_errors: list[str] = []
    for commit in commits:
        message = _commit_message(commit)
        entries = _commit_entries(commit)
        risk = is_risk_triggered(entries)

        msg_errors = validate_commit_message(message)
        for err in msg_errors:
            all_errors.append(f"{commit}: commit message -> {err}")

        semantic_errors = _validate_commit_tests_semantics(message, risk=risk)
        for err in semantic_errors:
            all_errors.append(f"{commit}: commit tests semantics -> {err}")

        entry_errors = validate_staged_entries(entries)
        for err in entry_errors:
            all_errors.append(f"{commit}: file policy -> {err}")

    if all_errors:
        print("governance guard: FAIL")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print("governance guard: PASS")
    print(f"checked commits: {len(commits)} ({base[:7]}..{head[:7]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

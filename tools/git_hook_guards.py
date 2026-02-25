from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_COMMIT_HEADERS = (
    "Summary:",
    "Changes:",
    "Tests:",
    "Risks/Follow-up:",
)

CONSTITUTIONAL_FILES = {
    "AGENTS.md",
    ".cursorrules",
    "tests/test_rule_docs_sync.py",
    "tests/test_rule_guard_steps_mutation.py",
}

BLOCKED_STAGE_PATTERNS = (
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.pyc$"),
    re.compile(r"^logs/run_events_.*\.jsonl$"),
)


@dataclass(frozen=True)
class StagedEntry:
    status: str
    paths: tuple[str, ...]


def _norm(path: str) -> str:
    return path.replace("\\", "/").strip()


def validate_commit_message(text: str) -> list[str]:
    errors: list[str] = []
    normalized = text.replace("\r\n", "\n")

    for header in REQUIRED_COMMIT_HEADERS:
        if header not in normalized:
            errors.append(f"missing commit section: {header}")

    if not re.search(r"(?mi)^\s*-\s*targeted:\s*(PASS|FAIL)\b", normalized):
        errors.append("missing tests line: '- targeted: PASS / FAIL'")

    if not re.search(r"(?mi)^\s*-\s*full suite:\s*\S+", normalized):
        errors.append("missing tests line: '- full suite: ...'")

    return errors


def parse_name_status(text: str) -> list[StagedEntry]:
    entries: list[StagedEntry] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        entries.append(StagedEntry(status=parts[0], paths=tuple(_norm(p) for p in parts[1:] if p)))
    return entries


def validate_staged_entries(entries: list[StagedEntry]) -> list[str]:
    errors: list[str] = []
    for entry in entries:
        code = entry.status[:1]
        for path in entry.paths:
            if path in CONSTITUTIONAL_FILES and code in {"D", "R", "C"}:
                errors.append(
                    f"constitutional file may not be {entry.status}: {path} "
                    "(edit-in-place only)"
                )
            if any(pattern.search(path) for pattern in BLOCKED_STAGE_PATTERNS):
                errors.append(f"blocked staged artifact path: {path}")
    return errors


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def run_commit_msg_guard(msg_file: str) -> int:
    text = Path(msg_file).read_text(encoding="utf-8")
    errors = validate_commit_message(text)
    if not errors:
        return 0
    print("[commit-msg] rejected:")
    for err in errors:
        print(f"- {err}")
    return 1


def run_pre_commit_guard() -> int:
    staged_text = _git("diff", "--cached", "--name-status")
    entries = parse_name_status(staged_text)
    errors = validate_staged_entries(entries)
    if not errors:
        return 0
    print("[pre-commit] rejected:")
    for err in errors:
        print(f"- {err}")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python tools/git_hook_guards.py <commit-msg|pre-commit> [args]")
        return 2

    mode = argv[1]
    if mode == "commit-msg":
        if len(argv) < 3:
            print("commit-msg mode requires message file path")
            return 2
        return run_commit_msg_guard(argv[2])

    if mode == "pre-commit":
        return run_pre_commit_guard()

    print(f"unknown mode: {mode}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

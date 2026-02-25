from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_COMMIT_HEADERS = (
    "Summary:",
    "Changes:",
    "Tests:",
    "Risks/Follow-up:",
    "Scope:",
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
    re.compile(r"^logs/.*\.jsonl$"),
)

HIGH_RISK_PATH_PATTERNS = (
    re.compile(r"thread", re.IGNORECASE),
    re.compile(r"signal", re.IGNORECASE),
    re.compile(r"runner", re.IGNORECASE),
    re.compile(r"stepdata", re.IGNORECASE),
    re.compile(r"serialization", re.IGNORECASE),
    re.compile(r"basecommand", re.IGNORECASE),
    re.compile(r"undostack", re.IGNORECASE),
    re.compile(r"app/core/commands\.py$", re.IGNORECASE),
)

BLOCKED_USER_PATH_PATTERNS = (
    re.compile(r"(^|/)backups/"),
)

GATE_FILE = Path(".git") / "post_task_gate.json"
GATE_MAX_AGE_SEC = 30 * 60
MAX_STAGE_FILES = 18
MAX_STAGE_LINES = 1400
CLEANUP_ATOMIC_THRESHOLD = 10
ALLOWED_SCOPES = ("feature", "rule", "cleanup", "docs", "test")


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
    scope_match = re.search(r"(?mi)^\s*Scope:\s*([a-z_]+)\s*$", normalized)
    if not scope_match:
        errors.append("missing scope line: 'Scope: feature|rule|cleanup|docs|test'")
    else:
        scope = scope_match.group(1).strip().lower()
        if scope not in ALLOWED_SCOPES:
            errors.append(
                "invalid scope value: "
                f"'{scope}' (allowed: {'|'.join(ALLOWED_SCOPES)})"
            )

    return errors


def extract_tests_lines(text: str) -> dict[str, str]:
    normalized = text.replace("\r\n", "\n")
    out: dict[str, str] = {}
    mt = re.search(r"(?mi)^\s*-\s*targeted:\s*(.+?)\s*$", normalized)
    mf = re.search(r"(?mi)^\s*-\s*full suite:\s*(.+?)\s*$", normalized)
    if mt:
        out["targeted"] = mt.group(1).strip()
    if mf:
        out["full_suite"] = mf.group(1).strip()
    return out


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


def compute_staged_hash(entries: list[StagedEntry]) -> str:
    canon = "\n".join(f"{e.status}\t" + "\t".join(e.paths) for e in entries)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def is_risk_triggered(entries: list[StagedEntry]) -> bool:
    file_set = {path for entry in entries for path in entry.paths}
    for path in file_set:
        if _is_blocked_artifact(path):
            continue
        if any(pattern.search(path) for pattern in HIGH_RISK_PATH_PATTERNS):
            return True
    return False


def parse_numstat(text: str) -> tuple[int, int]:
    files = 0
    changed_lines = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        files += 1
        a, d = parts[0], parts[1]
        try:
            added = int(a) if a.isdigit() else 0
            deleted = int(d) if d.isdigit() else 0
        except ValueError:
            added, deleted = 0, 0
        changed_lines += added + deleted
    return files, changed_lines


def validate_scope_limits(file_count: int, line_count: int) -> list[str]:
    errors: list[str] = []
    if file_count > MAX_STAGE_FILES:
        errors.append(
            f"staged files too large ({file_count}>{MAX_STAGE_FILES}); split into atomic commits"
        )
    if line_count > MAX_STAGE_LINES:
        errors.append(
            f"staged changed lines too large ({line_count}>{MAX_STAGE_LINES}); split into atomic commits"
        )
    return errors


def _is_constitutional(path: str) -> bool:
    return path in CONSTITUTIONAL_FILES


def _is_blocked_artifact(path: str) -> bool:
    return any(pattern.search(path) for pattern in BLOCKED_STAGE_PATTERNS)


def is_artifact_cleanup_only(entries: list[StagedEntry]) -> bool:
    if not entries:
        return False
    for entry in entries:
        code = entry.status[:1]
        for path in entry.paths:
            if code != "D":
                return False
            if not _is_blocked_artifact(path):
                return False
    return True


def validate_staged_entries(entries: list[StagedEntry]) -> list[str]:
    errors: list[str] = []
    has_constitutional = False
    has_non_constitutional = False
    cleanup_artifact_delete_count = 0
    has_non_cleanup_change = False

    for entry in entries:
        code = entry.status[:1]
        for path in entry.paths:
            if _is_constitutional(path):
                has_constitutional = True
            else:
                has_non_constitutional = True

            if _is_constitutional(path) and code in {"D", "R", "C"}:
                errors.append(
                    f"constitutional file may not be {entry.status}: {path} "
                    "(edit-in-place only)"
                )
            if _is_blocked_artifact(path) and code != "D":
                errors.append(f"blocked staged artifact path: {path}")
            if any(pattern.search(path) for pattern in BLOCKED_USER_PATH_PATTERNS):
                errors.append(f"blocked protected path change: {path}")
            if _is_blocked_artifact(path) and code == "D":
                cleanup_artifact_delete_count += 1
            else:
                has_non_cleanup_change = True

    if has_constitutional and has_non_constitutional:
        errors.append(
            "constitutional file changes must be isolated (no mixing with feature/runtime files)"
        )
    if cleanup_artifact_delete_count >= CLEANUP_ATOMIC_THRESHOLD and has_non_cleanup_change:
        errors.append(
            "cleanup artifact deletions >= "
            f"{CLEANUP_ATOMIC_THRESHOLD} must be isolated in a dedicated "
            "chore(cleanup) commit"
        )
    return errors


def validate_gate_record(
    record: dict[str, Any],
    *,
    current_head: str,
    current_staged_hash: str,
    now_ts: float | None = None,
) -> list[str]:
    errors: list[str] = []
    now = now_ts if now_ts is not None else time.time()

    head = str(record.get("head", ""))
    staged_hash = str(record.get("staged_hash", ""))
    gate_ts_raw = record.get("timestamp", record.get("created_at", 0.0))
    try:
        gate_ts = float(gate_ts_raw)
    except (TypeError, ValueError):
        gate_ts = 0.0
    targeted_pass = bool(record.get("targeted_pass", False))
    risk = bool(record.get("risk", False))
    full_suite_pass = bool(record.get("full_suite_pass", False))

    if head != current_head:
        errors.append("post-task gate head mismatch; rerun gate script")
    if staged_hash != current_staged_hash:
        errors.append("post-task gate staged hash mismatch; rerun gate script")
    if not targeted_pass:
        errors.append("post-task gate targeted tests not marked PASS")
    if risk and not full_suite_pass:
        errors.append("risk trigger active but full suite PASS missing in post-task gate")
    if gate_ts <= 0:
        errors.append("post-task gate timestamp missing/invalid")
    elif now - gate_ts > GATE_MAX_AGE_SEC:
        errors.append("post-task gate is stale; rerun gate script")
    return errors


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _load_gate_record() -> dict[str, Any] | None:
    if not GATE_FILE.exists():
        return None
    try:
        return json.loads(GATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def validate_message_against_gate_record(
    message_text: str,
    gate_record: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    if gate_record is None:
        errors.append("post-task gate record missing for commit message validation")
        return errors

    msg_lines = extract_tests_lines(message_text)
    if "targeted" not in msg_lines or "full_suite" not in msg_lines:
        errors.append("cannot validate message vs gate: tests lines missing")
        return errors

    targeted_pass = bool(gate_record.get("targeted_pass", False))
    targeted_summary = str(gate_record.get("targeted_summary", "")).strip()
    expected_targeted_prefix = "PASS" if targeted_pass else "FAIL"
    targeted_msg = msg_lines["targeted"]
    if not targeted_msg.startswith(expected_targeted_prefix):
        errors.append(
            f"targeted line mismatch: expected prefix '{expected_targeted_prefix}', got '{targeted_msg}'"
        )
    if targeted_summary and targeted_summary not in targeted_msg:
        errors.append(
            "targeted line mismatch: must include gate targeted summary "
            f"('{targeted_summary}')"
        )

    risk = bool(gate_record.get("risk", False))
    full_suite_pass = bool(gate_record.get("full_suite_pass", False))
    full_suite_summary = str(gate_record.get("full_suite_summary", "")).strip()
    expected_full_prefix = "PASS" if full_suite_pass else "FAIL"
    full_msg = msg_lines["full_suite"]

    if risk:
        if not full_msg.startswith(expected_full_prefix):
            errors.append(
                f"full suite line mismatch: expected prefix '{expected_full_prefix}', got '{full_msg}'"
            )
        if full_suite_summary and full_suite_summary not in full_msg:
            errors.append(
                "full suite line mismatch: must include gate full-suite summary "
                f"('{full_suite_summary}')"
            )
    else:
        lowered = full_msg.lower()
        if "not required" not in lowered and "skip" not in lowered:
            errors.append(
                "full suite line mismatch: non-risk commit must state not required/skip"
            )
    return errors


def run_commit_msg_guard(msg_file: str) -> int:
    text = Path(msg_file).read_text(encoding="utf-8")
    errors = validate_commit_message(text)
    errors.extend(validate_message_against_gate_record(text, _load_gate_record()))
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
    numstat_text = _git("diff", "--cached", "--numstat")
    file_count, line_count = parse_numstat(numstat_text)
    if not is_artifact_cleanup_only(entries):
        errors.extend(validate_scope_limits(file_count, line_count))

    if not entries:
        errors.append("no staged changes detected")

    gate_record = _load_gate_record()
    if gate_record is None:
        errors.append(
            "post-task gate record missing: run "
            "'python tools/post_task_gate.py --targeted \"<targeted pytest command>\"'"
        )
    else:
        current_head = _git("rev-parse", "HEAD").strip()
        current_staged_hash = compute_staged_hash(entries)
        errors.extend(
            validate_gate_record(
                gate_record,
                current_head=current_head,
                current_staged_hash=current_staged_hash,
            )
        )

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

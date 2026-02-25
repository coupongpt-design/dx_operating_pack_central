from __future__ import annotations

import subprocess
import sys
from typing import Iterable

try:
    from tools.git_hook_guards import BLOCKED_STAGE_PATTERNS
    from tools.git_hook_guards import parse_name_status
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from git_hook_guards import BLOCKED_STAGE_PATTERNS
    from git_hook_guards import parse_name_status


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _is_cleanup_artifact(path: str) -> bool:
    return any(pattern.search(path) for pattern in BLOCKED_STAGE_PATTERNS)


def _count_cleanup_artifact_deletes(name_status_text: str) -> int:
    entries = parse_name_status(name_status_text)
    return sum(
        1
        for entry in entries
        if entry.status[:1] == "D"
        for path in entry.paths
        if _is_cleanup_artifact(path)
    )


def run_guard() -> int:
    staged_text = _git("diff", "--cached", "--name-status")
    entries = parse_name_status(staged_text)
    if not entries:
        print("task-start guard: clean index (no staged changes)")
        return 0

    cleanup_deletes = _count_cleanup_artifact_deletes(staged_text)
    print("task-start guard: BLOCKED")
    print(f"- staged entries: {len(entries)}")
    if cleanup_deletes:
        print(f"- cleanup artifact deletes staged: {cleanup_deletes}")
    print("- action: commit or unstage staged changes before starting a new task")
    return 1


def main(argv: Iterable[str] | None = None) -> int:
    _ = argv
    return run_guard()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

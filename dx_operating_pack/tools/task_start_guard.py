from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

try:
    from tools.git_hook_guards import BLOCKED_STAGE_PATTERNS
    from tools.git_hook_guards import parse_name_status
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from git_hook_guards import BLOCKED_STAGE_PATTERNS
    from git_hook_guards import parse_name_status

SNAPSHOT_FILES = (
    Path("dx_operating_pack/docs_for_ai/CONTEXT_CORE.md"),
    Path("dx_operating_pack/docs_for_ai/CONTEXT_UI.md"),
    Path("dx_operating_pack/docs_for_ai/CONTEXT_SNAPSHOT.md"),
)
SNAPSHOT_MAX_AGE_SEC = 24 * 60 * 60  # 24 hours


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


def _warn_stale_snapshots() -> None:
    """Warn if context snapshot files are older than SNAPSHOT_MAX_AGE_SEC."""
    now = time.time()
    for snap in SNAPSHOT_FILES:
        if not snap.exists():
            continue
        age = now - snap.stat().st_mtime
        if age > SNAPSHOT_MAX_AGE_SEC:
            hours = int(age // 3600)
            print(
                f"[snapshot-warn] {snap.name} is {hours}h old "
                f"(threshold={SNAPSHOT_MAX_AGE_SEC // 3600}h). "
                "Consider regenerating: python tools/generate_context_snapshot.py --scope core"
            )


def run_guard() -> int:
    _warn_stale_snapshots()

    staged_text = _git("diff", "--cached", "--name-status")
    entries = parse_name_status(staged_text)
    if not entries:
        print("task-start guard: clean index (no staged changes)")
        print("task-start guard policy: this is the mandatory first gate for every task")
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

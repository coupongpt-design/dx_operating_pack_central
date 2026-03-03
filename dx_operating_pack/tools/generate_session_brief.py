from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUT = Path("dx_operating_pack/docs_for_ai/SESSION_BRIEF.md")
DEFAULT_MAX_COMMITS = 5
GATE_FILE = Path(".git") / "post_task_gate.json"
SNAPSHOT_FILES = (
    Path("dx_operating_pack/docs_for_ai/CONTEXT_CORE.md"),
    Path("dx_operating_pack/docs_for_ai/CONTEXT_UI.md"),
    Path("dx_operating_pack/docs_for_ai/CONTEXT_SNAPSHOT.md"),
)
SNAPSHOT_MAX_AGE_SEC = 24 * 60 * 60


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _safe_git(*args: str) -> str:
    try:
        return _git(*args)
    except Exception:
        return ""


def _load_gate() -> dict:
    if not GATE_FILE.exists():
        return {}
    try:
        return json.loads(GATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _gate_summary(now_ts: float) -> list[str]:
    payload = _load_gate()
    if not payload:
        return ["- gate: missing (`.git/post_task_gate.json`)"]

    ts_raw = payload.get("timestamp")
    try:
        gate_ts = float(ts_raw)
    except (TypeError, ValueError):
        return ["- gate: invalid timestamp"]

    age = max(0, int(now_ts - gate_ts))
    targeted = "PASS" if bool(payload.get("targeted_pass", False)) else "FAIL"
    full_required = bool(payload.get("full_suite_required", payload.get("risk", False)))
    if full_required:
        full = "PASS" if bool(payload.get("full_suite_pass", False)) else "FAIL"
    else:
        full = "SKIP"
    stamp = datetime.fromtimestamp(gate_ts, tz=timezone.utc).isoformat()
    return [
        f"- gate_timestamp_utc: {stamp}",
        f"- gate_age_sec: {age}",
        f"- targeted: {targeted}",
        f"- full_suite: {full}",
    ]


def _snapshot_summary(now_ts: float) -> list[str]:
    rows: list[str] = []
    for path in SNAPSHOT_FILES:
        if not path.exists():
            rows.append(f"- {path.name}: missing")
            continue
        age = max(0, int(now_ts - path.stat().st_mtime))
        state = "fresh" if age <= SNAPSHOT_MAX_AGE_SEC else "stale"
        rows.append(f"- {path.name}: {state} (age={age}s)")
    return rows


def _latest_commits(max_commits: int) -> list[str]:
    out = _safe_git("log", "--oneline", f"-n{max_commits}")
    rows = [line.strip() for line in out.splitlines() if line.strip()]
    if rows:
        return rows
    return ["(no commits found)"]


def _last_commit_changed_files(limit: int = 12) -> list[str]:
    out = _safe_git("show", "--name-only", "--pretty=format:", "--no-renames", "HEAD")
    rows: list[str] = []
    seen: set[str] = set()
    for line in out.splitlines():
        item = line.strip().replace("\\", "/")
        if not item or item in seen:
            continue
        seen.add(item)
        rows.append(item)
        if len(rows) >= limit:
            break
    if rows:
        return rows
    return ["(no changed files in HEAD)"]


def build_brief(max_commits: int = DEFAULT_MAX_COMMITS) -> str:
    now = time.time()
    now_utc = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
    branch = _safe_git("branch", "--show-current").strip() or "-"
    head = _safe_git("rev-parse", "--short", "HEAD").strip() or "-"

    lines: list[str] = []
    lines.append("# SESSION BRIEF")
    lines.append("")
    lines.append(f"- generated_at_utc: {now_utc}")
    lines.append(f"- branch: `{branch}`")
    lines.append(f"- head: `{head}`")
    lines.append("")
    lines.append("## Fast Catch-Up Order")
    lines.append("1. `dx_operating_pack/docs_for_ai/INTERFACES.md`")
    lines.append("2. `dx_operating_pack/docs_for_ai/SCOPE_GUIDE.md`")
    lines.append("3. `dx_operating_pack/docs_for_ai/CONTEXT_SNAPSHOT.md`")
    lines.append("")
    lines.append("## Recommended Commands")
    lines.append("- `python tools/task_start_guard.py`")
    lines.append(
        "- `python tools/generate_context_snapshot.py --scope all --out "
        "dx_operating_pack/docs_for_ai/CONTEXT_SNAPSHOT.md`"
    )
    lines.append("- `python tools/generate_session_brief.py`")
    lines.append("")
    lines.append("## Recent Commits")
    for row in _latest_commits(max_commits):
        lines.append(f"- {row}")
    lines.append("")
    lines.append("## HEAD Changed Files")
    for row in _last_commit_changed_files():
        lines.append(f"- `{row}`")
    lines.append("")
    lines.append("## Gate Status")
    lines.extend(_gate_summary(now))
    lines.append("")
    lines.append("## Snapshot Freshness")
    lines.extend(_snapshot_summary(now))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one-page session brief for quick project catch-up.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output markdown path.")
    parser.add_argument("--max-commits", type=int, default=DEFAULT_MAX_COMMITS, help="Number of recent commits.")
    args = parser.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = Path(".").resolve() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_brief(max_commits=max(1, int(args.max_commits))), encoding="utf-8")
    print(f"[ok] session brief written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

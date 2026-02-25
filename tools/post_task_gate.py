from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

try:
    from tools.git_hook_guards import compute_staged_hash
    from tools.git_hook_guards import is_risk_triggered
    from tools.git_hook_guards import parse_name_status
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from git_hook_guards import compute_staged_hash
    from git_hook_guards import is_risk_triggered
    from git_hook_guards import parse_name_status

GATE_FILE = Path(".git") / "post_task_gate.json"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _run_shell(command: str) -> tuple[int, str]:
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


def _extract_pytest_summary(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if " passed" in line or " failed" in line or " skipped" in line:
            return line
    return "summary unavailable"


def run_gate(targeted_cmd: str) -> int:
    staged_text = _git("diff", "--cached", "--name-status")
    entries = parse_name_status(staged_text)
    if not entries:
        print("no staged changes; stage files before running post-task gate")
        return 1

    head = _git("rev-parse", "HEAD").strip()
    staged_hash = compute_staged_hash(entries)
    risk = is_risk_triggered(entries)

    targeted_rc, targeted_output = _run_shell(targeted_cmd)
    targeted_summary = _extract_pytest_summary(targeted_output)
    targeted_pass = targeted_rc == 0

    full_cmd = "python -m pytest -q"
    full_rc = 0
    full_output = ""
    full_summary = "not required"
    full_suite_pass = True

    if risk:
        full_rc, full_output = _run_shell(full_cmd)
        full_summary = _extract_pytest_summary(full_output)
        full_suite_pass = full_rc == 0

    record = {
        "created_at": time.time(),
        "head": head,
        "staged_hash": staged_hash,
        "risk": risk,
        "targeted_command": targeted_cmd,
        "targeted_pass": targeted_pass,
        "targeted_summary": targeted_summary,
        "full_suite_required": risk,
        "full_suite_command": full_cmd if risk else "",
        "full_suite_pass": full_suite_pass,
        "full_suite_summary": full_summary,
    }
    GATE_FILE.write_text(json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"post-task gate written: {GATE_FILE}")
    print(f"targeted: {'PASS' if targeted_pass else 'FAIL'} | {targeted_summary}")
    if risk:
        print(f"full suite: {'PASS' if full_suite_pass else 'FAIL'} | {full_summary}")
    else:
        print("full suite: SKIP (no risk trigger)")

    if targeted_pass and full_suite_pass:
        return 0
    return 1


def parse_targeted(argv: Sequence[str] | None = None) -> str:
    items = list(argv) if argv is not None else []
    if not items:
        raise ValueError(
            "missing args. usage: python tools/post_task_gate.py --targeted python -m pytest -q tests/..."
        )
    try:
        idx = items.index("--targeted")
    except ValueError as exc:
        raise ValueError(
            "missing --targeted. usage: python tools/post_task_gate.py --targeted python -m pytest -q tests/..."
        ) from exc
    tokens = items[idx + 1 :]
    if not tokens:
        raise ValueError("empty targeted command after --targeted")
    return " ".join(tokens)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        targeted_cmd = parse_targeted(argv)
    except ValueError as exc:
        print(str(exc))
        return 2
    return run_gate(targeted_cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

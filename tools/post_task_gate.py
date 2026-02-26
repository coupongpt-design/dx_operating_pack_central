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
    from tools.test_selector import build_pytest_command
    from tools.test_selector import filter_existing_tests
    from tools.test_selector import select_tests
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from git_hook_guards import compute_staged_hash
    from git_hook_guards import is_risk_triggered
    from git_hook_guards import parse_name_status
    from test_selector import build_pytest_command
    from test_selector import filter_existing_tests
    from test_selector import select_tests

GATE_FILE = Path(".git") / "post_task_gate.json"
GATE_TTL_SEC = 30 * 60


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _has_app_code_changes(entries: Sequence[object]) -> bool:
    for entry in entries:
        paths = getattr(entry, "paths", ())
        for path in paths:
            norm = str(path).replace("\\", "/")
            if norm.startswith("app/") and norm.endswith(".py"):
                return True
    return False


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


def _harvest_knowledge_from_staged() -> None:
    script_candidates = (
        Path("tools/capture_lesson_draft.py"),
        Path("dx_operating_pack/tools/capture_lesson_draft.py"),
    )
    script = next((p for p in script_candidates if p.exists()), None)
    if script is None:
        print("[harvest] skip: capture_lesson_draft.py not found")
        return
    cmd = [
        sys.executable,
        str(script),
        "--from-staged",
        "--title",
        "Post Task Gate Harvest",
    ]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    out = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if completed.returncode == 0:
        print("[harvest] PASS")
        if out:
            print(out)
    else:
        print("[harvest] WARN: capture failed")
        if out:
            print(out)


def run_gate(targeted_cmd: str, *, harvest_feedback: bool = True) -> int:
    staged_text = _git("diff", "--cached", "--name-status")
    entries = parse_name_status(staged_text)
    if not entries:
        print("no staged changes; stage files before running post-task gate")
        return 1

    head = _git("rev-parse", "HEAD").strip()
    staged_hash = compute_staged_hash(entries)
    risk = is_risk_triggered(entries)

    effective_targeted_cmd = targeted_cmd
    selected_tests: list[str] = []
    if targeted_cmd.strip().lower() == "auto":
        staged_paths = [p for e in entries for p in e.paths]
        selected_tests = filter_existing_tests(select_tests(staged_paths))
        if not selected_tests:
            if _has_app_code_changes(entries):
                print(
                    "post-task gate: app code changes detected but auto targeted "
                    "selection returned no tests"
                )
            else:
                print("post-task gate: auto targeted selection returned no tests")
            return 1
        effective_targeted_cmd = build_pytest_command(selected_tests)

    targeted_rc, targeted_output = _run_shell(effective_targeted_cmd)
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

    gate_ts = time.time()
    record = {
        "timestamp": gate_ts,
        "created_at": gate_ts,
        "ttl_sec": GATE_TTL_SEC,
        "head": head,
        "staged_hash": staged_hash,
        "risk": risk,
        "targeted_mode": "auto" if targeted_cmd.strip().lower() == "auto" else "manual",
        "targeted_command": effective_targeted_cmd,
        "targeted_selected_tests": selected_tests,
        "targeted_pass": targeted_pass,
        "targeted_summary": targeted_summary,
        "full_suite_required": risk,
        "full_suite_command": full_cmd if risk else "",
        "full_suite_pass": full_suite_pass,
        "full_suite_summary": full_summary,
    }
    GATE_FILE.write_text(json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"post-task gate written: {GATE_FILE}")
    print(f"gate ttl: {GATE_TTL_SEC // 60} minutes")
    print(f"targeted: {'PASS' if targeted_pass else 'FAIL'} | {targeted_summary}")
    if selected_tests:
        print(f"targeted auto tests: {', '.join(selected_tests)}")
    if risk:
        print(f"full suite: {'PASS' if full_suite_pass else 'FAIL'} | {full_summary}")
    else:
        print("full suite: SKIP (no risk trigger)")

    if targeted_pass and full_suite_pass and harvest_feedback:
        _harvest_knowledge_from_staged()

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
    if len(tokens) == 1 and tokens[0].lower() == "auto":
        return "auto"
    return " ".join(tokens)


def parse_harvest_feedback(argv: Sequence[str] | None = None) -> bool:
    items = list(argv) if argv is not None else []
    return "--skip-harvest" not in items


def main(argv: Sequence[str] | None = None) -> int:
    try:
        targeted_cmd = parse_targeted(argv)
    except ValueError as exc:
        print(str(exc))
        return 2
    harvest_feedback = parse_harvest_feedback(argv)
    return run_gate(targeted_cmd, harvest_feedback=harvest_feedback)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Any


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from app.core.multi_role_ai import (  # noqa: E402
    GeminiCliRoleBackend,
    MultiRoleAIOrchestrator,
    load_roles_from_json,
    render_result_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-role AI orchestration.")
    parser.add_argument("--task", required=True, help="Main task statement.")
    parser.add_argument("--context", default="", help="Optional context.")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "compact", "precision"],
        help="Execution mode selection.",
    )
    parser.add_argument(
        "--roles",
        default="",
        help="Comma-separated role IDs. Example: planner,implementer,reviewer",
    )
    parser.add_argument(
        "--roles-file",
        default="",
        help="Optional JSON file to override role definitions.",
    )
    parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "json"],
        help="Output format.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file path hint for mode decision. Can be repeated.",
    )
    parser.add_argument(
        "--backend",
        default="heuristic",
        choices=["heuristic", "gemini-cli"],
        help="Role generation backend.",
    )
    parser.add_argument(
        "--gemini-command",
        default=os.environ.get("GEMINI_CLI_COMMAND", "gemini"),
        help="Gemini CLI command path when --backend gemini-cli is used.",
    )
    parser.add_argument(
        "--gemini-model",
        default=os.environ.get("GEMINI_CLI_MODEL", ""),
        help="Optional Gemini model name passed to the CLI backend.",
    )
    parser.add_argument(
        "--gemini-extra-arg",
        action="append",
        default=[],
        help="Extra Gemini CLI arg. Can be repeated.",
    )
    parser.add_argument(
        "--gemini-timeout-sec",
        type=int,
        default=180,
        help="Gemini CLI timeout in seconds.",
    )
    return parser.parse_args()


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _collect_git_state() -> dict[str, set[str]] | None:
    proc = _run_git(["status", "--porcelain"])
    if proc.returncode != 0:
        return None
    tracked: set[str] = set()
    untracked: set[str] = set()
    for row in (proc.stdout or "").splitlines():
        if len(row) < 3:
            continue
        status = row[:2]
        path = row[3:].strip()
        if not path:
            continue
        if status == "??":
            untracked.add(path)
        else:
            tracked.add(path)
    return {"tracked": tracked, "untracked": untracked}


def _safe_git_diff() -> str:
    proc = _run_git(["diff", "--no-color"])
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def _compute_session_delta(
    baseline: dict[str, set[str]] | None,
    current: dict[str, set[str]] | None,
) -> dict[str, list[str]]:
    if not baseline or not current:
        return {"new_tracked_files": [], "new_untracked_files": []}
    new_tracked = sorted(current["tracked"] - baseline["tracked"])
    new_untracked = sorted(current["untracked"] - baseline["untracked"])
    return {
        "new_tracked_files": new_tracked,
        "new_untracked_files": new_untracked,
    }


def _auto_rollback_changes(
    baseline: dict[str, set[str]] | None,
) -> dict[str, Any]:
    current = _collect_git_state()
    delta = _compute_session_delta(baseline, current)
    targets = list(delta["new_tracked_files"])
    rolled_back: list[str] = []
    failed: list[str] = []
    for path in targets:
        proc = _run_git(["checkout", "--", path])
        if proc.returncode == 0:
            rolled_back.append(path)
        else:
            failed.append(path)
    return {
        "attempted": bool(targets),
        "targets": targets,
        "rolled_back": rolled_back,
        "failed": failed,
    }


def _extract_json_objects(text: str) -> list[dict[str, Any]]:
    candidates: list[str] = []
    body = str(text or "").strip()
    if body:
        candidates.append(body)
    for block in re.findall(r"```json\s*(\{.*?\})\s*```", body, flags=re.IGNORECASE | re.DOTALL):
        candidates.append(block.strip())
    parsed: list[dict[str, Any]] = []
    for row in candidates:
        try:
            obj = json.loads(row)
        except Exception:
            continue
        if isinstance(obj, dict):
            parsed.append(obj)
    return parsed


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in ("true", "1", "yes", "y", "pass", "approved"):
        return True
    if raw in ("false", "0", "no", "n", "fail", "rejected"):
        return False
    return None


def _is_guardian_approved(response: str) -> bool:
    text = str(response or "")
    for obj in _extract_json_objects(text):
        for key in ("is_approved", "approved", "pass"):
            if key in obj:
                parsed = _coerce_bool(obj.get(key))
                if parsed is not None:
                    return parsed
    if re.search(r"\bis_approved\s*[:=]\s*false\b", text, flags=re.IGNORECASE):
        return False
    if re.search(r"\bFAIL\b", text, flags=re.IGNORECASE):
        return False
    if re.search(r"\bPASS\b", text, flags=re.IGNORECASE):
        return True
    return True


def _find_turn(result, role_ids: set[str]):
    for turn in result.turns:
        if str(turn.role_id or "").lower() in role_ids:
            return turn
    return None


def _make_session_dir() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    base = os.path.join(ROOT, "logs", "ai_sessions", stamp)
    os.makedirs(base, exist_ok=True)
    return base


def _write_session_artifacts(
    result,
    *,
    session_dir: str,
    git_diff: str,
    session_delta: dict[str, list[str]],
    guardian_turn,
    is_approved: bool,
    rollback_report: dict[str, Any],
) -> None:
    planner_turn = _find_turn(result, {"planner"})
    executor_turn = _find_turn(result, {"executor", "implementer"})
    planner_path = os.path.join(session_dir, "planner_plan.md")
    with open(planner_path, "w", encoding="utf-8") as fp:
        fp.write("# Planner Plan\n\n")
        if planner_turn is not None:
            fp.write(str(planner_turn.response or "").strip() + "\n")
        else:
            fp.write("(planner output not found)\n")

    executor_payload = {
        "task": result.task,
        "mode": result.mode,
        "executor_role_id": getattr(executor_turn, "role_id", ""),
        "executor_response": getattr(executor_turn, "response", ""),
        "new_tracked_files": list(session_delta.get("new_tracked_files", [])),
        "new_untracked_files": list(session_delta.get("new_untracked_files", [])),
        "git_diff": git_diff,
    }
    with open(os.path.join(session_dir, "executor_diff.json"), "w", encoding="utf-8") as fp:
        json.dump(executor_payload, fp, ensure_ascii=False, indent=2)

    guardian_payload = {
        "is_approved": bool(is_approved),
        "guardian_role_id": getattr(guardian_turn, "role_id", ""),
        "guardian_response": getattr(guardian_turn, "response", ""),
        "hard_gate_triggered": not bool(is_approved),
        "rollback": rollback_report,
    }
    with open(os.path.join(session_dir, "guardian_report.json"), "w", encoding="utf-8") as fp:
        json.dump(guardian_payload, fp, ensure_ascii=False, indent=2)


def main() -> int:
    args = parse_args()

    roles = None
    if args.roles_file:
        roles = load_roles_from_json(args.roles_file)

    backend = None
    if args.backend == "gemini-cli":
        backend = GeminiCliRoleBackend(
            command=args.gemini_command,
            model=args.gemini_model,
            extra_args=args.gemini_extra_arg,
            timeout_sec=args.gemini_timeout_sec,
        )

    orchestrator = MultiRoleAIOrchestrator(backend=backend, roles=roles)
    role_ids = [row.strip() for row in args.roles.split(",") if row.strip()] or None
    changed_files = [str(row or "").strip() for row in (args.changed_file or []) if str(row or "").strip()]
    baseline_state = _collect_git_state()

    result = orchestrator.run(
        task=args.task,
        context=args.context,
        mode=args.mode,
        role_ids=role_ids,
        changed_files=changed_files,
    )

    guardian_turn = _find_turn(result, {"guardian", "reviewer"})
    is_approved = True if guardian_turn is None else _is_guardian_approved(getattr(guardian_turn, "response", ""))
    rollback_report: dict[str, Any] = {"attempted": False, "targets": [], "rolled_back": [], "failed": []}
    if not is_approved:
        rollback_report = _auto_rollback_changes(baseline_state)

    current_state = _collect_git_state()
    session_delta = _compute_session_delta(baseline_state, current_state)
    git_diff_text = _safe_git_diff()
    session_dir = _make_session_dir()
    _write_session_artifacts(
        result,
        session_dir=session_dir,
        git_diff=git_diff_text,
        session_delta=session_delta,
        guardian_turn=guardian_turn,
        is_approved=is_approved,
        rollback_report=rollback_report,
    )

    if not is_approved:
        print(f"[ai_sessions] saved: {session_dir}", file=sys.stderr)
        print("[HARD_GATE] Guardian rejected output. Process aborted.", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_result_markdown(result))
    print(f"[ai_sessions] saved: {session_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

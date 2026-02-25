from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable
from typing import Sequence

try:
    from tools.git_hook_guards import CONSTITUTIONAL_FILES
    from tools.git_hook_guards import is_artifact_cleanup_only
    from tools.git_hook_guards import parse_name_status
    from tools.preflight_env import run_preflight
    from tools.post_task_gate import GATE_FILE
    from tools.post_task_gate import run_gate
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from git_hook_guards import CONSTITUTIONAL_FILES
    from git_hook_guards import is_artifact_cleanup_only
    from git_hook_guards import parse_name_status
    from preflight_env import run_preflight
    from post_task_gate import GATE_FILE
    from post_task_gate import run_gate

TEMPLATE_PATH = Path(".git") / "TASK_COMMIT_TEMPLATE.md"
ALLOWED_SCOPES = ("feature", "rule", "cleanup", "docs", "test")
DOC_SYNC_FILES = ("PROJECT_STATUS.md", "now_spec.md", "DEV_LOG.md")
DOC_MTIME_WARN_SEC = 5 * 60


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _staged_exists() -> bool:
    out = _git("diff", "--cached", "--name-only")
    return bool(out.strip())


def _staged_entries():
    out = _git("diff", "--cached", "--name-status")
    return parse_name_status(out)


def _staged_paths() -> list[str]:
    return [p for entry in _staged_entries() for p in entry.paths]


def _needs_doc_sync_confirmation(staged_paths: list[str]) -> tuple[bool, list[str], list[str]]:
    docs = set(DOC_SYNC_FILES)
    touched = sorted(set(staged_paths).intersection(docs))
    if not touched:
        return (False, touched, [])
    missing = sorted(docs.difference(touched))
    return (len(missing) > 0, touched, missing)


def _confirm_doc_sync(
    staged_paths: list[str],
    *,
    confirmed_flag: bool,
    stdin_reader: Callable[[], str] | None = None,
) -> bool:
    needs_confirm, touched, missing = _needs_doc_sync_confirmation(staged_paths)
    if not needs_confirm:
        return True
    if confirmed_flag:
        print(
            "doc-sync confirm: acknowledged partial docs update "
            f"(touched={touched}, missing={missing})"
        )
        return True
    if sys.stdin.isatty():
        print(
            "doc-sync check: partial docs update detected "
            f"(touched={touched}, missing={missing})"
        )
        print("did you verify all three docs are intentionally handled? [y/N]: ", end="")
        reader = stdin_reader or input
        answer = str(reader() or "").strip().lower()
        if answer in {"y", "yes"}:
            return True
    print(
        "doc-sync guard: blocked. update all docs or re-run with --confirm-doc-sync "
        f"(missing={missing})"
    )
    return False


def _doc_mtime_gap_seconds(paths: Sequence[str] = DOC_SYNC_FILES) -> float:
    mtimes: list[float] = []
    for rel in paths:
        path = Path(rel)
        if path.exists():
            mtimes.append(path.stat().st_mtime)
    if len(mtimes) < 2:
        return 0.0
    return max(mtimes) - min(mtimes)


def _warn_doc_mtime_drift(threshold_sec: int = DOC_MTIME_WARN_SEC) -> None:
    gap = _doc_mtime_gap_seconds()
    if gap <= threshold_sec:
        return
    print(
        "doc-sync warning: docs modified-time drift detected "
        f"(gap={int(gap)}s, threshold={threshold_sec}s). "
        "check PROJECT_STATUS.md / now_spec.md / DEV_LOG.md alignment."
    )


def recommend_scope() -> str:
    entries = _staged_entries()
    if not entries:
        return "feature"

    paths = [p for entry in entries for p in entry.paths]
    lower_paths = [p.lower() for p in paths]

    if is_artifact_cleanup_only(entries):
        return "cleanup"
    if all(p.startswith("tests/") and p.endswith(".py") for p in lower_paths):
        return "test"
    if all(p.endswith(".md") or p.startswith("docs/") for p in lower_paths):
        return "docs"
    if any(p in CONSTITUTIONAL_FILES for p in paths):
        return "rule"
    if any(p.startswith("tools/") for p in lower_paths):
        return "rule"
    return "feature"


def _load_gate_record() -> dict:
    if not GATE_FILE.exists():
        raise RuntimeError(f"gate record missing: {GATE_FILE}")
    return json.loads(GATE_FILE.read_text(encoding="utf-8"))


def build_template_text(subject: str, record: dict, scope: str) -> str:
    targeted_summary = str(record.get("targeted_summary", "summary unavailable")).strip()
    targeted_line = (
        f"PASS ({targeted_summary})" if bool(record.get("targeted_pass", False))
        else f"FAIL ({targeted_summary})"
    )
    if bool(record.get("full_suite_required", False)):
        full_summary = str(record.get("full_suite_summary", "summary unavailable")).strip()
        full_line = (
            f"PASS ({full_summary})" if bool(record.get("full_suite_pass", False))
            else f"FAIL ({full_summary})"
        )
    else:
        full_line = "not required (no risk trigger)"

    scope_value = scope if scope in ALLOWED_SCOPES else "feature"
    return (
        f"{subject}\n\n"
        f"Scope: {scope_value}\n\n"
        "Summary:\n"
        "- \n\n"
        "Changes:\n"
        "- \n\n"
        "Tests:\n"
        f"- targeted: {targeted_line}\n"
        f"- full suite: {full_line}\n\n"
        "Risks/Follow-up:\n"
        "- none\n"
    )


def parse_args(argv: Sequence[str]) -> tuple[str, str, str, bool, bool]:
    subject = "chore: task finish checkpoint"
    targeted = "auto"
    scope = ""
    confirm_doc_sync = False
    run_audit = False
    items = list(argv)

    if "--scope" in items:
        sidx = items.index("--scope")
        if sidx + 1 >= len(items):
            raise ValueError("--scope requires value")
        scope = items[sidx + 1].strip().lower()

    if "--targeted" in items:
        tidx = items.index("--targeted")
        remain = items[tidx + 1 :]
        for stop_opt in ("--scope", "--subject"):
            if stop_opt in remain:
                remain = remain[: remain.index(stop_opt)]
        if not remain:
            raise ValueError("--targeted requires value")
        if len(remain) == 1 and remain[0].lower() == "auto":
            targeted = "auto"
        else:
            targeted = " ".join(remain)

    if "--confirm-doc-sync" in items:
        confirm_doc_sync = True
    if "--run-audit" in items:
        run_audit = True

    i = 0
    while i < len(items):
        tok = items[i]
        if tok == "--subject":
            if i + 1 >= len(items):
                raise ValueError("--subject requires value")
            subject = items[i + 1]
            i += 2
            continue
        i += 1
    return subject, targeted, scope, confirm_doc_sync, run_audit


def main(argv: Sequence[str] | None = None) -> int:
    items = list(argv) if argv is not None else sys.argv[1:]
    try:
        subject, targeted_cmd, scope_arg, confirm_doc_sync, run_audit = parse_args(items)
    except ValueError as exc:
        print(str(exc))
        return 2

    preflight_rc = run_preflight()
    if preflight_rc != 0:
        return preflight_rc

    if not _staged_exists():
        print("no staged changes; stage files before task_finish")
        return 1

    staged_paths = _staged_paths()
    if not _confirm_doc_sync(staged_paths, confirmed_flag=confirm_doc_sync):
        return 1
    _warn_doc_mtime_drift()

    rc = run_gate(targeted_cmd)
    if rc != 0:
        print("post-task gate failed")
        return rc

    record = _load_gate_record()
    suggested_scope = scope_arg if scope_arg in ALLOWED_SCOPES else recommend_scope()
    template = build_template_text(subject, record, suggested_scope)
    TEMPLATE_PATH.write_text(template, encoding="utf-8")
    print(f"commit template written: {TEMPLATE_PATH}")
    print(f"scope suggestion: {suggested_scope} (allowed: {'|'.join(ALLOWED_SCOPES)})")
    print("현재 프로젝트 자산 상태를 확인하려면 `python tools/project_audit.py`를 실행하세요")
    if run_audit:
        audit_rc = subprocess.call([sys.executable, "tools/project_audit.py"])
        if audit_rc != 0:
            print(f"project audit failed with exit code {audit_rc}")
            return audit_rc
        print("project audit: PASS")
    print(f"next: git commit -F {TEMPLATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

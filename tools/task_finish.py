from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

try:
    from tools.post_task_gate import GATE_FILE
    from tools.post_task_gate import run_gate
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from post_task_gate import GATE_FILE
    from post_task_gate import run_gate

TEMPLATE_PATH = Path(".git") / "TASK_COMMIT_TEMPLATE.md"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _staged_exists() -> bool:
    out = _git("diff", "--cached", "--name-only")
    return bool(out.strip())


def _load_gate_record() -> dict:
    if not GATE_FILE.exists():
        raise RuntimeError(f"gate record missing: {GATE_FILE}")
    return json.loads(GATE_FILE.read_text(encoding="utf-8"))


def build_template_text(subject: str, record: dict) -> str:
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

    return (
        f"{subject}\n\n"
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


def parse_args(argv: Sequence[str]) -> tuple[str, str]:
    subject = "chore: task finish checkpoint"
    targeted = "auto"
    items = list(argv)
    i = 0
    while i < len(items):
        tok = items[i]
        if tok == "--subject":
            if i + 1 >= len(items):
                raise ValueError("--subject requires value")
            subject = items[i + 1]
            i += 2
            continue
        if tok == "--targeted":
            remain = items[i + 1 :]
            if not remain:
                raise ValueError("--targeted requires value")
            if len(remain) == 1 and remain[0].lower() == "auto":
                targeted = "auto"
            else:
                targeted = " ".join(remain)
            break
        i += 1
    return subject, targeted


def main(argv: Sequence[str] | None = None) -> int:
    items = list(argv) if argv is not None else sys.argv[1:]
    try:
        subject, targeted_cmd = parse_args(items)
    except ValueError as exc:
        print(str(exc))
        return 2

    if not _staged_exists():
        print("no staged changes; stage files before task_finish")
        return 1

    rc = run_gate(targeted_cmd)
    if rc != 0:
        print("post-task gate failed")
        return rc

    record = _load_gate_record()
    template = build_template_text(subject, record)
    TEMPLATE_PATH.write_text(template, encoding="utf-8")
    print(f"commit template written: {TEMPLATE_PATH}")
    print(f"next: git commit -F {TEMPLATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


TOOL_FILES = (
    "task_start_guard.py",
    "task_finish.py",
    "test_selector.py",
    "preflight_env.py",
    "post_task_gate.py",
    "git_hook_guards.py",
    "ci_governance_guard.py",
    "install_git_hooks.py",
    "run_multi_role_ai.py",
    "check_tool_integrity.py",
    "generate_context_snapshot.py",
    "dependency_graph_gen.py",
    "context_compressor.py",
    "generate_session_brief.py",
    "transplant_full_system.py",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            chunk = fp.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _is_wrapper(text: str, tool_name: str) -> bool:
    norm = text.replace("\\", "/").lower()
    wrapper_targets = ("dx_operating_pack" in norm) or (
        "dk_system" in norm and "tools" in norm
    )
    return (
        "importlib.util.spec_from_file_location" in norm
        and wrapper_targets
        and tool_name.lower() in norm
    )


def check_integrity(project_root: Path) -> tuple[int, list[str]]:
    logs: list[str] = []
    issues = 0
    for tool_name in TOOL_FILES:
        root_tool = project_root / "tools" / tool_name
        dx_tool = project_root / "dx_operating_pack" / "tools" / tool_name

        if not dx_tool.exists():
            issues += 1
            logs.append(f"[fail] missing dx tool: {dx_tool}")
            continue
        if not root_tool.exists():
            issues += 1
            logs.append(f"[fail] missing root tool: {root_tool}")
            continue

        root_hash = _sha256(root_tool)
        dx_hash = _sha256(dx_tool)
        if root_hash == dx_hash:
            logs.append(f"[ok] {tool_name}: exact-match copy ({root_hash[:12]})")
            continue

        root_text = root_tool.read_text(encoding="utf-8", errors="ignore")
        if _is_wrapper(root_text, tool_name):
            logs.append(
                f"[ok] {tool_name}: wrapper delegation detected "
                f"(root={root_hash[:12]}, dx={dx_hash[:12]})"
            )
            continue

        issues += 1
        logs.append(
            f"[warn] {tool_name}: hash mismatch and wrapper not detected "
            f"(root={root_hash[:12]}, dx={dx_hash[:12]})"
        )
    return issues, logs


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify root tools delegate to dx_operating_pack/tools.")
    parser.add_argument("--project-root", default=".", help="Project root path")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on any integrity issue")
    parser.add_argument("--quiet-ok", action="store_true", help="Hide [ok] lines")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    issues, logs = check_integrity(root)
    for line in logs:
        if args.quiet_ok and line.startswith("[ok]"):
            continue
        print(line)
    if issues:
        print(f"[summary] integrity issues={issues}")
    else:
        print("[summary] tool integrity clean")
    return 1 if (issues and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())

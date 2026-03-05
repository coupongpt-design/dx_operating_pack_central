from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_ITEMS: tuple[tuple[str, str], ...] = (
    ("dx_operating_pack", "dx_operating_pack"),
    ("dx_operating_pack/hooks", ".githooks"),
    ("tools", "tools"),
    ("AGENTS.md", "AGENTS.md"),
    (".cursorrules", ".cursorrules"),
    ("docs_for_ai", "docs_for_ai"),
    ("pytest.ini", "pytest.ini"),
    ("requirements-dev.txt", "requirements-dev.txt"),
    ("macro/run_health_check.py", "macro/run_health_check.py"),
)

PROJECT_STATE_ITEMS: tuple[tuple[str, str], ...] = (
    ("DEV_LOG.md", "DEV_LOG.md"),
    ("PROJECT_STATUS.md", "PROJECT_STATUS.md"),
    ("now_spec.md", "now_spec.md"),
)

STATE_TEMPLATE_MAP: tuple[tuple[str, str], ...] = (
    ("dx_operating_pack/templates/DEV_LOG.template.md", "DEV_LOG.md"),
    ("dx_operating_pack/templates/PROJECT_STATUS.template.md", "PROJECT_STATUS.md"),
    ("dx_operating_pack/templates/now_spec.template.md", "now_spec.md"),
)

STATE_FALLBACK_TEXT: dict[str, str] = {
    "DEV_LOG.md": "# DEV LOG\n\n- bootstrap: transplanted DX operating system.\n",
    "PROJECT_STATUS.md": "# PROJECT STATUS\n\n## Current Focus\n- bootstrap session\n",
    "now_spec.md": "# now_spec\n\n- bootstrap session\n",
}

GOVERNANCE_BRIDGES: tuple[tuple[str, str], ...] = (
    ("tests/test_rule_docs_sync.py", "dx_operating_pack.tests.test_rule_docs_sync"),
    (
        "tests/test_rule_guard_steps_mutation.py",
        "dx_operating_pack.tests.test_rule_guard_steps_mutation",
    ),
    ("tests/test_git_hook_guards.py", "dx_operating_pack.tests.test_git_hook_guards"),
    ("tests/test_test_selector.py", "dx_operating_pack.tests.test_test_selector"),
    ("tests/test_task_finish.py", "dx_operating_pack.tests.test_task_finish"),
    ("tests/test_post_task_gate.py", "dx_operating_pack.tests.test_post_task_gate"),
    ("tests/test_ci_governance_guard.py", "dx_operating_pack.tests.test_ci_governance_guard"),
)

HOOK_FILES: tuple[str, ...] = (
    ".githooks/pre-commit",
    ".githooks/commit-msg",
    ".githooks/pre-push",
)

SYNC_BLOCK_START = "<!-- SYNC_BLOCK_START -->"
SYNC_BLOCK_END = "<!-- SYNC_BLOCK_END -->"


def _safe_remove(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _copy_path(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def _archive_path(target_root: Path, path: Path, archive_stamp: str, *, dry_run: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    try:
        rel = path.relative_to(target_root)
    except ValueError:
        rel = Path(path.name)
    base = target_root / "archive" / "legacy_rules" / archive_stamp / rel
    candidate = base
    idx = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}.bak{idx}")
        idx += 1
    if dry_run:
        print(f"[dry-run] archive: {rel} -> {candidate.relative_to(target_root)}")
        return
    candidate.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(candidate))
    print(f"[archive] {rel} -> {candidate.relative_to(target_root)}")


def _backup_existing(target_root: Path, dst: Path, backup_root: Path) -> None:
    rel = dst.relative_to(target_root)
    backup_dst = backup_root / rel
    backup_dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_dir() and not dst.is_symlink():
        shutil.copytree(dst, backup_dst)
    else:
        shutil.copy2(dst, backup_dst)


def _run_check_tool_integrity(target_root: Path) -> tuple[int, str]:
    tool = target_root / "tools" / "check_tool_integrity.py"
    if not tool.exists():
        return 1, f"[fail] missing verify tool: {tool}"

    completed = subprocess.run(
        [sys.executable, str(tool), "--project-root", str(target_root), "--strict"],
        cwd=str(target_root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode, output


def _resolve_items(include_project_state: bool) -> list[tuple[str, str]]:
    items = list(BASE_ITEMS)
    if include_project_state:
        items.extend(PROJECT_STATE_ITEMS)
    return items


def _write_text(path: Path, text: str, *, dry_run: bool, label: str) -> None:
    if dry_run:
        print(f"[dry-run] write: {label} -> {path.as_posix()}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"[ok] write: {label} -> {path.as_posix()}")


def _extract_sync_block_from_text(text: str) -> str | None:
    start = text.find(SYNC_BLOCK_START)
    end = text.find(SYNC_BLOCK_END)
    if start == -1 or end == -1 or end < start:
        return None
    end += len(SYNC_BLOCK_END)
    return text[start:end].strip()


def _replace_sync_block(text: str, new_block: str) -> str:
    start = text.find(SYNC_BLOCK_START)
    end = text.find(SYNC_BLOCK_END)
    if start == -1 or end == -1 or end < start:
        tail = "" if text.endswith("\n") else "\n"
        return f"{text}{tail}\n{new_block}\n"
    end += len(SYNC_BLOCK_END)
    return f"{text[:start]}{new_block}{text[end:]}"


def _ensure_governance_bridges(target_root: Path, *, archive_stamp: str, dry_run: bool) -> list[str]:
    errors: list[str] = []
    for dst_rel, module in GOVERNANCE_BRIDGES:
        test_name = Path(dst_rel).name
        dx_test = target_root / "dx_operating_pack" / "tests" / test_name
        if not dx_test.exists():
            errors.append(f"missing dx governance test: {dx_test}")
    if errors:
        return errors

    for dst_rel, module in GOVERNANCE_BRIDGES:
        dst = target_root / dst_rel
        content = (
            "from __future__ import annotations\n\n"
            f"from {module} import *  # noqa: F401,F403\n"
        )
        if dst.exists():
            current = dst.read_text(encoding="utf-8", errors="ignore")
            if current == content:
                print(f"[ok] governance bridge already synced: {dst_rel}")
                continue
            _archive_path(target_root, dst, archive_stamp, dry_run=dry_run)
        _write_text(dst, content, dry_run=dry_run, label=f"governance bridge {dst_rel}")
    return errors


def _bootstrap_state_docs(target_root: Path, *, dry_run: bool) -> None:
    for template_rel, dst_rel in STATE_TEMPLATE_MAP:
        dst = target_root / dst_rel
        if dst.exists():
            continue
        template_path = target_root / template_rel
        if template_path.exists():
            if dry_run:
                print(f"[dry-run] bootstrap state doc: {template_rel} -> {dst_rel}")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template_path, dst)
            print(f"[ok] bootstrap state doc: {template_rel} -> {dst_rel}")
            continue
        fallback = STATE_FALLBACK_TEXT.get(dst_rel, f"# {dst_rel}\n")
        _write_text(dst, fallback, dry_run=dry_run, label=f"fallback state doc {dst_rel}")


def _normalize_rule_files(target_root: Path, *, archive_stamp: str, dry_run: bool) -> list[str]:
    errors: list[str] = []
    root_agents = target_root / "AGENTS.md"
    if not root_agents.exists():
        errors.append(f"missing AGENTS.md for bridge creation: {root_agents}")
        return errors

    agents_text = root_agents.read_text(encoding="utf-8", errors="ignore")
    agents_sync_block = _extract_sync_block_from_text(agents_text)

    root_cursorrules = target_root / ".cursorrules"
    if not root_cursorrules.exists():
        fallback = target_root / "dx_operating_pack" / "rules" / ".cursorrules"
        if fallback.exists():
            _write_text(
                root_cursorrules,
                fallback.read_text(encoding="utf-8", errors="ignore"),
                dry_run=dry_run,
                label=".cursorrules bootstrap",
            )
        else:
            errors.append(f"missing .cursorrules and fallback canonical file: {fallback}")
            return errors

    cursor_text = root_cursorrules.read_text(encoding="utf-8", errors="ignore")
    if agents_sync_block is not None:
        cursor_sync_block = _extract_sync_block_from_text(cursor_text)
        if cursor_sync_block != agents_sync_block:
            normalized = _replace_sync_block(cursor_text, agents_sync_block)
            _archive_path(target_root, root_cursorrules, archive_stamp, dry_run=dry_run)
            _write_text(
                root_cursorrules,
                normalized,
                dry_run=dry_run,
                label=".cursorrules sync-block normalize",
            )
        else:
            print("[ok] .cursorrules sync block already aligned")
    else:
        print("[warn] AGENTS.md sync block missing; .cursorrules sync-block normalization skipped")

    legacy_rule_md = target_root / "rule.md"
    if legacy_rule_md.exists():
        _archive_path(target_root, legacy_rule_md, archive_stamp, dry_run=dry_run)

    bridge_dst = target_root / "rules" / "AGENTS.md"
    bridge_text = agents_text
    if bridge_dst.exists():
        existing = bridge_dst.read_text(encoding="utf-8", errors="ignore")
        if existing != bridge_text:
            _archive_path(target_root, bridge_dst, archive_stamp, dry_run=dry_run)
            _write_text(bridge_dst, bridge_text, dry_run=dry_run, label="rules/AGENTS.md bridge")
        else:
            print("[ok] rules/AGENTS.md bridge already synced")
    else:
        _write_text(bridge_dst, bridge_text, dry_run=dry_run, label="rules/AGENTS.md bridge")

    return errors


def _run_doctor(target_root: Path) -> tuple[int, list[str]]:
    required = [
        Path("AGENTS.md"),
        Path(".cursorrules"),
        Path("rules/AGENTS.md"),
        Path("DEV_LOG.md"),
        Path("PROJECT_STATUS.md"),
        Path("now_spec.md"),
        Path("tests"),
    ]
    required.extend(Path(p) for p in HOOK_FILES)
    required.extend(Path(rel) for rel, _ in GOVERNANCE_BRIDGES)

    errors: list[str] = []
    logs: list[str] = []
    for rel in required:
        path = target_root / rel
        if not path.exists():
            errors.append(f"[doctor-fail] missing required path: {rel.as_posix()}")
        else:
            logs.append(f"[doctor-ok] {rel.as_posix()}")

    pre_push = target_root / ".githooks" / "pre-push"
    if pre_push.exists():
        text = pre_push.read_text(encoding="utf-8", errors="ignore")
        referenced = sorted(
            {
                token.strip()
                for token in text.replace("\r", " ").replace("\n", " ").split()
                if token.startswith("tests/") and token.endswith(".py")
            }
        )
        for expected, _ in GOVERNANCE_BRIDGES:
            if expected not in referenced:
                errors.append(f"[doctor-fail] pre-push missing governance test ref: {expected}")
        for rel in referenced:
            if not (target_root / rel).exists():
                errors.append(f"[doctor-fail] pre-push references missing test: {rel}")
    else:
        errors.append("[doctor-fail] missing pre-push hook")

    agents = target_root / "AGENTS.md"
    root_cur = target_root / ".cursorrules"
    if agents.exists() and root_cur.exists():
        agents_block = _extract_sync_block_from_text(agents.read_text(encoding="utf-8", errors="ignore"))
        cursor_block = _extract_sync_block_from_text(root_cur.read_text(encoding="utf-8", errors="ignore"))
        if agents_block is None:
            errors.append("[doctor-fail] AGENTS.md missing sync block markers")
        elif cursor_block is None:
            errors.append("[doctor-fail] .cursorrules missing sync block markers")
        elif agents_block != cursor_block:
            errors.append("[doctor-fail] .cursorrules sync block mismatch vs AGENTS.md")
        else:
            logs.append("[doctor-ok] .cursorrules sync")

    if (target_root / "rule.md").exists():
        errors.append("[doctor-fail] legacy rule.md still present (must be archived)")

    logs.extend(errors)
    return (1 if errors else 0), logs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy full DX operating assets from source project to target project."
    )
    parser.add_argument(
        "--target-root",
        required=True,
        help="Destination project root to receive transplanted assets.",
    )
    parser.add_argument(
        "--source-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Source project root (default: current repository root).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files/directories in target.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without changing files.",
    )
    parser.add_argument(
        "--include-project-state",
        action="store_true",
        help="Also copy DEV_LOG.md / PROJECT_STATUS.md / now_spec.md.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-copy check_tool_integrity verification.",
    )
    parser.add_argument(
        "--skip-bootstrap-state",
        action="store_true",
        help="Skip state-doc bootstrap from dx templates when files are missing.",
    )
    parser.add_argument(
        "--skip-governance-bridge",
        action="store_true",
        help="Skip creating root governance test bridge files under tests/.",
    )
    parser.add_argument(
        "--skip-rule-normalization",
        action="store_true",
        help="Skip .cursorrules normalization and rules/AGENTS.md bridge sync.",
    )
    parser.add_argument(
        "--skip-doctor",
        action="store_true",
        help="Skip post-transplant structural doctor checks.",
    )
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    target_root = Path(args.target_root).resolve()
    items = _resolve_items(include_project_state=args.include_project_state)
    archive_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not source_root.exists():
        print(f"[fail] source root not found: {source_root}")
        return 1
    target_root.mkdir(parents=True, exist_ok=True)

    missing_sources: list[str] = []
    for src_rel, _ in items:
        src = source_root / src_rel
        if not src.exists():
            missing_sources.append(str(src))
    if missing_sources:
        print("[fail] missing source assets:")
        for path in missing_sources:
            print(f"       - {path}")
        return 1

    existing_targets: list[Path] = []
    for _, dst_rel in items:
        dst = target_root / dst_rel
        if dst.exists() or dst.is_symlink():
            existing_targets.append(dst)

    backup_root: Path | None = None
    if args.overwrite and existing_targets and not args.dry_run:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = target_root / ".dx_cache" / "transplant_backup" / stamp
        backup_root.mkdir(parents=True, exist_ok=True)
        print(f"[ok] backup root prepared: {backup_root}")

    for src_rel, dst_rel in items:
        src = source_root / src_rel
        dst = target_root / dst_rel

        if dst.exists() or dst.is_symlink():
            if not args.overwrite:
                print(f"[skip] {dst_rel} already exists (use --overwrite)")
                continue
            if args.dry_run:
                print(f"[dry-run] overwrite: {dst_rel}")
                continue
            if backup_root is not None:
                _backup_existing(target_root=target_root, dst=dst, backup_root=backup_root)
                print(f"[backup] {dst_rel}")
            _safe_remove(dst)

        if args.dry_run:
            print(f"[dry-run] copy: {src_rel} -> {dst_rel}")
            continue

        _copy_path(src=src, dst=dst)
        print(f"[ok] copy: {src_rel} -> {dst_rel}")

    if args.dry_run:
        print("[done] dry-run finished")
        return 0

    if not args.skip_bootstrap_state:
        _bootstrap_state_docs(target_root=target_root, dry_run=False)

    if not args.skip_governance_bridge:
        bridge_errors = _ensure_governance_bridges(
            target_root=target_root,
            archive_stamp=archive_stamp,
            dry_run=False,
        )
        if bridge_errors:
            for line in bridge_errors:
                print(f"[fail] {line}")
            return 1

    if not args.skip_rule_normalization:
        rule_errors = _normalize_rule_files(
            target_root=target_root,
            archive_stamp=archive_stamp,
            dry_run=False,
        )
        if rule_errors:
            for line in rule_errors:
                print(f"[fail] {line}")
            return 1

    if not args.skip_doctor:
        doctor_rc, doctor_logs = _run_doctor(target_root=target_root)
        for line in doctor_logs:
            print(line)
        if doctor_rc != 0:
            print("[fail] transplant doctor detected blocking issues")
            return doctor_rc

    if not args.skip_verify:
        rc, out = _run_check_tool_integrity(target_root=target_root)
        if out:
            print(out)
        if rc != 0:
            print("[fail] post-copy integrity check failed")
            return rc
        print("[ok] post-copy integrity check passed")

    print(f"[done] full transplant complete -> {target_root}")
    print("[next] run in target project:")
    print("       python tools/install_git_hooks.py")
    print("       python tools/task_start_guard.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
from pathlib import Path


# (source_rel, target_rel) mapping inside/new project root.
INSTALL_MAP: list[tuple[str, str]] = [
    ("rules/AGENTS.md", "AGENTS.md"),
    ("rules/.cursorrules", ".cursorrules"),
    ("hooks", ".githooks"),
    ("tools", "tools"),
    ("ci", ".github/workflows"),
    ("tests", "tests"),
    ("docs", "docs/dx_pack"),
    ("docs_for_ai", "docs_for_ai"),
    ("prompt_recipes", "PROMPT_RECIPES"),
    (".cursor/prompts", ".cursor/prompts"),
    ("COMPLIANCE_GUIDE.md", "COMPLIANCE_GUIDE.md"),
]

HOOK_FILENAMES = ("pre-commit", "commit-msg", "pre-push")


def _safe_remove(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _copy_or_link(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        if src.is_dir():
            dst.symlink_to(src, target_is_directory=True)
        else:
            dst.symlink_to(src)
        return

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


def _resolve_remote_cache_dir(target_root: Path, raw: str) -> Path:
    cache = Path(raw)
    return cache if cache.is_absolute() else (target_root / cache)


def _git_env_check(target_root: Path) -> tuple[bool, list[str]]:
    logs: list[str] = []
    if not target_root.exists():
        logs.append(f"[fail] target root does not exist: {target_root}")
        return False, logs

    rc, out = _run(["git", "--version"])
    if rc != 0:
        logs.append("[fail] Git prerequisite not satisfied: git command not found.")
        logs.append("[guide] Install Git, reopen shell, then retry.")
        logs.append("[guide] Download: https://git-scm.com/downloads")
        logs.append(f"[detail] {out}")
        return False, logs
    logs.append(f"[ok] {out.splitlines()[0] if out else 'git available'}")

    rc, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=target_root)
    if rc != 0:
        logs.append("[fail] target project is not a git repository.")
        logs.append("[guide] Run the following first, then rerun setup:")
        logs.append(f"        cd {target_root}")
        logs.append("        git init")
        return False, logs
    logs.append("[ok] git repository detected in target root")
    return True, logs


def _auth_help_lines() -> list[str]:
    return [
        "[troubleshooting] Private repository authentication is required.",
        "[troubleshooting] Use one of the following:",
        "       - SSH: add your public key to remote provider and use git@... URL",
        "       - HTTPS+PAT: create token and configure credential manager",
        "       - Verify access manually: git ls-remote <repo-url>",
    ]


def _acquire_remote_pack(remote: str, cache_dir: Path) -> tuple[Path | None, list[str]]:
    logs: list[str] = []
    cache_dir = cache_dir.resolve()
    git_dir = cache_dir / ".git"

    if git_dir.exists():
        logs.append(f"[info] remote cache exists: {cache_dir}")
        _run(["git", "-C", str(cache_dir), "remote", "set-url", "origin", remote])
        rc, out = _run(["git", "-C", str(cache_dir), "pull", "--ff-only"])
        if rc != 0:
            logs.append(f"[fail] remote pull failed (exit={rc}): {out}")
            logs.extend(_auth_help_lines())
            return None, logs
        logs.append("[ok] remote cache updated (pull --ff-only)")
        return cache_dir, logs

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    rc, out = _run(["git", "clone", remote, str(cache_dir)])
    if rc != 0:
        logs.append(f"[fail] remote clone failed (exit={rc}): {out}")
        logs.extend(_auth_help_lines())
        return None, logs
    logs.append(f"[ok] remote cloned: {remote} -> {cache_dir}")
    return cache_dir, logs


def _ensure_hook_executable(target_root: Path, installed: list[str]) -> None:
    """Best-effort chmod +x for git hooks on POSIX-like environments."""
    hook_dir = target_root / ".githooks"
    if not hook_dir.exists():
        return

    for name in HOOK_FILENAMES:
        hook_path = hook_dir / name
        if not hook_path.exists() or not hook_path.is_file():
            continue
        try:
            current = hook_path.stat().st_mode
            desired = current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            if desired != current:
                hook_path.chmod(desired)
                installed.append(f"[ok] chmod +x {hook_path.relative_to(target_root)}")
            else:
                installed.append(f"[ok] hook exec already set: {hook_path.relative_to(target_root)}")
        except Exception as exc:
            installed.append(f"[warn] hook chmod skipped: {hook_path.name} ({exc})")


def install(pack_root: Path, target_root: Path, mode: str, overwrite: bool) -> list[str]:
    installed: list[str] = []
    for src_rel, dst_rel in INSTALL_MAP:
        src = pack_root / src_rel
        dst = target_root / dst_rel
        if not src.exists():
            continue

        if dst.exists() or dst.is_symlink():
            if not overwrite:
                installed.append(f"[skip] {dst_rel} (exists)")
                continue
            _safe_remove(dst)

        _copy_or_link(src=src, dst=dst, mode=mode)
        installed.append(f"[ok] {src_rel} -> {dst_rel}")
    _ensure_hook_executable(target_root=target_root, installed=installed)
    return installed


def main() -> int:
    parser = argparse.ArgumentParser(description="Install DX operating pack into another project.")
    parser.add_argument(
        "--pack-root",
        default="dx_operating_pack",
        help="Path to dx_operating_pack root.",
    )
    parser.add_argument(
        "--remote",
        default="",
        help="Remote git URL/path for central dx pack. If set, clone/pull from remote first.",
    )
    parser.add_argument(
        "--remote-cache-dir",
        default=".dx_cache/dx_operating_pack_remote",
        help="Local cache directory for remote dx pack clone/pull.",
    )
    parser.add_argument(
        "--target-root",
        default=".",
        help="Path to destination project root.",
    )
    parser.add_argument(
        "--mode",
        choices=("copy", "symlink"),
        default="copy",
        help="Install mode: copy files or create symlinks.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing target files/directories.",
    )
    args = parser.parse_args()

    target_root = Path(args.target_root).resolve()
    pack_root: Path
    logs: list[str] = []

    ok, env_logs = _git_env_check(target_root=target_root)
    logs.extend(env_logs)
    if not ok:
        for line in logs:
            print(line)
        return 1

    if args.remote.strip():
        cache_dir = _resolve_remote_cache_dir(target_root=target_root, raw=args.remote_cache_dir)
        remote_root, remote_logs = _acquire_remote_pack(remote=args.remote.strip(), cache_dir=cache_dir)
        logs.extend(remote_logs)
        if not remote_root:
            for line in logs:
                print(line)
            return 1
        pack_root = remote_root
    else:
        pack_root = Path(args.pack_root).resolve()
        if not pack_root.exists():
            print(f"[fail] pack root not found: {pack_root}")
            return 1

    logs.extend(install(pack_root=pack_root, target_root=target_root, mode=args.mode, overwrite=args.overwrite))
    print(f"[done] mode={args.mode}, overwrite={args.overwrite}, target={target_root}")
    for line in logs:
        print(line)
    print("[next] run: python tools/install_git_hooks.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

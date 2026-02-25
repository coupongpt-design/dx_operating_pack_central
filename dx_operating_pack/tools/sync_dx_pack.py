from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

PROTECTED_FILE_PATTERNS = (
    "**/*.local.*",
    "DEV_LOG.md",
    "PROJECT_STATUS.md",
    "now_spec.md",
)


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"[cmd] {' '.join(cmd)} (cwd={cwd or Path.cwd()})")
    completed = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
    return completed.returncode


def _auth_help_lines() -> list[str]:
    return [
        "[hint] Private repository may require authentication.",
        "[hint] Configure SSH key or HTTPS PAT credentials.",
        "[hint] Quick check: git ls-remote <repo-url>",
    ]


def _git_env_check(project_root: Path) -> bool:
    rc = _run(["git", "--version"])
    if rc != 0:
        print("[fail] git not found. Install Git and retry.")
        return False
    rc = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_root)
    if rc != 0:
        print("[fail] target project is not git-initialized. Run `git init` first.")
        return False
    return True


def _backup_current_pack(project_root: Path) -> None:
    src = project_root / "dx_operating_pack"
    if not src.exists():
        print("[info] no local dx_operating_pack folder found; backup skipped")
        return

    backup = project_root / "dx_operating_pack_bak"
    if backup.exists():
        if backup.is_dir():
            shutil.rmtree(backup)
        else:
            backup.unlink()
    shutil.copytree(src, backup)
    print(f"[ok] backup created: {backup}")


def _collect_protected_files(project_root: Path) -> list[Path]:
    protected: set[Path] = set()
    for pattern in PROTECTED_FILE_PATTERNS:
        for match in project_root.glob(pattern):
            if match.is_file():
                protected.add(match.resolve())
    return sorted(protected)


def _backup_protected_files(project_root: Path, files: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = (project_root / ".dx_cache" / "protected_backup" / stamp).resolve()
    for file in files:
        rel = file.relative_to(project_root.resolve())
        dst = backup_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dst)
    return backup_root


def _restore_protected_files(project_root: Path, backup_root: Path) -> None:
    if not backup_root.exists():
        return
    for file in backup_root.rglob("*"):
        if not file.is_file():
            continue
        rel = file.relative_to(backup_root)
        dst = project_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dst)
    print(f"[ok] protected local files restored from: {backup_root}")


def _acquire_remote(remote_url: str, cache_dir: Path) -> Path | None:
    git_dir = cache_dir / ".git"
    if git_dir.exists():
        _run(["git", "-C", str(cache_dir), "remote", "set-url", "origin", remote_url])
        rc = _run(["git", "-C", str(cache_dir), "pull", "--ff-only"])
        if rc != 0:
            print("[fail] remote pull failed")
            for line in _auth_help_lines():
                print(line)
            return None
        return cache_dir

    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    rc = _run(["git", "clone", remote_url, str(cache_dir)])
    if rc != 0:
        print("[fail] remote clone failed")
        for line in _auth_help_lines():
            print(line)
        return None
    return cache_dir


def _resolve_pack_repo(args: argparse.Namespace, project_root: Path) -> Path | None:
    if args.remote_url:
        cache_dir = Path(args.cache_dir)
        if not cache_dir.is_absolute():
            cache_dir = project_root / cache_dir
        return _acquire_remote(remote_url=args.remote_url, cache_dir=cache_dir.resolve())

    if args.pack_repo:
        pack_repo = Path(args.pack_repo).resolve()
        if not pack_repo.exists():
            print(f"[fail] pack repo not found: {pack_repo}")
            return None
        rc = _run(["git", "pull", "--ff-only"], cwd=pack_repo)
        if rc != 0:
            print("[fail] git pull failed")
            return None
        return pack_repo
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync/update dx pack and apply to target project.")
    parser.add_argument(
        "--remote-url",
        default="",
        help="Central dx pack git URL/path to clone/pull.",
    )
    parser.add_argument(
        "--cache-dir",
        default=".dx_cache/dx_operating_pack_remote",
        help="Local cache dir used when --remote-url is set.",
    )
    parser.add_argument(
        "--pack-repo",
        default="",
        help="Local shared dx-pack git repository path (fallback mode).",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Target project root where setup_dx.py will apply updates.",
    )
    parser.add_argument(
        "--mode",
        choices=("copy", "symlink"),
        default="copy",
        help="Install mode passed to setup_dx.py.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files during sync.",
    )
    args = parser.parse_args()

    if not args.remote_url and not args.pack_repo:
        print("[fail] provide either --remote-url or --pack-repo")
        return 1

    project_root = Path(args.project_root).resolve()
    if not _git_env_check(project_root=project_root):
        return 1

    pack_repo = _resolve_pack_repo(args=args, project_root=project_root)
    if not pack_repo:
        return 1

    setup_script = pack_repo / "tools" / "setup_dx.py"
    if not setup_script.exists():
        print(f"[fail] setup script missing: {setup_script}")
        return 1

    _backup_current_pack(project_root=project_root)
    protected_files = _collect_protected_files(project_root=project_root)
    protected_backup_root = _backup_protected_files(project_root=project_root, files=protected_files)
    if protected_files:
        print(f"[ok] protected files backup created: {len(protected_files)} files")

    cmd = [
        "python",
        str(setup_script),
        "--pack-root",
        str(pack_repo),
        "--target-root",
        str(project_root),
        "--mode",
        args.mode,
    ]
    if args.overwrite:
        cmd.append("--overwrite")
    try:
        rc = _run(cmd, cwd=project_root)
    finally:
        _restore_protected_files(project_root=project_root, backup_root=protected_backup_root)
    if rc == 0:
        print("[ok] sync complete")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

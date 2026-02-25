from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> int:
    print(f"[cmd] {' '.join(cmd)} (cwd={cwd})")
    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync/update dx pack from its source repository.")
    parser.add_argument(
        "--pack-repo",
        required=True,
        help="Path to shared dx-pack git repository.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Target project root where setup_dx.py will be executed.",
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

    pack_repo = Path(args.pack_repo).resolve()
    project_root = Path(args.project_root).resolve()
    if not pack_repo.exists():
        print(f"[fail] pack repo not found: {pack_repo}")
        return 1

    rc = run(["git", "pull", "--ff-only"], cwd=pack_repo)
    if rc != 0:
        print("[fail] git pull failed")
        return rc

    setup_script = pack_repo / "tools" / "setup_dx.py"
    if not setup_script.exists():
        print(f"[fail] setup script missing: {setup_script}")
        return 1

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
    return run(cmd, cwd=project_root)


if __name__ == "__main__":
    raise SystemExit(main())


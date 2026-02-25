from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

REQUIRED_HOOKS = ("commit-msg", "pre-commit")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace").strip()


def _ensure_executable(path: Path) -> None:
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    root = Path(_git("rev-parse", "--show-toplevel"))
    hooks_dir = root / ".githooks"

    missing = [name for name in REQUIRED_HOOKS if not (hooks_dir / name).exists()]
    if missing:
        print(f"missing hook files: {', '.join(missing)}")
        return 1

    subprocess.check_call(["git", "config", "core.hooksPath", ".githooks"], cwd=root)

    for name in REQUIRED_HOOKS:
        _ensure_executable(hooks_dir / name)

    configured = _git("config", "--get", "core.hooksPath")
    print(f"installed hooksPath={configured}")
    print("active hooks:", ", ".join(REQUIRED_HOOKS))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())

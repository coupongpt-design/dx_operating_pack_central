from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from typing import Iterable

PATTERNS = (
    "__pycache__/*",
    "**/__pycache__/*",
    "*.pyc",
    "logs/*.jsonl",
)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def _tracked_files() -> list[str]:
    out = _git("ls-files")
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def _match(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in PATTERNS)


def find_tracked_artifacts() -> list[str]:
    return [path for path in _tracked_files() if _match(path)]


def run_cleanup(apply: bool) -> int:
    hits = find_tracked_artifacts()
    if not hits:
        print("no tracked artifacts found")
        return 0

    print(f"tracked artifacts: {len(hits)}")
    for path in hits:
        print(path)

    if not apply:
        print("dry-run only. use --apply to run git rm --cached.")
        return 0

    subprocess.check_call(["git", "rm", "--cached", "--", *hits])
    print("removed from index (working files kept).")
    return 0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove tracked build/runtime artifacts from Git index.")
    parser.add_argument("--apply", action="store_true", help="apply git rm --cached")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return run_cleanup(args.apply)


if __name__ == "__main__":
    raise SystemExit(main())

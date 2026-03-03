from __future__ import annotations

import argparse
import re
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)-----BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY-----"),
    re.compile(r"(?i)xox[baprs]-[0-9A-Za-z-]{10,}"),  # Slack-like tokens
]

TEXT_EXTS = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".ini", ".env", ".toml"}
DEFAULT_EXCLUDES = {".git", "__pycache__", "build", "dist", ".pytest_cache", "logs"}


def _is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTS or path.name.lower().startswith(".env")


def scan(root: Path, extra_excludes: set[str]) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    exclude_dirs = DEFAULT_EXCLUDES | extra_excludes

    for file in root.rglob("*"):
        if not file.is_file():
            continue
        parts = set(file.parts)
        if parts & exclude_dirs:
            continue
        if not _is_text_candidate(file):
            continue

        try:
            lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append((file, idx, line.strip()))
                    break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan repository for obvious secret leaks.")
    parser.add_argument("--root", default=".", help="Project root path.")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional directory names to exclude (can repeat).",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings = scan(root=root, extra_excludes=set(args.exclude))
    if not findings:
        print("[ok] no obvious secret patterns detected")
        return 0

    print("[fail] potential secrets detected:")
    for file, line_no, line in findings:
        rel = file.relative_to(root)
        print(f"  - {rel}:{line_no}: {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


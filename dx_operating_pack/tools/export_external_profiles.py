from __future__ import annotations

import argparse
import re
from pathlib import Path


MASK_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*:\s*)(.+)$"),
    re.compile(r"(?i)(token\s*:\s*)(.+)$"),
    re.compile(r"(?i)(password\s*:\s*)(.+)$"),
]


def mask_line(line: str) -> str:
    for pattern in MASK_PATTERNS:
        m = pattern.search(line)
        if m:
            return f"{m.group(1)}<REDACTED>"
    return line


def export_continue_config(src: Path, dst_raw: Path, dst_masked: Path) -> None:
    if not src.exists():
        print(f"[skip] missing source: {src}")
        return
    dst_raw.parent.mkdir(parents=True, exist_ok=True)
    raw = src.read_text(encoding="utf-8", errors="ignore")
    dst_raw.write_text(raw, encoding="utf-8")
    masked = "\n".join(mask_line(line) for line in raw.splitlines()) + "\n"
    dst_masked.write_text(masked, encoding="utf-8")
    print(f"[ok] raw backup: {dst_raw}")
    print(f"[ok] masked backup: {dst_masked}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export external profile backups with masked example.")
    parser.add_argument(
        "--continue-config",
        default=str(Path.home() / ".continue" / "config.yaml"),
        help="Path to continue config.yaml",
    )
    parser.add_argument("--out-dir", default="optional/external", help="Output directory")
    args = parser.parse_args()

    src = Path(args.continue_config).expanduser().resolve()
    out_dir = Path(args.out_dir).resolve()
    export_continue_config(
        src=src,
        dst_raw=out_dir / "continue_config.local.yaml",
        dst_masked=out_dir / "continue_config.example.yaml",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


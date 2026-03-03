from __future__ import annotations

import argparse
from pathlib import Path


SCAN_EXTS = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".ini", ".toml"}


def analyze(root: Path, top_n: int) -> str:
    rows: list[tuple[Path, int, int, int]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SCAN_EXTS:
            continue
        if any(part in {".git", "__pycache__", "build", "dist", ".pytest_cache"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.count("\n") + (1 if text else 0)
        size = path.stat().st_size
        est_tokens = max(1, size // 4)
        rows.append((path, lines, size, est_tokens))

    by_lines = sorted(rows, key=lambda r: r[1], reverse=True)[:top_n]
    by_tokens = sorted(rows, key=lambda r: r[3], reverse=True)[:top_n]

    out: list[str] = ["# TOKEN USAGE REPORT", ""]
    out.append("## Top by Line Count")
    for path, lines, size, tokens in by_lines:
        out.append(f"- `{path}` | lines={lines} | bytes={size} | est_tokens={tokens}")
    out.append("")
    out.append("## Top by Estimated Tokens")
    for path, lines, size, tokens in by_tokens:
        out.append(f"- `{path}` | est_tokens={tokens} | lines={lines} | bytes={size}")
    out.append("")
    out.append("## Split Recommendations")
    for path, lines, size, tokens in sorted(rows, key=lambda r: r[1], reverse=True):
        if lines >= 800 or tokens >= 8000:
            out.append(
                f"- `{path}` -> split candidate (lines={lines}, est_tokens={tokens}, bytes={size})"
            )
    if out[-1] == "## Split Recommendations":
        out.append("- no immediate split candidate over threshold")
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze large files that consume LLM context.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument("--top", type=int, default=20, help="Top N files per section.")
    parser.add_argument("--out", default="", help="Optional markdown output path.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = analyze(root=root, top_n=args.top)

    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        print(f"[ok] report written: {out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


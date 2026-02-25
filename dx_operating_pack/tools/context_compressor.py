from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Iterable


def _compress_py(path: Path) -> list[str]:
    lines: list[str] = [f"### {path}", ""]
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except Exception as exc:
        lines.append(f"- parse_error: {exc}")
        lines.append("")
        return lines

    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    funcs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    lines.append(f"- classes({len(classes)}): {', '.join(classes[:12]) or '-'}")
    lines.append(f"- functions({len(funcs)}): {', '.join(funcs[:20]) or '-'}")
    lines.append(f"- imports({len(imports)}): {', '.join(imports[:15]) or '-'}")
    lines.append("")
    return lines


def _compress_md(path: Path) -> list[str]:
    lines: list[str] = [f"### {path}", ""]
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    headings = [line.strip() for line in raw if line.lstrip().startswith("#")]
    bullets = [line.strip() for line in raw if line.lstrip().startswith(("- ", "* "))]
    lines.append(f"- headings({len(headings)}): {', '.join(headings[:12]) or '-'}")
    lines.append(f"- bullets({len(bullets)}): {', '.join(bullets[:12]) or '-'}")
    lines.append("")
    return lines


def compress(files: Iterable[Path]) -> str:
    out: list[str] = ["# COMPRESSED CONTEXT", ""]
    for path in files:
        if not path.exists():
            out.append(f"### {path}")
            out.append("- missing")
            out.append("")
            continue
        if path.suffix == ".py":
            out.extend(_compress_py(path))
        elif path.suffix in (".md", ".txt"):
            out.extend(_compress_md(path))
        else:
            size = path.stat().st_size
            out.append(f"### {path}")
            out.append(f"- type: {path.suffix or 'unknown'}")
            out.append(f"- size: {size} bytes")
            out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compress large project context into LLM-ready summary.")
    parser.add_argument("paths", nargs="+", help="Files to summarize.")
    parser.add_argument("--out", default="", help="Output path. If empty, print to stdout.")
    args = parser.parse_args()

    files = [Path(p) for p in args.paths]
    content = compress(files)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"[ok] written: {out}")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


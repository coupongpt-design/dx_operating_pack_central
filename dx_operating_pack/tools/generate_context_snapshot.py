from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DIRS = ("app/core", "app/ui", "tools", "tests")
SCOPE_DIRS: dict[str, tuple[str, ...]] = {
    "all": DEFAULT_DIRS,
    "core": ("app/core", "tests"),
    "ui": ("app/ui", "app", "tests"),
    "dx": ("tools", ".githooks", ".github", "docs", "docs_for_ai", "prompt_recipes"),
}


def _iter_files(root: Path, rel_dirs: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for rel in rel_dirs:
        target = root / rel
        if not target.exists():
            continue
        files.extend(p for p in target.rglob("*") if p.is_file())
    return sorted(files)


def _extract_api_symbols(py_file: Path) -> tuple[list[str], list[str]]:
    classes: list[str] = []
    functions: list[str] = []
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except Exception:
        return classes, functions

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
    return classes, functions


def generate_snapshot(root: Path, out_file: Path, include_dirs: tuple[str, ...], scope: str) -> None:
    files = _iter_files(root, include_dirs)
    py_files = [p for p in files if p.suffix == ".py"]

    lines: list[str] = []
    lines.append("# CONTEXT SNAPSHOT")
    lines.append("")
    lines.append(f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- project_root: `{root}`")
    lines.append(f"- scope: `{scope}`")
    lines.append(f"- scanned_dirs: `{', '.join(include_dirs)}`")
    lines.append(f"- file_count: {len(files)}")
    lines.append(f"- python_file_count: {len(py_files)}")
    lines.append("")
    lines.append("## Directory Summary")
    for rel in include_dirs:
        target = root / rel
        count = len([p for p in target.rglob("*") if p.is_file()]) if target.exists() else 0
        lines.append(f"- `{rel}`: {count} files")
    lines.append("")
    lines.append("## Key Python Interfaces")

    for py_file in py_files[:120]:
        classes, functions = _extract_api_symbols(py_file)
        if not classes and not functions:
            continue
        rel = py_file.relative_to(root)
        cls_txt = ", ".join(classes[:5]) if classes else "-"
        fn_txt = ", ".join(functions[:8]) if functions else "-"
        lines.append(f"- `{rel}`")
        lines.append(f"  - classes: {cls_txt}")
        lines.append(f"  - functions: {fn_txt}")

    lines.append("")
    lines.append("## Largest Files (By Size)")
    largest = sorted(files, key=lambda p: p.stat().st_size, reverse=True)[:25]
    for p in largest:
        rel = p.relative_to(root)
        lines.append(f"- `{rel}`: {p.stat().st_size} bytes")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an AI-ready context snapshot.")
    parser.add_argument("--root", default=".", help="Project root path.")
    parser.add_argument(
        "--out",
        default="docs_for_ai/CONTEXT_SNAPSHOT.md",
        help="Output markdown path.",
    )
    parser.add_argument(
        "--dirs",
        nargs="*",
        default=list(DEFAULT_DIRS),
        help="Relative directories to scan.",
    )
    parser.add_argument(
        "--scope",
        choices=("all", "core", "ui", "dx"),
        default="all",
        help="Preset directory scope for compact snapshot.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_file = Path(args.out)
    if not out_file.is_absolute():
        out_file = root / out_file

    include_dirs = tuple(args.dirs)
    if args.scope in SCOPE_DIRS and args.scope != "all":
        include_dirs = SCOPE_DIRS[args.scope]
    generate_snapshot(
        root=root,
        out_file=out_file,
        include_dirs=include_dirs,
        scope=args.scope,
    )
    print(f"[ok] snapshot written: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

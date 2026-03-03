from __future__ import annotations

import argparse
import ast
from pathlib import Path


def _module_name(root: Path, py_file: Path) -> str:
    rel = py_file.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def _local_imports(tree: ast.AST) -> set[str]:
    deps: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    deps.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app."):
                deps.add(node.module)
    return deps


def generate(root: Path, out: Path, dot_out: Path | None) -> None:
    app_dir = root / "app"
    py_files = sorted(app_dir.rglob("*.py")) if app_dir.exists() else []

    graph: dict[str, set[str]] = {}
    for py_file in py_files:
        module = _module_name(root, py_file)
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            graph[module] = set()
            continue
        graph[module] = _local_imports(tree)

    md_lines: list[str] = ["# DEPENDENCY GRAPH", ""]
    for module, deps in sorted(graph.items()):
        dep_txt = ", ".join(sorted(deps)) if deps else "-"
        md_lines.append(f"- `{module}` -> {dep_txt}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"[ok] markdown graph: {out}")

    if dot_out:
        dot_lines = ["digraph G {"]
        for module, deps in sorted(graph.items()):
            if not deps:
                dot_lines.append(f'  "{module}";')
                continue
            for dep in sorted(deps):
                dot_lines.append(f'  "{module}" -> "{dep}";')
        dot_lines.append("}")
        dot_out.parent.mkdir(parents=True, exist_ok=True)
        dot_out.write_text("\n".join(dot_lines) + "\n", encoding="utf-8")
        print(f"[ok] dot graph: {dot_out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local module dependency graph.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument(
        "--out",
        default="dx_operating_pack/docs_for_ai/DEPENDENCY_GRAPH.md",
        help="Markdown output path.",
    )
    parser.add_argument("--dot-out", default="", help="Optional Graphviz DOT output path.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    dot_out = None
    if args.dot_out:
        dot_out = Path(args.dot_out)
        if not dot_out.is_absolute():
            dot_out = root / dot_out

    generate(root=root, out=out, dot_out=dot_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


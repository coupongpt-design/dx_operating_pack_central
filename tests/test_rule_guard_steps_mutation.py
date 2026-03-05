from __future__ import annotations

import ast
from pathlib import Path


BANNED_MUTATORS = {
    "append",
    "extend",
    "insert",
    "pop",
    "remove",
    "clear",
    "sort",
    "reverse",
}

ALLOWED_STEPS_REBIND_FUNCTIONS = {
    "__init__",
    "_load_macro_from_path",
}


def _is_self_steps(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == "steps"
    )


class _StepsMutationGuard(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []
        self._fn_stack: list[str] = []

    def _current_fn(self) -> str | None:
        return self._fn_stack[-1] if self._fn_stack else None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._fn_stack.append(node.name)
        self.generic_visit(node)
        self._fn_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._fn_stack.append(node.name)
        self.generic_visit(node)
        self._fn_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr in BANNED_MUTATORS
            and _is_self_steps(fn.value)
        ):
            self.violations.append((node.lineno, f"self.steps.{fn.attr}(...)"))
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if _is_self_steps(node.target):
            self.violations.append((node.lineno, "self.steps <op>= ..."))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if _is_self_steps(target):
                fn = self._current_fn()
                if fn not in ALLOWED_STEPS_REBIND_FUNCTIONS:
                    self.violations.append(
                        (node.lineno, "self.steps = ... (outside allowlist)")
                    )
            if isinstance(target, ast.Subscript) and _is_self_steps(target.value):
                self.violations.append((node.lineno, "self.steps[...] = ..."))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if _is_self_steps(node.target):
            fn = self._current_fn()
            if fn not in ALLOWED_STEPS_REBIND_FUNCTIONS:
                self.violations.append(
                    (node.lineno, "self.steps: ... = ... (outside allowlist)")
                )
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            if isinstance(target, ast.Subscript) and _is_self_steps(target.value):
                self.violations.append((node.lineno, "del self.steps[idx]"))
        self.generic_visit(node)


def _resolve_main_path() -> Path:
    candidates = (
        Path("app/main.py"),
        Path("macro/main_refactored.py"),
        Path("main_refactored.py"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise AssertionError("No main entry file found (expected app/main.py or main_refactored.py)")


def test_mainwindow_steps_do_not_use_direct_mutation() -> None:
    main_path = _resolve_main_path()
    source = main_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(main_path))
    guard = _StepsMutationGuard()
    guard.visit(tree)

    assert not guard.violations, (
        "Direct self.steps mutation detected outside command flow: "
        + ", ".join(f"L{line}:{kind}" for line, kind in guard.violations)
    )

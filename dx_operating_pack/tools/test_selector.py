from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Iterable
from typing import Sequence

RULE_GUARD_TESTS = [
    "tests/test_rule_docs_sync.py",
    "tests/test_rule_guard_steps_mutation.py",
    "tests/test_git_hook_guards.py",
]

MAPPINGS: list[tuple[re.Pattern[str], list[str]]] = [
    (
        re.compile(r"^(AGENTS\.md|\.cursorrules|\.githooks/|tools/(git_hook_guards|post_task_gate|task_finish|ci_governance_guard)\.py)"),
        RULE_GUARD_TESTS,
    ),
    (
        re.compile(r"^tools/test_selector\.py$"),
        ["tests/test_test_selector.py"],
    ),
    (
        re.compile(r"^tools/task_start_guard\.py$"),
        [
            "tests/test_task_start_guard.py",
            "tests/test_git_hook_guards.py",
        ],
    ),
    (
        re.compile(r"^tools/preflight_env\.py$"),
        ["tests/test_preflight_env.py"],
    ),
    (
        re.compile(r"^app/core/(data_orchestration|session_adapter|excel_io)\.py$"),
        [
            "tests/test_data_orchestration_v2.py",
            "tests/test_session_adapter_v2.py",
            "tests/test_excel_io.py",
        ],
    ),
    (
        re.compile(r"^app/core/(recorder|smart_recorder)\.py$"),
        [
            "tests/test_smart_recorder_core.py",
            "tests/test_recording_integration.py",
            "tests/test_ui_integration.py",
        ],
    ),
    (
        re.compile(r"^app/main\.py$|^app/ui/|^app/ui/tabs/"),
        [
            "tests/test_ui_integration.py",
            "tests/test_excel_toolbar_responsive.py",
            "tests/test_coordinate_overlay_mapping.py",
        ],
    ),
]

FALLBACK_TESTS = [
    "tests/test_ui_integration.py",
]


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8", errors="replace")


def staged_paths() -> list[str]:
    out = _git("diff", "--cached", "--name-only")
    paths = [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]
    return paths


def select_tests(paths: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    normalized = [p.replace("\\", "/") for p in paths]

    for path in normalized:
        if path.startswith("tests/") and path.endswith(".py"):
            if path not in seen:
                seen.add(path)
                out.append(path)
            continue
        for pattern, tests in MAPPINGS:
            if pattern.search(path):
                for test in tests:
                    if test not in seen:
                        seen.add(test)
                        out.append(test)

    if not out:
        for test in FALLBACK_TESTS:
            if test not in seen:
                seen.add(test)
                out.append(test)
    return out


def filter_existing_tests(tests: Iterable[str]) -> list[str]:
    existing: list[str] = []
    for test in tests:
        if Path(test).exists():
            existing.append(test)
    return existing


def build_pytest_command(tests: Sequence[str], python_exe: str = "python") -> str:
    if not tests:
        raise ValueError("no selected tests")
    return " ".join([python_exe, "-m", "pytest", "-q", *tests])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select targeted tests from staged or provided paths.")
    parser.add_argument("--staged", action="store_true", help="select from git staged paths")
    parser.add_argument("--paths", nargs="*", default=[], help="explicit paths")
    parser.add_argument("--python", default="python", help="python executable for command generation")
    parser.add_argument(
        "--format",
        choices=("cmd", "list"),
        default="cmd",
        help="output format",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = list(args.paths)
    if args.staged or not paths:
        paths = staged_paths()

    tests = filter_existing_tests(select_tests(paths))
    if not tests:
        print("no test selected")
        return 1

    if args.format == "list":
        for test in tests:
            print(test)
        return 0

    print(build_pytest_command(tests, python_exe=args.python))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

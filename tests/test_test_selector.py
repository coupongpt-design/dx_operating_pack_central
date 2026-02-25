from __future__ import annotations

from tools.test_selector import build_pytest_command
from tools.test_selector import select_tests


def test_select_tests_for_governance_files() -> None:
    tests = select_tests(["AGENTS.md", "tools/git_hook_guards.py"])
    assert "tests/test_rule_docs_sync.py" in tests
    assert "tests/test_rule_guard_steps_mutation.py" in tests
    assert "tests/test_git_hook_guards.py" in tests


def test_select_tests_includes_changed_test_file_itself() -> None:
    tests = select_tests(["tests/test_excel_io.py"])
    assert tests == ["tests/test_excel_io.py"]


def test_build_pytest_command() -> None:
    cmd = build_pytest_command(["tests/test_a.py", "tests/test_b.py"])
    assert cmd == "python -m pytest -q tests/test_a.py tests/test_b.py"


def test_select_tests_for_task_start_guard() -> None:
    tests = select_tests(["tools/task_start_guard.py"])
    assert "tests/test_task_start_guard.py" in tests
    assert "tests/test_git_hook_guards.py" in tests

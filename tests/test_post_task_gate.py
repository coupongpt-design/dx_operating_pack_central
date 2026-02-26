from __future__ import annotations

from pathlib import Path

from tools.post_task_gate import parse_harvest_feedback
from tools.post_task_gate import parse_targeted
from tools.post_task_gate import run_gate
from tools.post_task_gate import _has_app_code_changes


def test_parse_targeted_auto() -> None:
    assert parse_targeted(["--targeted", "auto"]) == "auto"


def test_parse_targeted_manual_command() -> None:
    cmd = parse_targeted(["--targeted", "python", "-m", "pytest", "-q", "tests/test_x.py"])
    assert cmd == "python -m pytest -q tests/test_x.py"


def test_parse_harvest_feedback_default_true() -> None:
    assert parse_harvest_feedback(["--targeted", "auto"]) is True
    assert parse_harvest_feedback(["--targeted", "auto", "--skip-harvest"]) is False


def test_has_app_code_changes_detects_python_paths() -> None:
    class _Entry:
        def __init__(self, *paths: str) -> None:
            self.paths = paths

    assert _has_app_code_changes([_Entry("app/main.py")]) is True
    assert _has_app_code_changes([_Entry("docs/README.md")]) is False


def test_run_gate_auto_fails_when_app_changed_but_no_tests(monkeypatch, tmp_path: Path) -> None:
    import tools.post_task_gate as gate

    monkeypatch.setattr(gate, "GATE_FILE", tmp_path / "gate.json")

    def fake_git(*args: str) -> str:
        if args == ("diff", "--cached", "--name-status"):
            return "M\tapp/main.py\n"
        if args == ("rev-parse", "HEAD"):
            return "abc123\n"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(gate, "_git", fake_git)
    monkeypatch.setattr(gate, "select_tests", lambda paths: [])
    monkeypatch.setattr(gate, "filter_existing_tests", lambda tests: [])
    monkeypatch.setattr(gate, "_run_shell", lambda command: (0, "1 passed in 0.01s"))

    rc = run_gate("auto", harvest_feedback=False)
    assert rc == 1
    assert not gate.GATE_FILE.exists()


def test_run_gate_writes_timestamp_and_ttl(monkeypatch, tmp_path: Path) -> None:
    import json
    import tools.post_task_gate as gate

    monkeypatch.setattr(gate, "GATE_FILE", tmp_path / "gate.json")

    def fake_git(*args: str) -> str:
        if args == ("diff", "--cached", "--name-status"):
            return "M\ttools/task_finish.py\n"
        if args == ("rev-parse", "HEAD"):
            return "abc123\n"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(gate, "_git", fake_git)
    monkeypatch.setattr(gate, "select_tests", lambda paths: ["tests/test_task_finish.py"])
    monkeypatch.setattr(gate, "filter_existing_tests", lambda tests: list(tests))
    monkeypatch.setattr(gate, "build_pytest_command", lambda tests: "python -m pytest -q tests/test_task_finish.py")
    monkeypatch.setattr(gate, "_run_shell", lambda command: (0, "3 passed in 0.02s"))

    rc = run_gate("auto", harvest_feedback=False)
    assert rc == 0
    record = json.loads(gate.GATE_FILE.read_text(encoding="utf-8"))
    assert "timestamp" in record
    assert record.get("ttl_sec") == 1800

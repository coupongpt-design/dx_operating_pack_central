from __future__ import annotations

from tools.post_task_gate import parse_targeted


def test_parse_targeted_auto() -> None:
    assert parse_targeted(["--targeted", "auto"]) == "auto"


def test_parse_targeted_manual_command() -> None:
    cmd = parse_targeted(["--targeted", "python", "-m", "pytest", "-q", "tests/test_x.py"])
    assert cmd == "python -m pytest -q tests/test_x.py"

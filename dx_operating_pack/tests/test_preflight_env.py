from __future__ import annotations

from tools.preflight_env import CheckResult
from tools.preflight_env import _check_memory
from tools.preflight_env import _check_pytest_available
from tools.preflight_env import _check_required_commands
from tools.preflight_env import run_preflight


def test_check_required_commands_reports_missing(monkeypatch) -> None:
    import tools.preflight_env as env

    monkeypatch.setattr(env.shutil, "which", lambda cmd: None if cmd == "git" else "C:/python.exe")
    results = _check_required_commands()
    assert any((not r.ok) and r.message.startswith("git:") for r in results)


def test_check_pytest_available_pass(monkeypatch) -> None:
    import tools.preflight_env as env

    class _Proc:
        returncode = 0
        stdout = "pytest 9.0.1\n"
        stderr = ""

    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: _Proc())
    result = _check_pytest_available()
    assert result.ok is True
    assert "pytest" in result.message


def test_check_memory_skipped_when_unknown(monkeypatch) -> None:
    import tools.preflight_env as env

    monkeypatch.setattr(env, "_available_memory_mb", lambda: None)
    result = _check_memory()
    assert result.ok is True
    assert "unknown" in result.message


def test_run_preflight_fails_on_any_error(monkeypatch) -> None:
    import tools.preflight_env as env

    monkeypatch.setattr(
        env,
        "_check_required_commands",
        lambda: [CheckResult(False, "git missing"), CheckResult(True, "python ok")],
    )
    monkeypatch.setattr(env, "_check_pytest_available", lambda: CheckResult(True, "pytest ok"))
    monkeypatch.setattr(env, "_check_memory", lambda: CheckResult(True, "memory ok"))
    assert run_preflight() == 1

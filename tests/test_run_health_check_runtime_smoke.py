from __future__ import annotations

import sys

import run_health_check as health_check


def test_main_skips_runtime_smoke_by_default(monkeypatch) -> None:
    monkeypatch.setattr(health_check, "_run_pytest_suite", lambda: 0)
    called = {"smoke": 0}

    def _fake_runtime_smoke(*, python: str, timeout_sec: float, headed: bool) -> int:
        called["smoke"] += 1
        return 0

    monkeypatch.setattr(health_check, "_run_runtime_smoke", _fake_runtime_smoke)
    code = health_check.main([])
    assert code == 0
    assert called["smoke"] == 0


def test_main_runs_runtime_smoke_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(health_check, "_run_pytest_suite", lambda: 0)
    captured: dict[str, object] = {}

    def _fake_runtime_smoke(*, python: str, timeout_sec: float, headed: bool) -> int:
        captured["python"] = python
        captured["timeout_sec"] = timeout_sec
        captured["headed"] = headed
        return 0

    monkeypatch.setattr(health_check, "_run_runtime_smoke", _fake_runtime_smoke)
    code = health_check.main(["--runtime-smoke", "--smoke-timeout-sec", "7.5", "--smoke-headed"])
    assert code == 0
    assert captured == {
        "python": sys.executable,
        "timeout_sec": 7.5,
        "headed": True,
    }


def test_main_fails_when_runtime_smoke_fails(monkeypatch) -> None:
    monkeypatch.setattr(health_check, "_run_pytest_suite", lambda: 0)
    monkeypatch.setattr(
        health_check,
        "_run_runtime_smoke",
        lambda *, python, timeout_sec, headed: 2,
    )
    code = health_check.main(["--runtime-smoke"])
    assert code == 2


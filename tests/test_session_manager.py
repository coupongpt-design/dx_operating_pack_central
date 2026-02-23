import sys
from types import SimpleNamespace

import pytest

# Ensure root on path
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.session_manager import GameSession, SessionManager  # noqa: E402


def test_crud_operations(qtbot):
    mgr = SessionManager()
    mgr.add_session(GameSession("Maple", "Maple", "Maple.json"))
    assert len(mgr.sessions) == 1
    mgr.remove_session(0)
    assert len(mgr.sessions) == 0


def _make_runner(call_state):
    running = {"val": False}

    def start():
        call_state["start"] += 1
        running["val"] = True

    def is_running():
        return running["val"]

    def requestInterruption():
        call_state["stop"] += 1
        running["val"] = False

    return SimpleNamespace(start=start, isRunning=is_running, requestInterruption=requestInterruption)


def test_round_robin_rotation(qtbot, monkeypatch):
    mgr = SessionManager()
    # prevent actual timer scheduling during test; we'll call _switch_context manually
    mgr._timer.stop()

    calls = {
        "s1": {"start": 0, "stop": 0, "activate": 0},
        "s2": {"start": 0, "stop": 0, "activate": 0},
        "s3": {"start": 0, "stop": 0, "activate": 0},
    }

    def make_session(key):
        runner = _make_runner(calls[key])

        def activate_window(hwnd):
            calls[key]["activate"] += 1

        return GameSession(
            name=key,
            target_title=key,
            script_path=f"{key}.json",
            runner=runner,
            status="idle",
        ), activate_window

    s1, act1 = make_session("s1")
    s2, act2 = make_session("s2")
    s3, act3 = make_session("s3")

    mgr.sessions = [s1, s2, s3]

    # Replace WindowManager with mocks that count activation
    mgr._wm = SimpleNamespace(
        find_window=lambda title: title,
        activate_window=lambda hwnd: [act1, act2, act3][["s1", "s2", "s3"].index(hwnd)](hwnd),
    )

    # Step 1: start -> should activate/start s1
    mgr.start_rotation()
    assert calls["s1"]["start"] == 1
    assert calls["s1"]["activate"] == 1

    # Step 2: manual switch -> s1 stop, s2 start/activate
    mgr._switch_context()
    assert calls["s1"]["stop"] == 1
    assert calls["s2"]["start"] == 1
    assert calls["s2"]["activate"] == 1

    # Step 3: switch -> s3
    mgr._switch_context()
    assert calls["s3"]["start"] == 1
    assert calls["s3"]["activate"] == 1

    # Step 4: switch -> back to s1
    mgr._switch_context()
    assert calls["s1"]["start"] == 2  # started again
    assert calls["s1"]["activate"] == 2


def test_pending_session_recovers_with_backoff(monkeypatch):
    now = {"t": 100.0}
    monkeypatch.setattr("app.core.session_manager.time.monotonic", lambda: now["t"])

    runner_calls = {"start": 0, "stop": 0}
    runner = _make_runner(runner_calls)
    provider_calls = {"count": 0}

    def provider(_sess):
        provider_calls["count"] += 1
        if provider_calls["count"] >= 2:
            return runner
        return None

    mgr = SessionManager(
        runner_provider=provider,
        pending_recovery_backoff_sec=2.0,
        pending_recovery_max_attempts=5,
        pending_recovery_max_pending_sec=30.0,
    )
    mgr._timer.stop()
    mgr._wm = SimpleNamespace(find_window=lambda _title: None, activate_window=lambda _hwnd: None)
    sess = GameSession(name="p1", target_title="", script_path="p1.json", runner=None, status="idle")
    mgr.sessions = [sess]

    mgr._switch_context()
    assert provider_calls["count"] == 1
    assert sess.status == "pending"

    # Backoff window has not elapsed: provider should not be called again.
    mgr._switch_context()
    assert provider_calls["count"] == 1
    assert sess.status == "pending"

    now["t"] = 102.1
    mgr._switch_context()
    assert provider_calls["count"] == 2
    assert sess.runner is runner
    assert sess.status == "running"
    assert runner_calls["start"] >= 1


def test_pending_session_escalates_to_error_after_max_attempts(monkeypatch):
    now = {"t": 200.0}
    monkeypatch.setattr("app.core.session_manager.time.monotonic", lambda: now["t"])

    provider_calls = {"count": 0}

    def provider(_sess):
        provider_calls["count"] += 1
        return None

    mgr = SessionManager(
        runner_provider=provider,
        pending_recovery_backoff_sec=1.0,
        pending_recovery_max_attempts=2,
        pending_recovery_max_pending_sec=30.0,
    )
    mgr._timer.stop()
    mgr._wm = SimpleNamespace(find_window=lambda _title: None, activate_window=lambda _hwnd: None)
    sess = GameSession(name="p2", target_title="", script_path="p2.json", runner=None, status="idle")
    mgr.sessions = [sess]

    mgr._switch_context()
    assert provider_calls["count"] == 1
    assert sess.status == "pending"

    now["t"] = 201.1
    mgr._switch_context()
    assert provider_calls["count"] == 2
    assert sess.status == "error"

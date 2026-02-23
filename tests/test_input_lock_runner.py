import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from app.core.input_lock import GlobalInputManager, InputLockTimeoutError
from app.core.models import RepeatConfig, StepData
from app.core.runner import MacroRunner


class DummyMSS:
    def __init__(self, *a, **k):
        self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _dummy_pyautogui():
    return SimpleNamespace(
        PAUSE=0,
        MINIMUM_DURATION=0,
        MINIMUM_SLEEP=0,
        FAILSAFE=False,
        moveTo=lambda *a, **k: None,
        click=lambda *a, **k: None,
        doubleClick=lambda *a, **k: None,
        mouseDown=lambda *a, **k: None,
        mouseUp=lambda *a, **k: None,
        hscroll=lambda *a, **k: None,
        scroll=lambda *a, **k: None,
        hotkey=lambda *a, **k: None,
        keyDown=lambda *a, **k: None,
        keyUp=lambda *a, **k: None,
        press=lambda *a, **k: None,
        typewrite=lambda *a, **k: None,
        easeInOutQuad=lambda x: x,
    )


def test_global_input_manager_times_out_when_held_by_other_thread():
    mgr = GlobalInputManager()
    entered = threading.Event()
    release = threading.Event()
    result = {"timed_out": False}

    def holder():
        with mgr.acquire(timeout_sec=1.0, owner="holder", operation="hold"):
            entered.set()
            release.wait(1.0)

    def waiter():
        try:
            with mgr.acquire(timeout_sec=0.05, owner="waiter", operation="wait"):
                pass
        except InputLockTimeoutError:
            result["timed_out"] = True

    th1 = threading.Thread(target=holder, daemon=True)
    th2 = threading.Thread(target=waiter, daemon=True)
    th1.start()
    assert entered.wait(0.5)
    th2.start()
    th2.join(1.0)
    release.set()
    th1.join(1.0)
    assert result["timed_out"] is True


def test_runner_writes_input_lock_events_on_success(monkeypatch, tmp_path):
    import app.core.runner as runner_mod

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)
    monkeypatch.setattr(runner_mod, "pyautogui", _dummy_pyautogui(), raising=False)

    step = StepData(id="clk1", name="Click", type="click_point", click_x=10, click_y=10)
    runner = MacroRunner(
        [step],
        repeat=RepeatConfig(repeat_count=1, stop_on_fail=True),
        dry_run=False,
        structured_logging=True,
        structured_log_dir=str(tmp_path),
        input_lock_timeout_sec=0.2,
        input_lock_manager=GlobalInputManager(),
    )
    runner.run()

    rows = _read_jsonl(Path(runner.structured_log_path))
    events = [row.get("event") for row in rows]
    assert "input_lock_waiting" in events
    assert "input_lock_acquired" in events
    assert "input_lock_released" in events
    assert "input_lock_timeout" not in events
    finished = next(row for row in rows if row.get("event") == "run_finished")
    assert finished.get("success") is True


def test_runner_writes_input_lock_timeout_and_fails(monkeypatch, tmp_path):
    import app.core.runner as runner_mod

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)
    monkeypatch.setattr(runner_mod, "pyautogui", _dummy_pyautogui(), raising=False)

    lock_mgr = GlobalInputManager()
    hold_entered = threading.Event()
    hold_release = threading.Event()

    def holder():
        with lock_mgr.acquire(timeout_sec=2.0, owner="holder", operation="hold"):
            hold_entered.set()
            hold_release.wait(2.0)

    th = threading.Thread(target=holder, daemon=True)
    th.start()
    assert hold_entered.wait(1.0)

    step = StepData(id="clk2", name="Click", type="click_point", click_x=10, click_y=10)
    runner = MacroRunner(
        [step],
        repeat=RepeatConfig(repeat_count=1, stop_on_fail=True),
        dry_run=False,
        structured_logging=True,
        structured_log_dir=str(tmp_path),
        input_lock_timeout_sec=0.05,
        input_lock_manager=lock_mgr,
    )
    runner.run()

    hold_release.set()
    th.join(1.0)

    rows = _read_jsonl(Path(runner.structured_log_path))
    events = [row.get("event") for row in rows]
    assert "input_lock_waiting" in events
    assert "input_lock_timeout" in events
    assert "step_failed" in events
    finished = next(row for row in rows if row.get("event") == "run_finished")
    assert finished.get("success") is False
    assert finished.get("reason") == "step_failed_stop_on_fail"


def test_input_lock_serializes_concurrent_runners(monkeypatch):
    import app.core.runner as runner_mod

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    state = {"active": 0, "max_active": 0}
    state_lock = threading.Lock()

    def tracked_move_to(*_a, **_k):
        with state_lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        try:
            time.sleep(0.03)
        finally:
            with state_lock:
                state["active"] -= 1

    monkeypatch.setattr(
        runner_mod,
        "pyautogui",
        SimpleNamespace(
            PAUSE=0,
            MINIMUM_DURATION=0,
            MINIMUM_SLEEP=0,
            FAILSAFE=False,
            moveTo=tracked_move_to,
            click=lambda *a, **k: None,
            doubleClick=lambda *a, **k: None,
            mouseDown=lambda *a, **k: None,
            mouseUp=lambda *a, **k: None,
            hscroll=lambda *a, **k: None,
            scroll=lambda *a, **k: None,
            hotkey=lambda *a, **k: None,
            keyDown=lambda *a, **k: None,
            keyUp=lambda *a, **k: None,
            press=lambda *a, **k: None,
            typewrite=lambda *a, **k: None,
            easeInOutQuad=lambda x: x,
        ),
        raising=False,
    )

    shared_lock = GlobalInputManager()
    step = StepData(id="clk", name="Click", type="click_point", click_x=10, click_y=10)
    runner1 = MacroRunner(
        [step],
        repeat=RepeatConfig(repeat_count=1, stop_on_fail=True),
        dry_run=False,
        structured_logging=False,
        input_lock_timeout_sec=1.0,
        input_lock_manager=shared_lock,
    )
    runner2 = MacroRunner(
        [step],
        repeat=RepeatConfig(repeat_count=1, stop_on_fail=True),
        dry_run=False,
        structured_logging=False,
        input_lock_timeout_sec=1.0,
        input_lock_manager=shared_lock,
    )

    t1 = threading.Thread(target=runner1.run, daemon=True)
    t2 = threading.Thread(target=runner2.run, daemon=True)
    t1.start()
    t2.start()
    t1.join(2.0)
    t2.join(2.0)

    assert t1.is_alive() is False
    assert t2.is_alive() is False
    assert state["max_active"] == 1

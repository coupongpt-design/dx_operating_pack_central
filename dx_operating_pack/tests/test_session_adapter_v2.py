import threading
import time

from app.core.data_orchestration import JobQueueManager
from app.core.session_adapter import SessionJobAdapter


class FakeRunner:
    def __init__(self):
        self.calls = 0
        self.payloads = []

    def execute_job(self, payload):
        self.calls += 1
        self.payloads.append(dict(payload or {}))
        mode = str((payload or {}).get("mode") or "success")
        if mode == "timeout":
            raise TimeoutError("sim-timeout")
        if mode == "error":
            raise RuntimeError("sim-error")
        if mode == "fatal":
            raise KeyboardInterrupt("sim-fatal")
        return True


def _wait_until(predicate, timeout_sec=3.0):
    started = time.perf_counter()
    while time.perf_counter() - started <= timeout_sec:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def test_adapter_success_path():
    rows = [{"mode": "success"} for _ in range(20)]
    manager = JobQueueManager(rows, max_retry=0, retry_delay_sec=0.001)
    runner = FakeRunner()
    a1 = SessionJobAdapter(manager, runner, consumer_id="c1")
    a2 = SessionJobAdapter(manager, runner, consumer_id="c2")
    a1.start()
    a2.start()
    assert _wait_until(manager.is_fully_done, timeout_sec=5.0)
    a1.stop()
    a2.stop()
    a1.join(1.0)
    a2.join(1.0)
    snap = manager.snapshot()
    assert snap["succeeded"] == 20
    assert snap["failed"] == 0


def test_adapter_exception_retry_until_cap():
    manager = JobQueueManager([{"mode": "error"}], max_retry=2, retry_delay_sec=0.001)
    runner = FakeRunner()
    adapter = SessionJobAdapter(manager, runner, consumer_id="ce")
    adapter.start()
    assert _wait_until(manager.is_fully_done, timeout_sec=5.0)
    adapter.join(1.0)
    snap = manager.snapshot()
    assert runner.calls == 3
    assert snap["retried"] == 2
    assert snap["failed"] == 1
    row = snap["rows"][0]
    assert str(row["error_reason"]).startswith("error:")


def test_adapter_timeout_reason_prefix():
    manager = JobQueueManager([{"mode": "timeout"}], max_retry=0, retry_delay_sec=0.001)
    runner = FakeRunner()
    adapter = SessionJobAdapter(manager, runner, consumer_id="ct")
    adapter.start()
    assert _wait_until(manager.is_fully_done, timeout_sec=5.0)
    adapter.join(1.0)
    snap = manager.snapshot()
    assert snap["failed"] == 1
    row = snap["rows"][0]
    assert str(row["error_reason"]).startswith("timeout:")


def test_adapter_stop_event_responsive():
    manager = JobQueueManager([{"mode": "error"}], max_retry=5, retry_delay_sec=2.0)
    runner = FakeRunner()
    stop_event = threading.Event()
    adapter = SessionJobAdapter(manager, runner, consumer_id="cs", stop_event=stop_event)
    adapter.start()

    assert _wait_until(lambda: runner.calls >= 1, timeout_sec=2.0)
    t0 = time.perf_counter()
    adapter.stop()
    adapter.join(1.0)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5
    assert adapter.is_alive() is False


def test_adapter_worker_death_safety_no_zombie_inflight():
    manager = JobQueueManager([{"mode": "fatal"}], max_retry=0, retry_delay_sec=0.001)
    runner = FakeRunner()
    adapter = SessionJobAdapter(manager, runner, consumer_id="cf")
    adapter.start()

    # fatal(BaseException) should not leave inflight hanging forever.
    assert _wait_until(manager.is_fully_done, timeout_sec=3.0)
    adapter.join(1.0)

    snap = manager.snapshot()
    assert snap["inflight"] == 0
    assert snap["failed"] == 1
    row = snap["rows"][0]
    assert str(row["error_reason"]).startswith("worker_crash:")


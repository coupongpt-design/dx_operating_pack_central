import argparse
import os
import subprocess
import sys
import threading
import time


class HeartbeatPlugin:
    def __init__(self, stall_sec: float) -> None:
        self._stall_sec = max(5.0, float(stall_sec))
        self._last_report = time.time()
        self._lock = threading.Lock()

    @property
    def stall_sec(self) -> float:
        return self._stall_sec

    def _mark(self) -> None:
        with self._lock:
            self._last_report = time.time()

    def last_report(self) -> float:
        with self._lock:
            return self._last_report

    def pytest_sessionstart(self, session):  # noqa: ANN001
        self._mark()

    def pytest_runtest_logreport(self, report):  # noqa: ANN001
        self._mark()

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ANN001
        self._mark()


def _start_watchdog(plugin: HeartbeatPlugin, interval_sec: float) -> threading.Event:
    stop_event = threading.Event()
    interval = max(5.0, float(interval_sec))

    def _watch():
        last_print = 0.0
        while not stop_event.is_set():
            time.sleep(1.0)
            now = time.time()
            if now - last_print < interval:
                continue
            since = now - plugin.last_report()
            if since >= plugin.stall_sec:
                print(
                    f"[HealthCheck] No test progress for {since:.0f}s; pytest still running...",
                    flush=True,
                )
                last_print = now
            elif since >= interval:
                print(
                    f"[HealthCheck] Running... last progress {since:.0f}s ago",
                    flush=True,
                )
                last_print = now

    thread = threading.Thread(target=_watch, name="healthcheck-watchdog", daemon=True)
    thread.start()
    return stop_event


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run test health check and optional runtime smoke")
    parser.add_argument(
        "--runtime-smoke",
        action="store_true",
        help="run runtime smoke after pytest succeeds",
    )
    parser.add_argument(
        "--smoke-timeout-sec",
        type=float,
        default=25.0,
        help="timeout for runtime smoke UI marker check",
    )
    parser.add_argument(
        "--smoke-headed",
        action="store_true",
        help="run runtime smoke with headed browser",
    )
    return parser.parse_args(list(argv or []))


def _run_pytest_suite() -> int:
    python = sys.executable
    args = ["tests", "-q"]
    cmd = [python, "-m", "pytest", *args]
    print(f"Running pytest: {' '.join(cmd)}")

    # Check pytest availability before spawning
    try:
        import pytest
    except Exception as exc:  # noqa: BLE001
        print(f"No module named pytest ({exc}). Install pytest before running health check.")
        print("SYSTEM FAILING")
        return 1

    try:
        heartbeat_sec = float(os.environ.get("HEALTHCHECK_HEARTBEAT_SEC", "30"))
        stall_sec = float(os.environ.get("HEALTHCHECK_STALL_SEC", "180"))
        plugin = HeartbeatPlugin(stall_sec=stall_sec)
        stop_event = _start_watchdog(plugin, interval_sec=heartbeat_sec)
        try:
            returncode = int(pytest.main(args, plugins=[plugin]))
        finally:
            stop_event.set()
    except SystemExit as exc:
        try:
            returncode = int(exc.code)
        except Exception:
            returncode = 1

    return returncode


def _run_runtime_smoke(*, python: str, timeout_sec: float, headed: bool) -> int:
    cmd = [python, "-m", "macro.run_runtime_smoke", "--timeout-sec", str(timeout_sec)]
    if headed:
        cmd.append("--headed")
    print(f"Running runtime smoke: {' '.join(cmd)}")
    try:
        completed = subprocess.run(cmd, check=False)
        return int(completed.returncode)
    except Exception as exc:  # noqa: BLE001
        print(f"[HealthCheck] Runtime smoke launch failed: {exc}")
        return 1


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    returncode = _run_pytest_suite()

    if returncode == 0:
        if ns.runtime_smoke:
            smoke_code = _run_runtime_smoke(
                python=sys.executable,
                timeout_sec=ns.smoke_timeout_sec,
                headed=ns.smoke_headed,
            )
            if smoke_code != 0:
                print("SYSTEM FAILING")
                return smoke_code
        print("SYSTEM HEALTHY")
        return 0

    print("SYSTEM FAILING")
    return returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

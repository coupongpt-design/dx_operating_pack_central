import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SMOKE_TESTS = [
    "tests/test_e2e_runtime_orchestration.py",
    "tests/test_scheduler_core.py",
    "tests/test_trigger_engine_core.py",
    "tests/test_image_dialog_presets.py",
    "tests/test_matcher_quality.py",
    "tests/test_stepdata_serialization.py",
]


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_pytest_args() -> list[str]:
    custom_args = os.environ.get("HEALTHCHECK_TEST_ARGS", "").strip()
    if custom_args:
        return shlex.split(custom_args)

    if _truthy(os.environ.get("HEALTHCHECK_FULL")):
        return ["tests", "-q"]

    return ["-q", *DEFAULT_SMOKE_TESTS]


def _terminate_process(proc: subprocess.Popen[str], grace_sec: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=max(0.5, float(grace_sec)))
        return
    except subprocess.TimeoutExpired:
        pass

    proc.kill()
    try:
        proc.wait(timeout=max(0.5, float(grace_sec)))
    except subprocess.TimeoutExpired:
        # Already kill-requested; parent will still report failing.
        pass


def _run_pytest_subprocess(cmd: list[str], heartbeat_sec: float, stall_sec: float) -> int:
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    last_output = {"at": time.monotonic()}
    lock = threading.Lock()

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line.rstrip("\n"), flush=True)
            with lock:
                last_output["at"] = time.monotonic()

    reader = threading.Thread(target=_reader, name="healthcheck-reader", daemon=True)
    reader.start()

    heartbeat = max(5.0, float(heartbeat_sec))
    stall = max(10.0, float(stall_sec))
    last_notice = 0.0

    while proc.poll() is None:
        time.sleep(1.0)
        with lock:
            idle = time.monotonic() - last_output["at"]

        now = time.monotonic()
        if idle >= stall:
            print(
                f"[HealthCheck] No output for {idle:.0f}s; terminating stalled pytest process.",
                flush=True,
            )
            _terminate_process(proc)
            return 124

        if idle >= heartbeat and (now - last_notice) >= heartbeat:
            print(f"[HealthCheck] Running... last output {idle:.0f}s ago", flush=True)
            last_notice = now

    reader.join(timeout=2.0)
    return int(proc.returncode or 0)


def main() -> int:
    python = sys.executable
    args = _build_pytest_args()
    cmd = [python, "-m", "pytest", *args]
    print(f"Running pytest: {' '.join(cmd)}")

    heartbeat_sec = float(os.environ.get("HEALTHCHECK_HEARTBEAT_SEC", "30"))
    stall_sec = float(os.environ.get("HEALTHCHECK_STALL_SEC", "180"))
    returncode = _run_pytest_subprocess(cmd, heartbeat_sec=heartbeat_sec, stall_sec=stall_sec)

    if returncode == 0:
        print("SYSTEM HEALTHY")
        return 0

    if returncode < 0:
        print(f"[HealthCheck] Pytest process crashed (returncode={returncode}).")
    print("SYSTEM FAILING")
    return returncode


if __name__ == "__main__":
    sys.exit(main())

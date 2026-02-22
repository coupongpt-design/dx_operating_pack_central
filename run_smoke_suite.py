import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _step_commands(quick: bool) -> list[tuple[str, list[str]]]:
    steps: list[tuple[str, list[str]]] = [
        (
            "runtime_core",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_e2e_runtime_orchestration.py",
                "tests/test_scheduler_core.py",
                "tests/test_trigger_engine_core.py",
            ],
        ),
        (
            "image_matching_core",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_image_dialog_presets.py",
                "tests/test_matcher_quality.py",
                "tests/test_stepdata_serialization.py",
            ],
        ),
    ]
    if not quick:
        steps.append(("health_check", [sys.executable, "run_health_check.py"]))
    return steps


def _run_step(name: str, cmd: list[str], log_write) -> int:
    started = time.perf_counter()
    log_write(f"[{_ts()}] [STEP] {name}: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        log_write(line.rstrip("\n"))
    rc = proc.wait()
    elapsed = time.perf_counter() - started
    log_write(f"[{_ts()}] [STEP] {name}: exit={rc}, elapsed={elapsed:.2f}s")
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run practical smoke suite for runtime confidence."
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only core suites (skip full run_health_check.py).",
    )
    args = parser.parse_args()

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    mode = "quick" if args.quick else "full"
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = logs_dir / f"smoke_suite_{mode}_{stamp}.log"

    with log_path.open("w", encoding="utf-8", newline="\n") as fp:
        def log_write(msg: str) -> None:
            print(msg, flush=True)
            fp.write(msg + "\n")
            fp.flush()

        log_write(f"[{_ts()}] [INFO] Smoke suite started (mode={mode})")
        log_write(f"[{_ts()}] [INFO] Log file: {log_path}")

        for name, cmd in _step_commands(quick=args.quick):
            rc = _run_step(name, cmd, log_write)
            if rc != 0:
                log_write(f"[{_ts()}] [FAIL] Smoke suite stopped at step: {name}")
                return rc

        log_write(f"[{_ts()}] [PASS] Smoke suite completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

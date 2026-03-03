from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from dataclasses import dataclass

MIN_AVAILABLE_MEMORY_MB = 256
REQUIRED_COMMANDS = ("git", "python")


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    message: str


def _check_required_commands() -> list[CheckResult]:
    results: list[CheckResult] = []
    for cmd in REQUIRED_COMMANDS:
        path = shutil.which(cmd)
        if path:
            results.append(CheckResult(True, f"{cmd}: {path}"))
        else:
            results.append(CheckResult(False, f"{cmd}: not found in PATH"))
    return results


def _check_pytest_available() -> CheckResult:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        line = (proc.stdout or proc.stderr or "").strip().splitlines()
        version_line = line[0] if line else "pytest available"
        return CheckResult(True, version_line)
    return CheckResult(False, "pytest: unavailable (python -m pytest --version failed)")


def _available_memory_mb() -> int | None:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    if sys.platform.startswith("win"):
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return int(stat.ullAvailPhys // (1024 * 1024))
        return None

    return None


def _check_memory() -> CheckResult:
    avail_mb = _available_memory_mb()
    if avail_mb is None:
        return CheckResult(True, "memory: unknown (skipped)")
    if avail_mb < MIN_AVAILABLE_MEMORY_MB:
        return CheckResult(
            False,
            f"memory: low available memory {avail_mb}MB < {MIN_AVAILABLE_MEMORY_MB}MB",
        )
    return CheckResult(True, f"memory: {avail_mb}MB available")


def run_preflight() -> int:
    checks: list[CheckResult] = []
    checks.extend(_check_required_commands())
    checks.append(_check_pytest_available())
    checks.append(_check_memory())

    has_error = False
    print("[preflight] environment checks")
    for result in checks:
        prefix = "PASS" if result.ok else "FAIL"
        print(f"- {prefix}: {result.message}")
        if not result.ok:
            has_error = True

    if has_error:
        print("[preflight] failed: fix environment before running task_finish")
        return 1
    print("[preflight] passed")
    return 0


def main() -> int:
    return run_preflight()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator


class InputLockTimeoutError(TimeoutError):
    """Raised when global input lock acquisition timed out."""


@dataclass
class InputLockToken:
    owner: str
    operation: str
    acquired_at: float
    wait_ms: int


class GlobalInputManager:
    """Singleton-style lock manager for physical input coordination."""

    def __init__(self):
        self._lock = threading.RLock()
        self._meta_lock = threading.Lock()
        self._owner = ""
        self._operation = ""
        self._acquired_at = 0.0

    @contextmanager
    def acquire(
        self,
        timeout_sec: float = 10.0,
        owner: str = "",
        operation: str = "",
    ) -> Generator[InputLockToken, None, None]:
        timeout = max(0.0, float(timeout_sec))
        started = time.perf_counter()
        ok = self._lock.acquire(timeout=timeout)
        if not ok:
            raise InputLockTimeoutError(
                f"input lock timeout after {timeout:.3f}s (owner={owner}, op={operation})"
            )

        acquired_at = time.perf_counter()
        token = InputLockToken(
            owner=str(owner or ""),
            operation=str(operation or ""),
            acquired_at=acquired_at,
            wait_ms=max(0, int((acquired_at - started) * 1000)),
        )
        with self._meta_lock:
            self._owner = token.owner
            self._operation = token.operation
            self._acquired_at = token.acquired_at
        try:
            yield token
        finally:
            with self._meta_lock:
                self._owner = ""
                self._operation = ""
                self._acquired_at = 0.0
            self._lock.release()


_GLOBAL_INPUT_MANAGER: GlobalInputManager | None = None


def get_global_input_manager() -> GlobalInputManager:
    global _GLOBAL_INPUT_MANAGER
    if _GLOBAL_INPUT_MANAGER is None:
        _GLOBAL_INPUT_MANAGER = GlobalInputManager()
    return _GLOBAL_INPUT_MANAGER


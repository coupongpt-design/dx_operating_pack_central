from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from PyQt5.QtCore import QObject, QTimer

from .runner import MacroRunner
from .window_manager import WindowManager


@dataclass
class GameSession:
    name: str
    target_title: str
    script_path: str
    runner: Optional[MacroRunner] = None
    status: str = "Idle"
    reset_time: str = ""            # "HH:MM"
    reset_vars: list[str] = field(default_factory=list)
    last_reset_date: str = ""       # ISO date "YYYY-MM-DD"


class SessionManager(QObject):
    """Round-robin manager for multiple game sessions."""

    def __init__(
        self,
        parent=None,
        runner_provider: Optional[Callable[[GameSession], Optional[MacroRunner]]] = None,
        pending_recovery_backoff_sec: float = 2.0,
        pending_recovery_max_attempts: int = 3,
        pending_recovery_max_pending_sec: float = 30.0,
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__ + ".SessionManager")
        self.sessions: List[GameSession] = []
        self._current_index = -1
        self._runner_provider = runner_provider
        self._pending_recovery_backoff_sec = max(0.1, float(pending_recovery_backoff_sec))
        self._pending_recovery_max_attempts = max(1, int(pending_recovery_max_attempts))
        self._pending_recovery_max_pending_sec = max(
            self._pending_recovery_backoff_sec,
            float(pending_recovery_max_pending_sec),
        )
        self._pending_recovery_meta: Dict[int, dict] = {}
        self._interval_ms = 5000
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._switch_context)
        self._wm = WindowManager()
        # Daily reset timer (every minute)
        self._reset_timer = QTimer(self)
        self._reset_timer.setInterval(60_000)
        self._reset_timer.timeout.connect(self._check_daily_resets)
        self._reset_timer.start()

    # Public API
    def set_interval_sec(self, sec: int) -> None:
        self._interval_ms = max(1000, int(sec * 1000))

    def add_session(self, session: GameSession) -> None:
        self.sessions.append(session)
        self._clear_pending_recovery(session)

    def remove_session(self, idx: int) -> None:
        if 0 <= idx < len(self.sessions):
            sess = self.sessions.pop(idx)
            self._stop_runner(sess)
            self._clear_pending_recovery(sess)

    def set_runner_provider(
        self,
        provider: Optional[Callable[[GameSession], Optional[MacroRunner]]],
    ) -> None:
        self._runner_provider = provider

    def start_rotation(self, interval_sec: int | None = None) -> None:
        if interval_sec is not None:
            self.set_interval_sec(interval_sec)
        if not self.sessions:
            self.logger.warning("No sessions to rotate.")
            return
        if not self._timer.isActive():
            self._timer.start(self._interval_ms)
        self._switch_context()

    def stop_rotation(self) -> None:
        self._timer.stop()
        for sess in self.sessions:
            self._stop_runner(sess)

    def stop_all(self) -> None:
        self.stop_rotation()

    def _pending_meta(self, sess: GameSession) -> dict:
        sid = id(sess)
        meta = self._pending_recovery_meta.get(sid)
        if meta is None:
            meta = {"attempts": 0, "next_try_at": 0.0, "first_pending_at": 0.0}
            self._pending_recovery_meta[sid] = meta
        return meta

    def _clear_pending_recovery(self, sess: GameSession) -> None:
        self._pending_recovery_meta.pop(id(sess), None)

    def _attempt_runner_recovery(self, sess: GameSession) -> bool:
        """Try to lazily build a runner for pending sessions with backoff."""
        meta = self._pending_meta(sess)
        now = time.monotonic()
        if meta["first_pending_at"] <= 0:
            meta["first_pending_at"] = now

        if now < meta["next_try_at"]:
            return False

        meta["attempts"] += 1
        if self._runner_provider is not None:
            try:
                runner = self._runner_provider(sess)
            except Exception:
                self.logger.exception("Runner provider failed for session %s", sess.name)
                runner = None
            if runner is not None:
                sess.runner = runner
                self._clear_pending_recovery(sess)
                return True

        # Exponential backoff, capped by pending timeout.
        backoff = self._pending_recovery_backoff_sec * (2 ** (meta["attempts"] - 1))
        backoff = min(backoff, self._pending_recovery_max_pending_sec)
        meta["next_try_at"] = now + backoff
        return False

    def _pending_escalation_reason(self, sess: GameSession) -> Optional[str]:
        meta = self._pending_recovery_meta.get(id(sess))
        if not meta:
            return None
        now = time.monotonic()
        attempts = int(meta.get("attempts", 0))
        first_pending_at = float(meta.get("first_pending_at", 0.0))
        elapsed = 0.0 if first_pending_at <= 0 else now - first_pending_at
        if attempts >= self._pending_recovery_max_attempts:
            return (
                f"runner recovery exceeded max attempts "
                f"({attempts}/{self._pending_recovery_max_attempts})"
            )
        if elapsed >= self._pending_recovery_max_pending_sec:
            return (
                f"runner recovery timeout "
                f"({elapsed:.1f}s/{self._pending_recovery_max_pending_sec:.1f}s)"
            )
        return None

    # Daily reset --------------------------------------------------------
    def _check_daily_resets(self) -> None:
        import datetime as _dt

        now = _dt.datetime.now()
        today = now.date().isoformat()
        current_hm = now.strftime("%H:%M")
        for sess in self.sessions:
            if not sess.reset_time:
                continue
            # Only once per day
            if sess.last_reset_date == today:
                continue
            # Trigger when current time has passed configured time
            if current_hm >= sess.reset_time:
                vars_to_reset = sess.reset_vars or []
                if isinstance(vars_to_reset, str):
                    vars_to_reset = [v.strip() for v in vars_to_reset.split(",") if v.strip()]
                ctx = getattr(sess.runner, "variable_context", None) if sess.runner else None
                if isinstance(ctx, dict):
                    for var in vars_to_reset:
                        ctx[var] = 0
                sess.last_reset_date = today
                self.logger.info("[%s] Daily Reset Triggered.", sess.name)

    # Internal
    def _stop_runner(self, sess: GameSession) -> None:
        if sess.runner and sess.runner.isRunning():
            try:
                if hasattr(sess.runner, "stop"):
                    sess.runner.stop()
                else:
                    sess.runner.requestInterruption()
            except Exception as e:
                self.logger.warning("[%s] Failed to request runner stop: %s", sess.name, e)
            try:
                sess.runner.wait(1500)
            except Exception as e:
                self.logger.warning("[%s] Failed while waiting for runner shutdown: %s", sess.name, e)
            sess.status = "stopped"

    def _switch_context(self) -> None:
        if not self.sessions:
            return
        # Pause current
        if 0 <= self._current_index < len(self.sessions):
            self._stop_runner(self.sessions[self._current_index])
        # Next index
        self._current_index = (self._current_index + 1) % len(self.sessions)
        sess = self.sessions[self._current_index]

        # Activate window if available
        if sess.target_title:
            try:
                hwnd = self._wm.find_window(sess.target_title)
                if hwnd:
                    self._wm.activate_window(hwnd)
                else:
                    self.logger.warning("Target window '%s' not found; continuing.", sess.target_title)
            except Exception:
                self.logger.exception("Failed to activate window for session %s", sess.name)

        # Start runner
        if sess.runner is None and sess.script_path:
            recovered = self._attempt_runner_recovery(sess)
            if not recovered:
                reason = self._pending_escalation_reason(sess)
                if reason:
                    sess.status = "error"
                    self.logger.error("Session %s pending escalation: %s", sess.name, reason)
                else:
                    sess.status = "pending"
                    self.logger.info(
                        "Session %s has no runner; recovery will retry with backoff.",
                        sess.name,
                    )
                return

        if sess.runner:
            try:
                if not sess.runner.isRunning():
                    sess.runner.start()
                sess.status = "running"
                self._clear_pending_recovery(sess)
            except Exception:
                self.logger.exception("Failed to start runner for session %s", sess.name)
                sess.status = "error"

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__ + ".SessionManager")
        self.sessions: List[GameSession] = []
        self._current_index = -1
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

    def remove_session(self, idx: int) -> None:
        if 0 <= idx < len(self.sessions):
            sess = self.sessions.pop(idx)
            self._stop_runner(sess)

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
            # Runner instantiation left to caller (UI) to keep dependencies minimal
            self.logger.info("Session %s has no runner; provide a runner before rotation.", sess.name)
            sess.status = "pending"
            return

        if sess.runner:
            try:
                if not sess.runner.isRunning():
                    sess.runner.start()
                sess.status = "running"
            except Exception:
                self.logger.exception("Failed to start runner for session %s", sess.name)
                sess.status = "error"

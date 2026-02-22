import os

from PyQt5.QtCore import QObject, QTimer, QTime, QDate, pyqtSignal

class MacroScheduler(QObject):
    statusChanged = pyqtSignal(str)
    log = pyqtSignal(str)
    requestRunMacro = pyqtSignal(str)
    sequenceFinished = pyqtSignal()

    FAILURE_CONTINUE = "continue_next"
    FAILURE_STOP = "stop_sequence"
    FAILURE_RETRY = "retry_then_continue"
    VALID_FAILURE_POLICIES = (
        FAILURE_CONTINUE,
        FAILURE_STOP,
        FAILURE_RETRY,
    )
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_time)
        self.timer.setInterval(1000)
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._retry_active_path)
        
        self.running = False
        self.target_time = QTime(0, 0)
        self.macro_queue = []
        self.current_queue = []
        self.ran_today = False
        self.last_run_date = QDate.currentDate()
        self.failure_policy = self.FAILURE_CONTINUE
        self.max_retries = 1
        self.retry_delay_ms = 1000
        self._active_path = None
        self._active_retry_count = 0
        self._retry_path = None
        
    def set_enabled(self, enabled: bool):
        self.running = enabled
        if enabled:
            self.timer.start()
            self.statusChanged.emit(f"Status: Waiting for {self.target_time.toString('HH:mm')}")
            self.log.emit(f"[Scheduler] Started. Waiting for {self.target_time.toString('HH:mm')}.")
        else:
            self.timer.stop()
            if self._retry_timer.isActive():
                self._retry_timer.stop()
            self.statusChanged.emit("Status: Stopped")
            self.log.emit("[Scheduler] Stopped.")
            self.current_queue = []
            self._clear_active_state()
            
    def set_target_time(self, time: QTime):
        self.target_time = time
        if self.running:
             self.statusChanged.emit(f"Status: Waiting for {self.target_time.toString('HH:mm')}")
        
    def set_macro_queue(self, queue: list[str]):
        self.macro_queue = queue

    def set_failure_policy(self, policy: str):
        normalized = str(policy or self.FAILURE_CONTINUE)
        if normalized not in self.VALID_FAILURE_POLICIES:
            normalized = self.FAILURE_CONTINUE
        self.failure_policy = normalized

    def set_retry_options(self, max_retries: int, retry_delay_ms: int):
        retries = int(max_retries)
        delay = int(retry_delay_ms)
        self.max_retries = max(0, retries)
        self.retry_delay_ms = max(0, delay)

    def _macro_name(self, path: str | None) -> str:
        if not path:
            return "<unknown>"
        return os.path.basename(path) or path
        
    def _check_time(self):
        if not self.running: return
        
        now = QTime.currentTime()
        today = QDate.currentDate()
        
        if self.last_run_date != today:
            self.ran_today = False
            self.last_run_date = today
            
        if not self.ran_today and now.hour() == self.target_time.hour() and now.minute() == self.target_time.minute():
            self.log.emit(f"[Scheduler] It's {now.toString('HH:mm')}! Starting sequence.")
            self.ran_today = True
            self._start_sequence()
            
    def _start_sequence(self):
        self.current_queue = list(self.macro_queue)
        self._clear_active_state()
        if not self.current_queue:
            self.log.emit("[Scheduler] No macros in queue.")
            return
        self._run_next()
        
    def _run_next(self):
        if not self.running: return
        if self._retry_timer.isActive():
            self._retry_timer.stop()
            self._retry_path = None
        
        if self.current_queue:
            path = self.current_queue.pop(0)
            self._active_path = path
            self._active_retry_count = 0
            self.statusChanged.emit(f"Status: Running {self._macro_name(path)}")
            self.log.emit(f"[Scheduler] Requesting run: {path}")
            self.requestRunMacro.emit(path)
        else:
            self._clear_active_state()
            self.log.emit("[Scheduler] Sequence finished.")
            self.sequenceFinished.emit()
            self.statusChanged.emit(f"Status: Waiting for {self.target_time.toString('HH:mm')} (Tomorrow)")
            
    def notify_macro_finished(self, success: bool):
        if not self.running:
            return

        if bool(success):
            self._clear_active_state()
            self._run_next()
            return

        if self.failure_policy == self.FAILURE_STOP:
            path = self._active_path or "<unknown>"
            self.log.emit(f"[Scheduler] Macro failed; stopping sequence: {path}")
            self.current_queue = []
            self._clear_active_state()
            self.sequenceFinished.emit()
            self.statusChanged.emit(
                f"Status: Sequence stopped on failure ({self._macro_name(path)}). "
                f"Waiting for {self.target_time.toString('HH:mm')} (Tomorrow)"
            )
            return

        if self.failure_policy == self.FAILURE_RETRY:
            path = self._active_path
            if not path:
                self.log.emit("[Scheduler] Macro failed but active path is unknown; continuing.")
                self._run_next()
                return

            if self._active_retry_count < self.max_retries:
                self._active_retry_count += 1
                self.log.emit(
                    f"[Scheduler] Macro failed; retry {self._active_retry_count}/{self.max_retries}: {path}"
                )
                retry_status = (
                    f"Status: Retrying {self._macro_name(path)} "
                    f"({self._active_retry_count}/{self.max_retries})"
                )
                self._retry_path = path
                if self.retry_delay_ms <= 0:
                    self.statusChanged.emit(retry_status)
                    self._retry_active_path()
                else:
                    self.statusChanged.emit(f"{retry_status} in {self.retry_delay_ms}ms")
                    self._retry_timer.start(self.retry_delay_ms)
                return

            self.log.emit(f"[Scheduler] Macro failed after retries; continuing: {path}")
            self.statusChanged.emit(
                f"Status: Retry limit reached for {self._macro_name(path)}; continuing"
            )
            self._clear_active_state()
            self._run_next()
            return

        path = self._active_path or "<unknown>"
        self.log.emit(f"[Scheduler] Macro failed; continuing with next: {path}")
        self.statusChanged.emit(f"Status: Failure on {self._macro_name(path)}; continuing")
        self._clear_active_state()
        self._run_next()

    def _retry_active_path(self):
        if not self.running:
            return
        path = self._retry_path or self._active_path
        if not path:
            return
        if self._active_path and self._active_path != path:
            return
        attempt = self._active_retry_count if self._active_retry_count > 0 else 1
        self.statusChanged.emit(
            f"Status: Running {self._macro_name(path)} (Retry {attempt}/{self.max_retries})"
        )
        self.log.emit(f"[Scheduler] Requesting retry run (attempt {attempt}): {path}")
        self.requestRunMacro.emit(path)

    def _clear_active_state(self):
        self._active_path = None
        self._active_retry_count = 0
        self._retry_path = None
        if self._retry_timer.isActive():
            self._retry_timer.stop()

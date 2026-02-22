from PyQt5.QtCore import QObject, QTimer, QTime, QDate, pyqtSignal

class MacroScheduler(QObject):
    statusChanged = pyqtSignal(str)
    log = pyqtSignal(str)
    requestRunMacro = pyqtSignal(str)
    sequenceFinished = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_time)
        self.timer.setInterval(1000)
        
        self.running = False
        self.target_time = QTime(0, 0)
        self.macro_queue = []
        self.current_queue = []
        self.ran_today = False
        self.last_run_date = QDate.currentDate()
        
    def set_enabled(self, enabled: bool):
        self.running = enabled
        if enabled:
            self.timer.start()
            self.statusChanged.emit(f"Status: Waiting for {self.target_time.toString('HH:mm')}")
            self.log.emit(f"[Scheduler] Started. Waiting for {self.target_time.toString('HH:mm')}.")
        else:
            self.timer.stop()
            self.statusChanged.emit("Status: Stopped")
            self.log.emit("[Scheduler] Stopped.")
            self.current_queue = []
            
    def set_target_time(self, time: QTime):
        self.target_time = time
        if self.running:
             self.statusChanged.emit(f"Status: Waiting for {self.target_time.toString('HH:mm')}")
        
    def set_macro_queue(self, queue: list[str]):
        self.macro_queue = queue
        
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
        if not self.current_queue:
            self.log.emit("[Scheduler] No macros in queue.")
            return
        self._run_next()
        
    def _run_next(self):
        if not self.running: return
        
        if self.current_queue:
            path = self.current_queue.pop(0)
            self.log.emit(f"[Scheduler] Requesting run: {path}")
            self.requestRunMacro.emit(path)
        else:
            self.log.emit("[Scheduler] Sequence finished.")
            self.sequenceFinished.emit()
            self.statusChanged.emit(f"Status: Waiting for {self.target_time.toString('HH:mm')} (Tomorrow)")
            
    def notify_macro_finished(self, success: bool):
        if self.running:
            self._run_next()

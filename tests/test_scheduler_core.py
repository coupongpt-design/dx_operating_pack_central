import os
import sys

from PyQt5.QtCore import QDate, QTime
from PyQt5.QtWidgets import QApplication
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.scheduler import MacroScheduler


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_set_enabled_start_stop_emits_status_and_logs(qapp):
    sched = MacroScheduler()
    statuses = []
    logs = []
    sched.statusChanged.connect(statuses.append)
    sched.log.connect(logs.append)
    sched.set_target_time(QTime(9, 30))

    sched.set_enabled(True)
    assert sched.running is True
    assert sched.timer.isActive() is True
    assert statuses[-1] == "Status: Waiting for 09:30"
    assert "[Scheduler] Started." in logs[-1]

    sched.current_queue = ["a.macro"]
    sched.set_enabled(False)
    assert sched.running is False
    assert sched.timer.isActive() is False
    assert sched.current_queue == []
    assert statuses[-1] == "Status: Stopped"
    assert logs[-1] == "[Scheduler] Stopped."


def test_set_target_time_updates_status_when_running(qapp):
    sched = MacroScheduler()
    statuses = []
    sched.statusChanged.connect(statuses.append)

    sched.set_enabled(True)
    sched.set_target_time(QTime(14, 5))

    assert statuses[-1] == "Status: Waiting for 14:05"
    sched.set_enabled(False)


def test_start_sequence_empty_queue_logs_without_request(qapp):
    sched = MacroScheduler()
    logs = []
    requested = []
    sched.log.connect(logs.append)
    sched.requestRunMacro.connect(requested.append)
    sched.set_macro_queue([])

    sched._start_sequence()

    assert requested == []
    assert any("No macros in queue." in msg for msg in logs)


def test_run_next_emits_request_and_pops_queue_when_running(qapp):
    sched = MacroScheduler()
    requested = []
    statuses = []
    sched.statusChanged.connect(statuses.append)
    sched.requestRunMacro.connect(requested.append)
    sched.running = True
    sched.current_queue = ["a.macro", "b.macro"]

    sched._run_next()

    assert requested == ["a.macro"]
    assert sched.current_queue == ["b.macro"]
    assert statuses[-1] == "Status: Running a.macro"


def test_run_next_emits_finished_when_queue_is_empty(qapp):
    sched = MacroScheduler()
    statuses = []
    finished = []
    sched.statusChanged.connect(statuses.append)
    sched.sequenceFinished.connect(lambda: finished.append(True))
    sched.running = True
    sched.set_target_time(QTime(8, 0))
    sched.current_queue = []

    sched._run_next()

    assert finished == [True]
    assert statuses[-1] == "Status: Waiting for 08:00 (Tomorrow)"


def test_notify_macro_finished_advances_only_when_running(qapp):
    sched = MacroScheduler()
    requested = []
    sched.requestRunMacro.connect(requested.append)
    sched.current_queue = ["one.macro"]

    sched.running = False
    sched.notify_macro_finished(True)
    assert requested == []

    sched.running = True
    sched.notify_macro_finished(True)
    assert requested == ["one.macro"]


def test_check_time_triggers_once_per_day(qapp):
    sched = MacroScheduler()
    runs = {"n": 0}
    sched._start_sequence = lambda: runs.__setitem__("n", runs["n"] + 1)
    sched.running = True
    sched.target_time = QTime.currentTime()
    sched.ran_today = False

    sched._check_time()
    sched._check_time()

    assert runs["n"] == 1
    assert sched.ran_today is True


def test_check_time_resets_ran_today_when_date_changes(qapp):
    sched = MacroScheduler()
    now = QTime.currentTime()
    sched.running = True
    sched.ran_today = True
    sched.last_run_date = QDate.currentDate().addDays(-1)
    sched.target_time = QTime((now.hour() + 1) % 24, now.minute())

    sched._check_time()

    assert sched.last_run_date == QDate.currentDate()
    assert sched.ran_today is False


def test_notify_failure_continue_policy_requests_next(qapp):
    sched = MacroScheduler()
    requested = []
    sched.requestRunMacro.connect(requested.append)
    sched.running = True
    sched.current_queue = ["next.macro"]
    sched._active_path = "failed.macro"
    sched.set_failure_policy(MacroScheduler.FAILURE_CONTINUE)

    sched.notify_macro_finished(False)

    assert requested == ["next.macro"]
    assert sched._active_path == "next.macro"


def test_notify_failure_stop_policy_finishes_sequence(qapp):
    sched = MacroScheduler()
    statuses = []
    finished = []
    sched.statusChanged.connect(statuses.append)
    sched.sequenceFinished.connect(lambda: finished.append(True))
    sched.running = True
    sched.current_queue = ["next.macro"]
    sched._active_path = "failed.macro"
    sched.set_target_time(QTime(6, 0))
    sched.set_failure_policy(MacroScheduler.FAILURE_STOP)

    sched.notify_macro_finished(False)

    assert finished == [True]
    assert sched.current_queue == []
    assert sched._active_path is None
    assert (
        statuses[-1]
        == "Status: Sequence stopped on failure (failed.macro). Waiting for 06:00 (Tomorrow)"
    )


def test_notify_failure_retry_policy_retries_then_continues(qapp):
    sched = MacroScheduler()
    requested = []
    statuses = []
    sched.statusChanged.connect(statuses.append)
    sched.requestRunMacro.connect(requested.append)
    sched.running = True
    sched.current_queue = ["next.macro"]
    sched._active_path = "failed.macro"
    sched.set_failure_policy(MacroScheduler.FAILURE_RETRY)
    sched.set_retry_options(max_retries=2, retry_delay_ms=0)

    sched.notify_macro_finished(False)  # retry 1
    sched.notify_macro_finished(False)  # retry 2
    sched.notify_macro_finished(False)  # exhausted -> continue

    assert requested == ["failed.macro", "failed.macro", "next.macro"]
    assert sched._active_path == "next.macro"
    assert sched._active_retry_count == 0
    assert "Status: Retrying failed.macro (1/2)" in statuses
    assert "Status: Running failed.macro (Retry 1/2)" in statuses
    assert "Status: Retrying failed.macro (2/2)" in statuses
    assert "Status: Running failed.macro (Retry 2/2)" in statuses
    assert statuses[-1] == "Status: Running next.macro"


def test_notify_success_after_retry_moves_to_next(qapp):
    sched = MacroScheduler()
    requested = []
    sched.requestRunMacro.connect(requested.append)
    sched.running = True
    sched.current_queue = ["next.macro"]
    sched._active_path = "failed.macro"
    sched.set_failure_policy(MacroScheduler.FAILURE_RETRY)
    sched.set_retry_options(max_retries=3, retry_delay_ms=0)

    sched.notify_macro_finished(False)  # retry request
    sched.notify_macro_finished(True)   # success -> next

    assert requested == ["failed.macro", "next.macro"]
    assert sched._active_path == "next.macro"
    assert sched._active_retry_count == 0


def test_disable_clears_pending_retry_timer(qapp):
    sched = MacroScheduler()
    sched.running = True
    sched.current_queue = ["next.macro"]
    sched._active_path = "failed.macro"
    sched.set_failure_policy(MacroScheduler.FAILURE_RETRY)
    sched.set_retry_options(max_retries=1, retry_delay_ms=2000)

    sched.notify_macro_finished(False)
    assert sched._retry_timer.isActive() is True

    sched.set_enabled(False)

    assert sched._retry_timer.isActive() is False
    assert sched._active_path is None


def test_retry_policy_emits_delayed_status_when_timer_used(qapp):
    sched = MacroScheduler()
    statuses = []
    requested = []
    sched.statusChanged.connect(statuses.append)
    sched.requestRunMacro.connect(requested.append)
    sched.running = True
    sched._active_path = "failed.macro"
    sched.set_failure_policy(MacroScheduler.FAILURE_RETRY)
    sched.set_retry_options(max_retries=1, retry_delay_ms=250)

    sched.notify_macro_finished(False)

    assert sched._retry_timer.isActive() is True
    assert requested == []
    assert statuses[-1] == "Status: Retrying failed.macro (1/1) in 250ms"

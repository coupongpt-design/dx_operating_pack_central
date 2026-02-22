import os
import sys

from PyQt5.QtWidgets import QApplication

# Ensure root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.ui.tabs.manager_tab import ManagerTab  # noqa: E402


class DummyRunner:
    def __init__(self):
        self._running = False
        self.start_calls = 0
        self.stop_calls = 0
        self.wait_calls = []

    def isRunning(self):
        return self._running

    def start(self):
        self.start_calls += 1
        self._running = True

    def stop(self):
        self.stop_calls += 1
        self._running = False

    def wait(self, ms):
        self.wait_calls.append(ms)


def _add_session(tab: ManagerTab, name: str, script_path: str):
    tab.edName.setText(name)
    tab.edTarget.setText("")
    tab.edScript.setText(script_path)
    tab.edResetVars.setText("hp, mp")
    tab.btnAdd.click()
    assert len(tab.sessions) >= 1
    return tab.sessions[-1]


def test_manager_tab_add_session_updates_table(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    tab = ManagerTab()
    qtbot.addWidget(tab)

    _add_session(tab, "Session A", r"C:\tmp\a.macro")

    assert len(tab.sessions) == 1
    assert len(tab.manager.sessions) == 1
    assert tab.tbl.rowCount() == 1
    assert tab.tbl.item(0, 0).text() == "Session A"
    assert tab.tbl.item(0, 2).text() == r"C:\tmp\a.macro"

    tab.manager.stop_all()
    tab.close()
    app.processEvents()


def test_manager_tab_start_all_without_runner_sets_pending(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    tab = ManagerTab()
    qtbot.addWidget(tab)

    sess = _add_session(tab, "Session Pending", r"C:\tmp\pending.macro")
    tab.spInterval.setValue(10)
    tab.btnStartAll.click()
    qtbot.wait(10)

    assert sess.status == "pending"
    assert tab.tbl.item(0, 3).text() == "pending"

    tab.btnStopAll.click()
    tab.close()
    app.processEvents()


def test_manager_tab_start_all_with_runner_sets_running(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    tab = ManagerTab()
    qtbot.addWidget(tab)

    sess = _add_session(tab, "Session Running", r"C:\tmp\running.macro")
    runner = DummyRunner()
    sess.runner = runner
    tab.spInterval.setValue(10)
    tab.btnStartAll.click()
    qtbot.wait(10)

    assert runner.start_calls >= 1
    assert sess.status == "running"
    assert tab.tbl.item(0, 3).text() == "running"

    tab.btnStopAll.click()
    qtbot.wait(10)
    assert runner.stop_calls >= 1
    assert sess.status == "stopped"

    tab.close()
    app.processEvents()


def test_manager_tab_start_all_builds_runner_when_missing(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    tab = ManagerTab()
    qtbot.addWidget(tab)

    sess = _add_session(tab, "Session AutoBuild", r"C:\tmp\autobuild.macro")
    runner = DummyRunner()
    calls = {"count": 0}

    def _builder(_sess):
        calls["count"] += 1
        assert _sess is sess
        return runner

    tab.set_runner_builder(_builder)
    tab.spInterval.setValue(10)
    tab.btnStartAll.click()
    qtbot.wait(10)

    assert calls["count"] == 1
    assert sess.runner is runner
    assert runner.start_calls >= 1
    assert sess.status == "running"
    assert tab.tbl.item(0, 3).text() == "running"

    tab.btnStopAll.click()
    qtbot.wait(10)
    assert runner.stop_calls >= 1
    assert sess.status == "stopped"

    tab.close()
    app.processEvents()

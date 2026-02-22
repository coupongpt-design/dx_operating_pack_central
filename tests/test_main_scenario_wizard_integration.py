import os
import sys

import pytest
pytest.importorskip("pytestqt")
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_scenario_wizard_button_inserts_steps(monkeypatch, qapp, qtbot):
    from app.main import MainWindow
    from app.core.models import StepData

    class DummyWizard:
        Accepted = QDialog.Accepted

        def __init__(self, parent=None):
            self.parent = parent

        def exec_(self):
            return self.Accepted

        def get_result(self):
            return {
                "template_id": "dummy_template",
                "template_title": "Dummy",
                "insert_mode": "end",
                "steps": [StepData(id="wiz1", name="Wizard Added", type="comment", comment="via wizard")],
                "values": {},
            }

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.ScenarioWizardDialog", DummyWizard)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    assert hasattr(win, "btnScenarioWizard")
    assert len(win.steps) == 0

    qtbot.mouseClick(win.btnScenarioWizard, Qt.LeftButton)

    assert len(win.steps) == 1
    assert win.steps[0].name == "Wizard Added"
    assert win.steps[0].type == "comment"
    win.close()


def test_scenario_wizard_insert_after_selected_row(monkeypatch, qapp, qtbot):
    from app.main import MainWindow
    from app.core.models import StepData

    class DummyWizardAfterSelection:
        Accepted = QDialog.Accepted

        def __init__(self, parent=None):
            self.parent = parent

        def exec_(self):
            return self.Accepted

        def get_result(self):
            return {
                "template_id": "dummy_template",
                "template_title": "Dummy",
                "insert_mode": "after_selection",
                "steps": [StepData(id="wiz2", name="Inserted Next", type="comment", comment="next row")],
                "values": {},
            }

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr("app.main.ScenarioWizardDialog", DummyWizardAfterSelection)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.steps[:] = [
        StepData(id="a1", name="A", type="comment", comment="a"),
        StepData(id="b1", name="B", type="comment", comment="b"),
    ]
    win.refresh_step_list()
    win.list.setCurrentRow(0)

    win.open_scenario_wizard()

    assert len(win.steps) == 3
    assert [s.name for s in win.steps] == ["A", "Inserted Next", "B"]
    win.close()

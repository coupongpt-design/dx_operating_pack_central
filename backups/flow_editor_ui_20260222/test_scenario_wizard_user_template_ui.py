import os
import sys

import pytest

pytest.importorskip("pytestqt")
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

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


def test_scenario_wizard_user_template_clone_edit_delete(monkeypatch, qapp, qtbot, tmp_path):
    from app.core import scenario_wizard as sw
    from app.ui.scenario_wizard import ScenarioWizardDialog

    user_file = tmp_path / "scenario_wizard_user_templates.json"
    monkeypatch.setattr(sw, "USER_TEMPLATE_FILE", user_file)

    class CloneDialog:
        def __init__(self, template, initial_values=None, parent=None):
            pass

        def exec_(self):
            return QDialog.Accepted

        def get_payload(self):
            return {
                "title": "UI 복제 템플릿",
                "summary": "ui clone",
                "tags": ["ui"],
                "defaults": {"message_text": "from_ui", "repeat_count": 2},
            }

    class EditDialog:
        def __init__(self, template, initial_values=None, parent=None):
            pass

        def exec_(self):
            return QDialog.Accepted

        def get_payload(self):
            return {
                "title": "UI 편집 템플릿",
                "summary": "ui edit",
                "tags": ["ui", "edited"],
                "defaults": {"repeat_count": 4},
            }

    win = ScenarioWizardDialog()
    qtbot.addWidget(win)
    win.hide()

    win._select_template_by_id("chat_repeater")
    monkeypatch.setattr("app.ui.scenario_wizard.UserTemplateEditDialog", CloneDialog)
    win._on_clone_template()

    users = sw.list_user_templates()
    assert len(users) == 1
    user_id = users[0]["id"]

    win._select_template_by_id(user_id)
    assert win._current_template is not None
    assert sw.is_user_template(win._current_template) is True

    monkeypatch.setattr("app.ui.scenario_wizard.UserTemplateEditDialog", EditDialog)
    win._on_edit_template()
    edited = sw.get_template(user_id)
    assert edited is not None
    assert edited.get("title") == "UI 편집 템플릿"

    monkeypatch.setattr("app.ui.scenario_wizard.QMessageBox.question", lambda *a, **k: QMessageBox.Yes)
    win._on_delete_template()
    assert sw.get_template(user_id) is None
    win.close()

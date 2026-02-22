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
        def __init__(self, template, initial_values=None, flow_blueprint=None, flow_system_step_ids=None, parent=None):
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
        def __init__(self, template, initial_values=None, flow_blueprint=None, flow_system_step_ids=None, parent=None):
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


def test_scenario_wizard_clone_to_custom_flow(monkeypatch, qapp, qtbot, tmp_path):
    from app.core import scenario_wizard as sw
    from app.ui.scenario_wizard import ScenarioWizardDialog

    user_file = tmp_path / "scenario_wizard_user_templates.json"
    monkeypatch.setattr(sw, "USER_TEMPLATE_FILE", user_file)

    class FlowCloneDialog:
        def __init__(self, template, initial_values=None, flow_blueprint=None, flow_system_step_ids=None, parent=None):
            self._flow = flow_blueprint or []
            self._system_ids = list(flow_system_step_ids or [])

        def exec_(self):
            return QDialog.Accepted

        def get_payload(self):
            rows = list(self._flow)
            rows.insert(
                1,
                {
                    "id": "u_custom_1",
                    "name": "Inserted Click",
                    "type": "click_point",
                    "click_x": 100,
                    "click_y": 200,
                    "click_btn": "left",
                },
            )
            return {
                "title": "CF 템플릿",
                "summary": "custom flow clone",
                "tags": ["ui", "flow"],
                "defaults": {},
                "use_custom_flow": True,
                "steps_blueprint": rows,
                "system_step_ids": self._system_ids,
            }

    win = ScenarioWizardDialog()
    qtbot.addWidget(win)
    win.hide()

    win._select_template_by_id("chat_repeater")
    monkeypatch.setattr("app.ui.scenario_wizard.UserTemplateEditDialog", FlowCloneDialog)
    win._on_clone_template()

    users = sw.list_user_templates()
    assert len(users) == 1
    saved = users[0]
    assert saved.get("mode") == "custom_flow"
    assert saved.get("fields") == []
    assert isinstance(saved.get("steps_blueprint"), list)
    assert any(str(row.get("id") or "") == "u_custom_1" for row in saved.get("steps_blueprint", []))
    win.close()


def test_flow_editor_seed_works_without_manual_required_inputs(monkeypatch, qapp, qtbot, tmp_path):
    from app.core import scenario_wizard as sw
    from app.ui.scenario_wizard import ScenarioWizardDialog

    user_file = tmp_path / "scenario_wizard_user_templates.json"
    monkeypatch.setattr(sw, "USER_TEMPLATE_FILE", user_file)

    seen: dict[str, Any] = {}

    class ProbeDialog:
        def __init__(self, template, initial_values=None, flow_blueprint=None, flow_system_step_ids=None, parent=None):
            seen["template_id"] = str(template.get("id") or "")
            seen["flow_count"] = len(flow_blueprint or [])

        def exec_(self):
            return QDialog.Rejected

    win = ScenarioWizardDialog()
    qtbot.addWidget(win)
    win.hide()

    idx = win.cbScope.findData("all")
    if idx >= 0:
        win.cbScope.setCurrentIndex(idx)
    win._select_template_by_id("run_macro_once")

    monkeypatch.setattr("app.ui.scenario_wizard.UserTemplateEditDialog", ProbeDialog)
    win._on_clone_template()

    assert seen.get("template_id") == "run_macro_once"
    assert int(seen.get("flow_count") or 0) > 0
    win.close()

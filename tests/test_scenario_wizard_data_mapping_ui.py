import os
import sys

import pytest

pytest.importorskip("pytestqt")
from PyQt5.QtWidgets import QApplication

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


def test_scenario_wizard_column_mapping_inserts_placeholder(qapp, qtbot, tmp_path):
    from app.ui.scenario_wizard import ScenarioWizardDialog

    csv_path = tmp_path / "mapping.csv"
    csv_path.write_text("name,email\nalice,a@test.com\n", encoding="utf-8")

    win = ScenarioWizardDialog()
    qtbot.addWidget(win)
    win.hide()
    win._select_template_by_id("csv_text_submit_loop")

    data_widget = win._field_widgets["data_file_path"]
    text_widget = win._field_widgets["text_pattern"]
    map_button = win._column_map_buttons["text_pattern"]

    data_widget[0].setText(str(csv_path))
    win._refresh_preview()

    assert "name" in win._data_columns
    assert map_button.isEnabled() is True

    text_widget[0].setText("")
    win._insert_column_token("text_pattern", "name")
    assert "{name}" in text_widget[0].text()
    win.close()

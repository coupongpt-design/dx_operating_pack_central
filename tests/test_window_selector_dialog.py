import os
import sys

import pytest
pytest.importorskip("pytestqt")
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


def test_window_selector_item_label_hides_empty_process(monkeypatch, qapp, qtbot):
    from app.ui.window_selector import WindowSelectorDialog

    windows = [
        {"hwnd": 1, "title": "Untitled - Notepad", "class_name": "Notepad", "process_name": ""},
        {"hwnd": 2, "title": "Code", "class_name": "Chrome_WidgetWin_1", "process_name": "Code.exe"},
    ]
    monkeypatch.setattr("app.ui.window_selector.WindowManager.get_window_list", lambda self: windows)

    dlg = WindowSelectorDialog()
    qtbot.addWidget(dlg)

    assert dlg.list.count() == 2
    assert dlg.list.item(0).text() == "Untitled - Notepad"
    assert dlg.list.item(1).text() == "[Code.exe] Code"
    dlg.close()


def test_window_selector_empty_list_shows_hint(monkeypatch, qapp, qtbot):
    from app.ui.window_selector import WindowSelectorDialog

    monkeypatch.setattr("app.ui.window_selector.WindowManager.get_window_list", lambda self: [])
    dlg = WindowSelectorDialog()
    qtbot.addWidget(dlg)

    assert dlg.list.count() == 1
    assert "No windows found" in dlg.list.item(0).text()
    dlg.close()


def test_window_selector_accept_sets_selected_title(monkeypatch, qapp, qtbot):
    from app.ui.window_selector import WindowSelectorDialog

    windows = [{"hwnd": 7, "title": "Game Window", "class_name": "Foo", "process_name": "game.exe"}]
    monkeypatch.setattr("app.ui.window_selector.WindowManager.get_window_list", lambda self: windows)

    dlg = WindowSelectorDialog()
    qtbot.addWidget(dlg)
    dlg.list.setCurrentRow(0)
    dlg._accept_selection()

    assert dlg.selected_title == "Game Window"
    assert dlg.result() == QDialog.Accepted
    dlg.close()


def test_manager_tab_pick_target_uses_selected_title_attr(monkeypatch, qapp, qtbot):
    from app.ui.tabs.manager_tab import ManagerTab

    class DummyDialog:
        Accepted = QDialog.Accepted

        def __init__(self, parent=None):
            self.selected_title = "My Target Window"

        def exec_(self):
            return self.Accepted

    monkeypatch.setattr("app.ui.tabs.manager_tab.WindowSelectorDialog", DummyDialog)
    tab = ManagerTab()
    qtbot.addWidget(tab)

    tab._on_pick_target()
    assert tab.edTarget.text() == "My Target Window"
    tab.close()

import os
import sys

import pytest

pytest.importorskip("pytestqt")
from PyQt5.QtWidgets import QApplication, QSizePolicy


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_excel_toolbar_priority_controls_are_fixed(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    assert win.chkExcelDataMode.minimumWidth() >= 120
    assert win.spExcelParallelism.minimumWidth() >= 60
    assert win.chkExcelDataMode.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
    assert win.spExcelParallelism.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed

    win.close()


def test_excel_path_field_elides_but_keeps_full_text(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    full_path = r"D:\very\long\folder\structure\for\excel\input_file_name_that_is_really_long.xlsx"
    win.edExcelDataPath.setFixedWidth(60)
    win.edExcelDataPath.setText(full_path)
    qapp.processEvents()

    assert win.edExcelDataPath.text() == full_path
    assert len(win.edExcelDataPath.displayText()) <= len(full_path)
    assert win.edExcelDataPath.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding

    win.close()


def test_excel_priority_controls_stay_visible_on_narrow_width(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.resize(760, 640)
    qapp.processEvents()

    assert win.chkExcelDataMode.isVisible() is True
    assert win.spExcelParallelism.isVisible() is True
    assert win.chkAutoEnterAfterText.isVisible() is True

    win.close()


def test_option_toolbar_is_split_into_core_and_advanced_rows(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    assert hasattr(win, "_opt_core_layout")
    assert hasattr(win, "_opt_adv_layout")
    assert win.chkExcelDataMode.parentWidget().isVisible() is True
    assert win.chkDry.parentWidget().isVisible() is True
    assert win.chkExcelDataMode.isVisible() is True
    assert win.chkDry.isVisible() is True

    win.close()


def test_excel_mode_visual_feedback_updates_core_row_and_badge(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    assert hasattr(win, "lblBatchModeBadge")
    assert win.lblBatchModeBadge.isVisible() is False
    assert "transparent" in win._opt_core_row.styleSheet()

    win.chkExcelDataMode.setChecked(True)
    qapp.processEvents()
    assert win.lblBatchModeBadge.isVisible() is True
    assert "#E6F4EA" in win._opt_core_row.styleSheet()
    assert "Excel Batch Mode Activated" in win.statusBar().currentMessage()

    win.chkExcelDataMode.setChecked(False)
    qapp.processEvents()
    assert win.lblBatchModeBadge.isVisible() is False
    assert "transparent" in win._opt_core_row.styleSheet()
    assert "Standard Mode Activated" in win.statusBar().currentMessage()

    win.close()


def test_left_panel_run_stop_smart_capture_visible_on_narrow_width(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.resize(760, 640)
    qapp.processEvents()

    assert not hasattr(win, "btnToolbarRun")
    assert not hasattr(win, "btnToolbarStop")
    assert hasattr(win, "btnRun")
    assert hasattr(win, "btnStop")
    assert hasattr(win, "btnSmartCapture")
    assert win.btnRun.isVisible() is True
    assert win.btnStop.isVisible() is True
    assert win.btnSmartCapture.isVisible() is True
    assert win.btnRun.minimumHeight() >= 26
    assert win.btnStop.minimumHeight() >= 26
    assert win.btnSmartCapture.minimumHeight() >= 26

    win.close()


def test_left_panel_run_stop_buttons_dispatch_existing_paths(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    calls = {"run": 0, "stop": 0}

    def fake_run(self):
        calls["run"] += 1

    def fake_stop(self):
        calls["stop"] += 1

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(MainWindow, "_on_run_button_clicked", fake_run, raising=False)
    monkeypatch.setattr(MainWindow, "_on_stop_button_clicked", fake_stop, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    win.btnRun.click()
    win.btnStop.setEnabled(True)
    win.btnStop.click()

    assert calls["run"] == 1
    assert calls["stop"] == 1

    win.close()


def test_smart_capture_button_dispatches_capture_menu(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    calls = {"capture": 0}

    def fake_capture(self):
        calls["capture"] += 1

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(MainWindow, "_open_smart_capture_menu", fake_capture, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    win.btnSmartCapture.click()
    assert calls["capture"] == 1

    win.close()


def test_file_edit_menu_actions_dispatch_existing_slots(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    calls = {"open": 0, "save": 0, "undo": 0, "redo": 0}

    def fake_open(self):
        calls["open"] += 1

    def fake_save(self):
        calls["save"] += 1

    def fake_undo(self):
        calls["undo"] += 1

    def fake_redo(self):
        calls["redo"] += 1

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(MainWindow, "load_macro", fake_open, raising=False)
    monkeypatch.setattr(MainWindow, "save_macro", fake_save, raising=False)
    monkeypatch.setattr(MainWindow, "_do_undo", fake_undo, raising=False)
    monkeypatch.setattr(MainWindow, "_do_redo", fake_redo, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    menu_titles = [a.text() for a in win.menuBar().actions()]
    assert "File" in menu_titles
    assert "Edit" in menu_titles

    assert win.act_load.shortcut().toString() == "Ctrl+O"
    assert win.act_save.shortcut().toString() == "Ctrl+S"
    assert win.act_undo.shortcut().toString() == "Ctrl+Z"
    assert win.act_redo.shortcut().toString() == "Ctrl+Y"

    win.act_load.trigger()
    win.act_save.trigger()
    win.act_undo.trigger()
    win.act_redo.trigger()

    assert calls == {"open": 1, "save": 1, "undo": 1, "redo": 1}

    win.close()


def test_toolbar_no_longer_contains_file_edit_icon_group(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    toolbar_texts = [a.text() for a in win.toolbar.actions()]
    for removed in ("Save", "Open", "Undo", "Redo"):
        assert removed not in toolbar_texts

    win.close()


def test_splitter_left_panel_is_collapsible_and_snaps(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    assert win.splitter.isCollapsible(0) is True
    assert getattr(win, "_left_panel_snap_threshold_px", 0) >= 50

    sizes = win.splitter.sizes()
    right = sizes[2] if len(sizes) > 2 else 0
    win.splitter.setSizes([max(1, int(win._left_panel_snap_threshold_px) - 10), 800, right])
    qapp.processEvents()
    win._on_splitter_moved(0, 0)
    qapp.processEvents()

    assert win.splitter.sizes()[0] == 0

    win.close()


def test_manager_and_trigger_tabs_have_relaxed_min_width(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qapp.processEvents()

    assert win.left_tabs.minimumWidth() == 0
    assert win.trigger_list.minimumWidth() == 0
    assert win.manager_tab.tbl.minimumWidth() == 0
    assert win.manager_tab.btnAdd.minimumWidth() <= 8
    assert win.manager_tab.btnDel.minimumWidth() <= 8
    assert win.manager_tab.btnDup.minimumWidth() <= 8

    win.close()


def test_toolbar_height_and_margins_fit_two_rows_without_clipping(monkeypatch, qapp, qtbot):
    from app.main import MainWindow
    from PyQt5.QtCore import Qt

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.resize(900, 580)
    qapp.processEvents()

    margins = win._opt_root_layout.contentsMargins()
    assert margins.top() == 0
    assert margins.bottom() == 0
    assert win._opt_root_layout.spacing() == 2
    assert win._opt_scroll.minimumHeight() >= 75
    assert win._opt_core_row.isVisible() is True
    assert win._opt_adv_row.isVisible() is True
    assert win._opt_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert win.edTargetTitle.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert win.edExcelDataPath.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding

    win.close()

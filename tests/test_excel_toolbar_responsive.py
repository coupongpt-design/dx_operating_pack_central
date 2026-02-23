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

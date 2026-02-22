import os
import sys

import pytest
pytest.importorskip("pytestqt")
from PyQt5.QtCore import QPoint, QRect, QSettings
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


def _make_dialog(qtbot, step_type="comment", steps=None, step=None):
    from app.ui.dialogs import NotImageDialog
    from app.core.models import StepData

    step = step or StepData(id="s1", name="Action", type=step_type)
    dlg = NotImageDialog(step, steps or [])
    qtbot.addWidget(dlg)
    return dlg


def _set_action_type(dlg, action_type):
    idx = dlg.cbType.findText(action_type)
    assert idx >= 0
    dlg.cbType.setCurrentIndex(idx)
    dlg._refresh_visibility()


def test_action_dialog_pick_click_updates_coordinates(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_select_point(*_args, **_kwargs):
        return QPoint(12, 34)

    monkeypatch.setattr(dialogs, "safe_select_point", fake_select_point)
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "click_point")

    dlg._on_pick_click()

    assert dlg.spClickX.value() == 12
    assert dlg.spClickY.value() == 34
    dlg.close()


def test_action_dialog_keyboard_mode_saved(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "keyboard")

    idx = dlg.cbKeyMode.findText("key_down")
    assert idx >= 0
    dlg.cbKeyMode.setCurrentIndex(idx)
    dlg.edKey.setText("ctrl")

    step = dlg.result_step()

    assert step.type == "keyboard"
    assert step.keyboard_mode == "key_down"
    assert step.key_string == "ctrl"
    dlg.close()


def test_action_dialog_mouse_mode_switches_groups(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "mouse")

    assert dlg.groupClick.isHidden() is False

    idx = dlg.cbMouseMode.findText("drag")
    assert idx >= 0
    dlg.cbMouseMode.setCurrentIndex(idx)
    dlg._refresh_visibility()
    assert dlg.groupDrag.isHidden() is False
    assert dlg.groupClick.isHidden() is True

    idx = dlg.cbMouseMode.findText("scroll")
    assert idx >= 0
    dlg.cbMouseMode.setCurrentIndex(idx)
    dlg._refresh_visibility()
    assert dlg.groupScroll.isHidden() is False
    assert dlg.groupDrag.isHidden() is True
    dlg.close()


def test_action_dialog_mouse_mode_saved(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "mouse")

    idx = dlg.cbMouseMode.findText("scroll")
    assert idx >= 0
    dlg.cbMouseMode.setCurrentIndex(idx)
    dlg.spScrollDx.setValue(11)
    dlg.spScrollDy.setValue(-22)
    dlg.spScrollTimes.setValue(3)
    dlg.spScrollInterval.setValue(44)

    step = dlg.result_step()

    assert step.type == "mouse"
    assert step.mouse_mode == "scroll"
    assert step.scroll_dx == 11
    assert step.scroll_dy == -22
    assert step.scroll_times == 3
    assert step.scroll_interval_ms == 44
    dlg.close()


def test_action_dialog_wait_saved(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "wait")

    dlg.spWaitMs.setValue(1500)
    step = dlg.result_step()

    assert step.type == "wait"
    assert step.wait_ms == 1500
    dlg.close()


def test_action_dialog_screen_check_switches_groups(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "screen_check")

    assert dlg.groupPixel.isHidden() is False

    idx = dlg.cbScreenCheckMode.findText("ocr_check_text")
    assert idx >= 0
    dlg.cbScreenCheckMode.setCurrentIndex(idx)
    dlg._refresh_visibility()
    assert dlg.groupOcr.isHidden() is False
    assert dlg.groupPixel.isHidden() is True
    dlg.close()


def test_action_dialog_screen_check_saved(qapp, qtbot):
    from app.core.models import StepData

    steps = [StepData(id="t1", name="Target", type="comment")]
    dlg = _make_dialog(qtbot, steps=steps)
    _set_action_type(dlg, "screen_check")

    idx = dlg.cbScreenCheckMode.findText("ocr_check_text")
    assert idx >= 0
    dlg.cbScreenCheckMode.setCurrentIndex(idx)
    dlg.edOcrExpected.setText("HP")
    dlg.spOcrScale.setValue(3.0)
    dlg.chkOcrInvert.setChecked(True)
    dlg._ocr_roi = (7, 8, 9, 10)
    target_idx = dlg.cbOcrGoto.findData("t1")
    assert target_idx >= 0
    dlg.cbOcrGoto.setCurrentIndex(target_idx)

    step = dlg.result_step()

    assert step.type == "screen_check"
    assert step.screen_check_mode == "ocr_check_text"
    assert step.ocr_expected_text == "HP"
    assert step.ocr_scale == 3.0
    assert step.ocr_invert is True
    assert step.ocr_roi_x == 7
    assert step.ocr_roi_y == 8
    assert step.ocr_roi_w == 9
    assert step.ocr_roi_h == 10
    assert step.on_match_goto_id == "t1"
    dlg.close()


def test_action_dialog_file_action_switches_groups(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "file_action")

    assert dlg.groupLoadData.isHidden() is False

    idx = dlg.cbFileActionMode.findText("run_macro")
    assert idx >= 0
    dlg.cbFileActionMode.setCurrentIndex(idx)
    dlg._refresh_visibility()
    assert dlg.groupRunMacro.isHidden() is False
    assert dlg.groupLoadData.isHidden() is True
    dlg.close()


def test_action_dialog_file_action_saved(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "file_action")

    idx = dlg.cbFileActionMode.findText("run_macro")
    assert idx >= 0
    dlg.cbFileActionMode.setCurrentIndex(idx)
    dlg.edRunMacroPath.setText(r"C:\tmp\macro.json")

    step = dlg.result_step()

    assert step.type == "file_action"
    assert step.file_action_mode == "run_macro"
    assert step.target_macro_path == r"C:\tmp\macro.json"
    dlg.close()


def test_action_dialog_file_action_run_macro_prefills_path(qapp, qtbot):
    from app.core.models import StepData

    step = StepData(id="s1", name="Action", type="file_action")
    step.file_action_mode = "run_macro"
    step.target_macro_path = r"C:\tmp\prefill.json"
    dlg = _make_dialog(qtbot, step=step)
    _set_action_type(dlg, "file_action")

    assert dlg.cbFileActionMode.currentText() == "run_macro"
    assert dlg.edRunMacroPath.text() == r"C:\tmp\prefill.json"
    dlg.close()


def test_action_dialog_compare_images_saved(qapp, qtbot):
    from app.core.models import StepData

    steps = [StepData(id="t1", name="Target", type="comment")]
    dlg = _make_dialog(qtbot, steps=steps)
    _set_action_type(dlg, "compare_images")

    dlg.edCompareImageA.setText(r"C:\tmp\a.png")
    dlg.edCompareImageB.setText(r"C:\tmp\b.png")
    idx_mode = dlg.cbCompareMode.findData("hash")
    assert idx_mode >= 0
    dlg.cbCompareMode.setCurrentIndex(idx_mode)
    dlg.spCompareThreshold.setValue(12.0)
    dlg.spCompareRoiX.setValue(1)
    dlg.spCompareRoiY.setValue(2)
    dlg.spCompareRoiW.setValue(3)
    dlg.spCompareRoiH.setValue(4)
    idx_match = dlg.cbCompareMatchGoto.findData("t1")
    assert idx_match >= 0
    dlg.cbCompareMatchGoto.setCurrentIndex(idx_match)
    idx_fail = dlg.cbCompareFailGoto.findData("t1")
    assert idx_fail >= 0
    dlg.cbCompareFailGoto.setCurrentIndex(idx_fail)

    step = dlg.result_step()

    assert step.type == "compare_images"
    assert step.image_a_path == r"C:\tmp\a.png"
    assert step.image_b_path == r"C:\tmp\b.png"
    assert step.compare_mode == "hash"
    assert step.compare_threshold == 12.0
    assert step.compare_roi_x == 1
    assert step.compare_roi_y == 2
    assert step.compare_roi_w == 3
    assert step.compare_roi_h == 4
    assert step.on_match_goto_id == "t1"
    assert step.branch_on_fail_goto_id == "t1"
    dlg.close()


def test_action_dialog_pick_drag_updates_coordinates(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    points = [QPoint(1, 2), QPoint(3, 4)]

    def fake_select_point(*_args, **_kwargs):
        return points.pop(0)

    monkeypatch.setattr(dialogs, "safe_select_point", fake_select_point)
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "drag")

    dlg._on_pick_drag_from()
    dlg._on_pick_drag_to()

    assert dlg.spDragFromX.value() == 1
    assert dlg.spDragFromY.value() == 2
    assert dlg.spDragToX.value() == 3
    assert dlg.spDragToY.value() == 4
    dlg.close()


def test_action_dialog_pick_ocr_roi_updates_display(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_select_from_screen():
        return QRect(5, 6, 7, 8), None, None

    monkeypatch.setattr(dialogs.ROISelector, "select_from_screen", staticmethod(fake_select_from_screen))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "ocr_check_text")

    dlg._on_pick_ocr_roi()

    assert dlg._ocr_roi == (5, 6, 7, 8)
    assert dlg.edOcrRoiDisplay.text() == "5,6 7x8"
    dlg.close()


def test_action_dialog_pick_ocr_jump_roi_updates_display(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_select_from_screen():
        return QRect(21, 22, 23, 24), None, None

    monkeypatch.setattr(dialogs.ROISelector, "select_from_screen", staticmethod(fake_select_from_screen))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "ocr_jump_if")

    dlg._on_pick_ocr_jump_roi()

    assert dlg._ocr_jump_roi == (21, 22, 23, 24)
    assert dlg.edOcrJumpRoiDisplay.text() == "21,22 23x24"
    dlg.close()


def test_action_dialog_ocr_jump_if_saved(qapp, qtbot):
    from app.core.models import StepData

    steps = [StepData(id="t1", name="Target", type="comment")]
    dlg = _make_dialog(qtbot, steps=steps)
    _set_action_type(dlg, "ocr_jump_if")

    idx = dlg.cbOcrJumpOp.findData(">")
    assert idx >= 0
    dlg.cbOcrJumpOp.setCurrentIndex(idx)
    dlg.edOcrJumpValue.setText("123")
    dlg.spOcrJumpScale.setValue(2.5)
    dlg.chkOcrJumpInvert.setChecked(True)
    dlg._ocr_jump_roi = (1, 2, 3, 4)
    target_idx = dlg.cbOcrJumpTarget.findData(0)
    assert target_idx >= 0
    dlg.cbOcrJumpTarget.setCurrentIndex(target_idx)

    step = dlg.result_step()

    assert step.type == "ocr_jump_if"
    assert step.condition_operator == ">"
    assert step.condition_value == 123.0
    assert step.ocr_scale == 2.5
    assert step.ocr_invert is True
    assert step.ocr_roi_x == 1
    assert step.ocr_roi_y == 2
    assert step.ocr_roi_w == 3
    assert step.ocr_roi_h == 4
    assert step.target_true_index == 0
    assert step.target_true_id == "t1"
    dlg.close()


def test_action_dialog_pick_shot_roi_updates_display(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_select_from_screen():
        return QRect(9, 10, 11, 12), None, None

    monkeypatch.setattr(dialogs.ROISelector, "select_from_screen", staticmethod(fake_select_from_screen))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "screenshot_roi")

    dlg._on_pick_shot_roi()

    assert dlg._screenshot_roi == (9, 10, 11, 12)
    assert dlg.edShotRoiDisplay.text() == "9,10 11x12"
    dlg.close()


def test_action_dialog_pick_ocr_store_roi_updates_display(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_select_from_screen():
        return QRect(13, 14, 15, 16), None, None

    monkeypatch.setattr(dialogs.ROISelector, "select_from_screen", staticmethod(fake_select_from_screen))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "ocr_store")

    dlg._on_pick_ocr_store_roi()

    assert dlg._ocr_store_roi == (13, 14, 15, 16)
    assert dlg.spOcrStoreX.value() == 13
    assert dlg.spOcrStoreY.value() == 14
    assert dlg.spOcrStoreW.value() == 15
    assert dlg.spOcrStoreH.value() == 16
    assert dlg.edOcrStoreRoiDisplay.text() == "13,14 15x16"
    dlg.close()


def test_action_dialog_browse_run_macro_sets_path(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_get_open(*_args, **_kwargs):
        return (r"C:\tmp\sample.macro", "GameBot Files (*.macro)")

    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", staticmethod(fake_get_open))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "run_macro")

    dlg._on_browse_run_macro()

    assert dlg.edRunMacroPath.text() == r"C:\tmp\sample.macro"
    dlg.close()


def test_action_dialog_browse_data_file_sets_path(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    def fake_get_open(*_args, **_kwargs):
        return (r"C:\tmp\data.csv", "CSV Files (*.csv)")

    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", staticmethod(fake_get_open))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "load_data_file")

    dlg._on_browse_data_file()

    assert dlg.edDataFilePath.text() == r"C:\tmp\data.csv"
    dlg.close()


def test_action_dialog_file_action_prefills_recent_paths(qapp, qtbot):
    settings = QSettings("ImageMacro", "MVP")
    prev_macro = settings.value("last_macro_path", "")
    prev_data = settings.value("last_data_file_path", "")
    try:
        settings.setValue("last_macro_path", r"C:\tmp\last.macro")
        settings.setValue("last_data_file_path", r"C:\tmp\data.csv")

        dlg = _make_dialog(qtbot)
        _set_action_type(dlg, "file_action")

        assert dlg.edDataFilePath.text() == r"C:\tmp\data.csv"

        idx = dlg.cbFileActionMode.findText("run_macro")
        assert idx >= 0
        dlg.cbFileActionMode.setCurrentIndex(idx)
        dlg._refresh_visibility()
        assert dlg.edRunMacroPath.text() == r"C:\tmp\last.macro"
        dlg.close()
    finally:
        if prev_macro:
            settings.setValue("last_macro_path", prev_macro)
        else:
            settings.remove("last_macro_path")
        if prev_data:
            settings.setValue("last_data_file_path", prev_data)
        else:
            settings.remove("last_data_file_path")


def test_action_dialog_file_action_legacy_recent_paths_migrate(qapp, qtbot):
    settings = QSettings("ImageMacro", "MVP")
    legacy = QSettings("AutoCording", "MacroTool")
    prev_macro = settings.value("last_macro_path", "")
    prev_data = settings.value("last_data_file_path", "")
    prev_legacy_macro = legacy.value("last_macro_path", "")
    prev_legacy_data = legacy.value("last_data_file_path", "")
    try:
        settings.remove("last_macro_path")
        settings.remove("last_data_file_path")
        legacy.setValue("last_macro_path", r"C:\tmp\legacy_last.macro")
        legacy.setValue("last_data_file_path", r"C:\tmp\legacy_data.csv")

        dlg = _make_dialog(qtbot)
        _set_action_type(dlg, "file_action")

        assert dlg.edDataFilePath.text() == r"C:\tmp\legacy_data.csv"

        idx = dlg.cbFileActionMode.findText("run_macro")
        assert idx >= 0
        dlg.cbFileActionMode.setCurrentIndex(idx)
        dlg._refresh_visibility()
        assert dlg.edRunMacroPath.text() == r"C:\tmp\legacy_last.macro"
        dlg.close()

        assert settings.value("last_macro_path", "") == r"C:\tmp\legacy_last.macro"
        assert settings.value("last_data_file_path", "") == r"C:\tmp\legacy_data.csv"
    finally:
        if prev_macro:
            settings.setValue("last_macro_path", prev_macro)
        else:
            settings.remove("last_macro_path")
        if prev_data:
            settings.setValue("last_data_file_path", prev_data)
        else:
            settings.remove("last_data_file_path")
        if prev_legacy_macro:
            legacy.setValue("last_macro_path", prev_legacy_macro)
        else:
            legacy.remove("last_macro_path")
        if prev_legacy_data:
            legacy.setValue("last_data_file_path", prev_legacy_data)
        else:
            legacy.remove("last_data_file_path")


def test_action_dialog_jump_help_shows_message(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    called = {}

    def fake_info(parent, title, text):
        called["title"] = title
        called["text"] = text
        return None

    monkeypatch.setattr(dialogs.QMessageBox, "information", staticmethod(fake_info))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "jump_if")

    dlg._show_jump_help()

    assert "Jump If" in called.get("title", "")
    assert "OCR" in called.get("text", "")
    dlg.close()


def test_action_dialog_ocr_store_warns_when_roi_missing(monkeypatch, qapp, qtbot):
    import app.ui.dialogs as dialogs

    called = {}

    def fake_warning(parent, title, text):
        called["title"] = title
        called["text"] = text
        return None

    monkeypatch.setattr(dialogs.QMessageBox, "warning", staticmethod(fake_warning))
    dlg = _make_dialog(qtbot)
    _set_action_type(dlg, "ocr_store")

    dlg._on_test_ocr_store()

    assert "OCR Test" in called.get("title", "")
    assert "ROI" in called.get("text", "")
    dlg.close()


def test_action_dialog_preserves_legacy_type(qapp, qtbot):
    from app.core.models import StepData
    from app.ui.dialogs import NotImageDialog

    step = StepData(id="s9", name="Legacy Loop", type="loop")
    dlg = NotImageDialog(step, [])
    qtbot.addWidget(dlg)

    assert "legacy" in dlg.cbType.currentText().lower()
    saved = dlg.result_step()
    assert saved.type == "loop"


def test_action_dialog_maps_legacy_action_to_keyboard(qapp, qtbot):
    from app.core.models import StepData
    from app.ui.dialogs import NotImageDialog

    step = StepData(id="s10", name="Legacy Action", type="action")
    dlg = NotImageDialog(step, [])
    qtbot.addWidget(dlg)

    assert dlg.cbType.currentText() == "keyboard"
    saved = dlg.result_step()
    assert saved.type == "keyboard"
    dlg.close()

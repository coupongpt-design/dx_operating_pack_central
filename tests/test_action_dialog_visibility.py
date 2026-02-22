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


ACTION_GROUP_MAP = [
    ("text", "groupKey"),
    ("key", "groupKey"),
    ("key_down", "groupKey"),
    ("key_up", "groupKey"),
    ("key_hold", "groupKey"),
    ("keyboard", "groupKey"),
    ("mouse", "groupClick"),
    ("click_point", "groupClick"),
    ("drag", "groupDrag"),
    ("scroll", "groupScroll"),
    ("wait", "groupWait"),
    ("screen_check", "groupPixel"),
    ("pixel_check", "groupPixel"),
    ("start_loop", "groupLoop"),
    ("end_loop", "groupLoop"),
    ("compare_images", "groupCompare"),
    ("screenshot_roi", "groupShot"),
    ("comment", "groupComment"),
    ("file_action", "groupLoadData"),
    ("load_data_file", "groupLoadData"),
    ("ocr_check_text", "groupOcr"),
    ("ocr_jump_if", "groupOcrJump"),
    ("ocr_store", "groupOcrStore"),
    ("jump_if", "groupJumpIf"),
    ("run_macro", "groupRunMacro"),
]

ACTION_WIDGET_MAP = [
    ("text", ["edKey", "lblKeyHint"]),
    ("key", ["edKey", "lblKeyHint"]),
    ("key_down", ["edKey", "lblKeyHint"]),
    ("key_up", ["edKey", "lblKeyHint"]),
    ("key_hold", ["edKey", "lblKeyHint"]),
    ("keyboard", ["lblKeyMode", "cbKeyMode", "edKey", "lblKeyHint"]),
    ("mouse", ["lblMouseMode", "cbMouseMode", "spClickX", "spClickY", "btnPickClick"]),
    ("click_point", ["spClickX", "spClickY", "btnPickClick"]),
    ("drag", ["spDragFromX", "spDragFromY", "spDragToX", "spDragToY", "spDragDuration"]),
    ("scroll", ["spScrollDx", "spScrollDy", "spScrollTimes", "spScrollInterval"]),
    ("wait", ["spWaitMs"]),
    ("screen_check", ["lblScreenCheckMode", "cbScreenCheckMode", "spPixelX", "spPixelY",
                      "edPixelHex", "spPixelTol", "cbPixelGoto"]),
    ("pixel_check", ["spPixelX", "spPixelY", "edPixelHex", "spPixelTol", "cbPixelGoto"]),
    ("start_loop", ["spLoopCount", "cbLoopStartRef"]),
    ("end_loop", ["spLoopCount", "cbLoopStartRef"]),
    ("compare_images", [
        "edCompareImageA", "btnCompareImageABrowse",
        "edCompareImageB", "btnCompareImageBBrowse",
        "cbCompareMode", "spCompareThreshold",
        "spCompareRoiX", "spCompareRoiY", "spCompareRoiW", "spCompareRoiH",
        "cbCompareMatchGoto", "cbCompareFailGoto",
    ]),
    ("screenshot_roi", ["edShotPath", "btnShotBrowse", "btnPickShotRoi", "edShotRoiDisplay"]),
    ("comment", ["edComment"]),
    ("file_action", ["lblFileActionMode", "cbFileActionMode", "edDataFilePath", "btnDataFileBrowse"]),
    ("load_data_file", ["edDataFilePath", "btnDataFileBrowse"]),
    ("ocr_check_text", ["edOcrExpected", "edOcrWhitelist", "cbOcrPreprocess",
                        "spOcrScale", "chkOcrInvert", "spOcrTargetHeight", "edOcrLang", "chkOcrDyn",
                        "btnPickOcrRoi", "edOcrRoiDisplay", "cbOcrGoto"]),
    ("ocr_jump_if", ["cbOcrJumpPreprocess", "spOcrJumpScale", "chkOcrJumpInvert", "edOcrJumpLang", "btnPickOcrJumpRoi",
                     "edOcrJumpRoiDisplay", "cbOcrJumpOp", "edOcrJumpValue",
                     "cbOcrJumpTarget", "lblOcrJumpSummary"]),
    ("ocr_store", ["edOcrStoreVar", "spOcrStoreX", "spOcrStoreY", "spOcrStoreW",
                   "spOcrStoreH", "chkOcrStoreInvert", "chkOcrStoreHighContrast",
                   "btnPickOcrStore", "edOcrStoreRoiDisplay",
                   "btnTestOcrStore", "lblTestOcrResult"]),
    ("jump_if", ["edJumpVar", "cbJumpOp", "edJumpValue", "cbJumpTarget",
                 "lblJumpSummary", "btnJumpHelp"]),
    ("run_macro", ["edRunMacroPath", "btnBrowseRunMacro"]),
]


GROUP_ATTRS = [
    "groupKey",
    "groupClick",
    "groupDrag",
    "groupScroll",
    "groupWait",
    "groupPixel",
    "groupLoop",
    "groupCompare",
    "groupShot",
    "groupComment",
    "groupLoadData",
    "groupOcr",
    "groupOcrJump",
    "groupOcrStore",
    "groupJumpIf",
    "groupRunMacro",
]


@pytest.mark.parametrize("action_type, expected_group", ACTION_GROUP_MAP)
def test_action_dialog_visibility(action_type, expected_group, qapp, qtbot):
    from app.ui.dialogs import NotImageDialog
    from app.core.models import StepData

    step = StepData(id="s1", name="Action", type="comment")
    dlg = NotImageDialog(step, [])
    qtbot.addWidget(dlg)

    idx = dlg.cbType.findText(action_type)
    assert idx >= 0
    dlg.cbType.setCurrentIndex(idx)
    dlg._refresh_visibility()

    for name in GROUP_ATTRS:
        widget = getattr(dlg, name, None)
        assert widget is not None
        if name == expected_group:
            assert widget.isHidden() is False
        else:
            assert widget.isHidden() is True

    dlg.close()


@pytest.mark.parametrize("action_type, expected_widgets", ACTION_WIDGET_MAP)
def test_action_dialog_expected_widgets_visible(action_type, expected_widgets, qapp, qtbot):
    from app.ui.dialogs import NotImageDialog
    from app.core.models import StepData

    step = StepData(id="s1", name="Action", type="comment")
    dlg = NotImageDialog(step, [])
    qtbot.addWidget(dlg)

    idx = dlg.cbType.findText(action_type)
    assert idx >= 0
    dlg.cbType.setCurrentIndex(idx)
    dlg._refresh_visibility()

    for name in expected_widgets:
        widget = getattr(dlg, name, None)
        assert widget is not None
        assert widget.isHidden() is False

    dlg.close()


def test_jump_if_variable_suggestions_include_ocr_store(qapp, qtbot):
    from app.ui.dialogs import NotImageDialog
    from app.core.models import StepData

    ocr_step = StepData(id="ocr1", name="HP", type="ocr_store")
    setattr(ocr_step, "ocr_store_var", "hp")
    step = StepData(id="s1", name="Action", type="comment")
    dlg = NotImageDialog(step, [ocr_step])
    qtbot.addWidget(dlg)

    idx = dlg.cbType.findText("jump_if")
    assert idx >= 0
    dlg.cbType.setCurrentIndex(idx)
    dlg._refresh_visibility()

    items = [dlg.edJumpVar.itemText(i) for i in range(dlg.edJumpVar.count())]
    assert "loop_index" in items
    assert "loop_count" in items
    assert "hp" in items

    dlg.close()

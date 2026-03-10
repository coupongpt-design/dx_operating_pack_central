import os
import sys
from types import SimpleNamespace

import pytest
import numpy as np
pytest.importorskip("pytestqt")
from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication, QScrollArea, QTabWidget

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


def _make_dialog(qtbot, step=None):
    from app.ui.dialogs import ImageStepDialog
    from app.core.models import StepData

    if step is None:
        step = StepData(id="img1", name="Image", type="image_click")
    dlg = ImageStepDialog(step)
    qtbot.addWidget(dlg)
    return dlg


def test_auto_fg_preset_applies_stable_values(qapp, qtbot):
    dlg = _make_dialog(qtbot)

    idx = dlg.cbAutoFgPreset.findData("stable")
    assert idx >= 0
    dlg.cbAutoFgPreset.setCurrentIndex(idx)

    assert dlg.spAutoFgPct.value() == pytest.approx(80.0, abs=1e-6)
    assert dlg.spAutoFgScale.value() == pytest.approx(0.9, abs=1e-6)
    assert dlg.spAutoFgMinDist.value() == pytest.approx(18.0, abs=1e-6)
    assert dlg.chkAutoFgMask.isChecked() is True
    dlg.close()


def test_auto_fg_tune_change_sets_custom_preset(qapp, qtbot):
    dlg = _make_dialog(qtbot)

    idx = dlg.cbAutoFgPreset.findData("aggressive")
    assert idx >= 0
    dlg.cbAutoFgPreset.setCurrentIndex(idx)
    assert dlg.cbAutoFgPreset.currentData() == "aggressive"

    dlg.spAutoFgMinDist.setValue(7.0)
    assert dlg.cbAutoFgPreset.currentData() == "custom"
    dlg.close()


def test_auto_fg_preset_persists_on_accept(qapp, qtbot):
    from app.core.models import StepData

    step = StepData(id="img2", name="Image", type="image_click")
    dlg = _make_dialog(qtbot, step=step)

    idx = dlg.cbAutoFgPreset.findData("aggressive")
    assert idx >= 0
    dlg.cbAutoFgPreset.setCurrentIndex(idx)
    dlg.spAutoFgStdLow.setValue(12.0)
    dlg.spAutoFgStdHigh.setValue(36.0)
    dlg.spAutoFgEdgeLow.setValue(0.05)
    dlg.spAutoFgEdgeHigh.setValue(0.18)
    dlg.accept()
    saved = dlg.get_step_data()

    assert saved.auto_fg_mask_enable is True
    assert saved.auto_fg_mask_bg_percentile == pytest.approx(60.0, abs=1e-6)
    assert saved.auto_fg_mask_dynamic_scale == pytest.approx(0.35, abs=1e-6)
    assert saved.auto_fg_mask_min_distance == pytest.approx(6.0, abs=1e-6)
    assert saved.auto_fg_suggest_std_low == pytest.approx(12.0, abs=1e-6)
    assert saved.auto_fg_suggest_std_high == pytest.approx(36.0, abs=1e-6)
    assert saved.auto_fg_suggest_edge_low == pytest.approx(0.05, abs=1e-6)
    assert saved.auto_fg_suggest_edge_high == pytest.approx(0.18, abs=1e-6)


def test_auto_fg_preset_hint_updates(qapp, qtbot):
    dlg = _make_dialog(qtbot)

    idx = dlg.cbAutoFgPreset.findData("stable")
    assert idx >= 0
    dlg.cbAutoFgPreset.setCurrentIndex(idx)
    assert "conservative" in dlg.lblAutoFgPresetHint.text().lower()
    dlg.close()


def test_auto_fg_suggest_preset_applies_stable(qapp, qtbot):
    from app.core.models import StepData

    step = StepData(id="img3", name="Image", type="image_click")
    step._tpl_bgr = np.zeros((20, 20, 3), dtype=np.uint8) + 25
    dlg = _make_dialog(qtbot, step=step)

    dlg._on_suggest_auto_fg_preset()
    assert dlg.cbAutoFgPreset.currentData() == "stable"
    assert dlg.chkAutoFgMask.isChecked() is True
    txt = dlg.lblAutoFgSuggestInfo.text().lower()
    assert "confidence" in txt
    assert "stable" in txt
    dlg.close()


def test_auto_fg_recommendation_detects_aggressive(qapp, qtbot):
    dlg = _make_dialog(qtbot)

    checker = np.indices((40, 40)).sum(axis=0) % 2
    checker = (checker * 255).astype(np.uint8)
    tpl = np.stack([checker, checker, checker], axis=2)
    key = dlg._recommend_auto_fg_preset_for_template(tpl)
    assert key == "aggressive"
    dlg.close()


def test_auto_fg_suggest_thresholds_change_recommendation(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    tpl = np.zeros((24, 24, 3), dtype=np.uint8) + 25

    assert dlg._recommend_auto_fg_preset_for_template(tpl) == "stable"
    dlg.spAutoFgStdLow.setValue(0.0)
    dlg.spAutoFgEdgeLow.setValue(0.0)
    assert dlg._recommend_auto_fg_preset_for_template(tpl) == "accurate"
    dlg.close()


def test_auto_fg_suggest_without_template_shows_message(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    dlg._step._tpl_bgr = None
    dlg._step.png_bytes = None

    dlg._on_suggest_auto_fg_preset()
    assert "load or capture" in dlg.lblAutoFgSuggestInfo.text().lower()
    dlg.close()


def test_auto_fg_recommendation_details_returns_confidence(qapp, qtbot):
    dlg = _make_dialog(qtbot)
    tpl = np.zeros((24, 24, 3), dtype=np.uint8) + 20
    tpl[6:18, 6:18, :] = 80

    key, conf, std, edge = dlg._recommend_auto_fg_preset_details(tpl)
    assert key in {"stable", "accurate", "aggressive"}
    assert 55 <= conf <= 95
    assert std >= 0.0
    assert edge >= 0.0
    dlg.close()


def test_relative_target_settings_persist_on_accept(qapp, qtbot):
    from app.core.models import StepData

    step = StepData(id="img-rel", name="Image", type="image_click")
    dlg = _make_dialog(qtbot, step=step)

    dlg.chkRelativeTarget.setChecked(True)
    dlg.edRelativeTargetPath.setText("C:/tmp/target.png")
    dlg._step.relative_target_png_bytes = b"png"
    dlg.spRelativeLeft.setValue(12)
    dlg.spRelativeTop.setValue(3)
    dlg.spRelativeRight.setValue(44)
    dlg.spRelativeBottom.setValue(8)
    dlg.accept()
    saved = dlg.get_step_data()

    assert saved.relative_target_enabled is True
    assert saved.relative_target_image_path == "C:/tmp/target.png"
    assert saved.relative_search_left == 12
    assert saved.relative_search_top == 3
    assert saved.relative_search_right == 44
    assert saved.relative_search_bottom == 8


def test_matching_tab_is_scrollable_and_keeps_button_box_visible(qapp, qtbot):
    dlg = _make_dialog(qtbot)

    dlg.show()
    qtbot.wait(50)
    tabs = dlg.findChild(QTabWidget)
    assert tabs is not None
    matching_index = next(i for i in range(tabs.count()) if tabs.tabText(i) == "Matching")
    tabs.setCurrentIndex(matching_index)
    qapp.processEvents()

    matching_page = tabs.widget(matching_index)
    assert isinstance(matching_page, QScrollArea)
    assert matching_page.widget() is not None

    screen = qapp.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()
    assert dlg.height() <= available.height()
    assert dlg.buttonBox.geometry().bottom() <= dlg.rect().bottom()
    dlg.close()


def test_capture_relative_target_updates_embedded_target(qapp, qtbot, monkeypatch):
    import app.ui.dialogs as dialogs

    dlg = _make_dialog(qtbot)
    crop = np.zeros((6, 8, 3), dtype=np.uint8)
    monkeypatch.setattr(
        dialogs.ROISelector,
        "select_from_screen",
        staticmethod(lambda parent=None: (QRect(10, 12, 8, 6), crop, (0, 0, 100, 100))),
    )

    dlg._on_capture_relative_target()

    assert dlg.chkRelativeTarget.isChecked() is True
    assert dlg._step.relative_target_png_bytes is not None
    assert dlg._step.relative_target_image_path is None
    assert "captured from screen" in dlg.lblRelativeTargetSource.text().lower()
    dlg.close()


def test_capture_relative_target_keeps_dialog_visible(qapp, qtbot, monkeypatch):
    import app.ui.dialogs as dialogs

    dlg = _make_dialog(qtbot)
    dlg.show()
    qapp.processEvents()

    def _fake_select_from_screen(parent=None):
        assert parent is dlg
        crop = np.zeros((6, 8, 3), dtype=np.uint8)
        return QRect(10, 12, 8, 6), crop, (0, 0, 100, 100)

    monkeypatch.setattr(
        dialogs.ROISelector,
        "select_from_screen",
        staticmethod(_fake_select_from_screen),
    )

    dlg._on_capture_relative_target()
    qapp.processEvents()

    assert dlg.isVisible() is True
    assert dlg.buttonBox.isVisible() is True
    dlg.close()


def test_pick_relative_search_area_updates_margins_from_selection(qapp, qtbot, monkeypatch):
    import app.ui.dialogs as dialogs

    dlg = _make_dialog(qtbot)
    dlg._step.png_bytes = b"anchor"
    dlg._step._tpl_bgr = np.zeros((6, 10, 3), dtype=np.uint8)

    class _DummyMSS:
        def __enter__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 100, "height": 80}]
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def grab(self, region):
            return np.zeros((80, 100, 4), dtype=np.uint8)

    monkeypatch.setattr(dialogs.mss, "mss", lambda: _DummyMSS())
    monkeypatch.setattr(
        dialogs.Matcher,
        "find_best_optimized",
        lambda self, frame, step: SimpleNamespace(ok=True, x=30, y=30, score=0.99, w=10, h=6),
    )
    monkeypatch.setattr(
        dialogs.ROISelector,
        "select_from_screen",
        staticmethod(lambda parent=None: (QRect(10, 15, 50, 25), None, (0, 0, 100, 80))),
    )

    dlg._on_pick_relative_search_area()

    assert dlg.spRelativeLeft.value() == 15
    assert dlg.spRelativeTop.value() == 12
    assert dlg.spRelativeRight.value() == 25
    assert dlg.spRelativeBottom.value() == 7
    assert "L 15" in dlg.lblRelativeSearchSummary.text()
    dlg.close()

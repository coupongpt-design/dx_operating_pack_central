import os
import sys

import pytest
import numpy as np
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

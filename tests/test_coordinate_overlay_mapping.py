import os
import sys

import pytest

pytest.importorskip("pytestqt")
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_coordinate_overlay_show_marker_stores_payload(qapp, qtbot):
    from app.ui.overlay import CoordinateGuideOverlay

    overlay = CoordinateGuideOverlay()
    qtbot.addWidget(overlay)

    overlay.show_marker(120, 240, 5, "image_click", bbox=(100, 200, 40, 30))

    assert overlay._marker_visible is True
    assert overlay._marker_global == (120, 240)
    assert overlay._last_marker.get("step_idx") == 5
    assert overlay._last_marker.get("step_type") == "image_click"
    assert isinstance(overlay._last_marker.get("local"), QPoint)
    assert overlay._last_marker.get("bbox_local") is not None

    overlay.clear_marker()
    assert overlay._marker_visible is False
    assert overlay._last_marker == {}


def test_coordinate_overlay_has_transparent_mouse_passthrough(qapp, qtbot):
    from app.ui.overlay import CoordinateGuideOverlay

    overlay = CoordinateGuideOverlay()
    qtbot.addWidget(overlay)

    assert overlay.testAttribute(Qt.WA_TransparentForMouseEvents) is True


def test_coordinate_overlay_shared_instance_reuse(qapp):
    from app.ui.overlay import CoordinateGuideOverlay

    a = CoordinateGuideOverlay.get_shared()
    b = CoordinateGuideOverlay.get_shared()
    assert a is b

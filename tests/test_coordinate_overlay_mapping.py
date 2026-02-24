import os
import sys

import pytest

pytest.importorskip("pytestqt")
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QSignalSpy
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


def test_step_list_coordinate_preview_signal_on_selection(qapp, qtbot):
    from app.core.models import StepData
    from app.ui.widgets import StepList

    lst = StepList()
    qtbot.addWidget(lst)

    step = StepData(
        id="s1",
        name="Click Step",
        type="click_point",
        click_x=321,
        click_y=654,
        image_path="images/sample.png",
    )
    lst.add_step_item(step)

    requested_spy = QSignalSpy(lst.coordinatePreviewRequested)
    cleared_spy = QSignalSpy(lst.coordinatePreviewCleared)

    lst.setCurrentRow(0)
    qtbot.waitUntil(lambda: len(requested_spy) >= 1, timeout=1000)

    payload = requested_spy[-1][0]
    assert payload["x"] == 321
    assert payload["y"] == 654
    assert payload["index"] == 1
    assert payload["type"] == "click_point"
    assert payload["image_path"] == "images/sample.png"
    assert len(cleared_spy) == 0


def test_step_list_coordinate_preview_cleared_on_non_coordinate_selection(qapp, qtbot):
    from app.core.models import StepData
    from app.ui.widgets import StepList

    lst = StepList()
    qtbot.addWidget(lst)

    coord_step = StepData(
        id="s1",
        name="Coord",
        type="click_point",
        click_x=10,
        click_y=20,
    )
    non_coord_step = StepData(
        id="s2",
        name="Wait",
        type="wait",
        wait_ms=500,
    )
    lst.add_step_item(coord_step)
    lst.add_step_item(non_coord_step)

    requested_spy = QSignalSpy(lst.coordinatePreviewRequested)
    cleared_spy = QSignalSpy(lst.coordinatePreviewCleared)

    lst.setCurrentRow(0)
    qtbot.waitUntil(lambda: len(requested_spy) >= 1, timeout=1000)

    lst.setCurrentRow(1)
    qtbot.waitUntil(lambda: len(cleared_spy) >= 1, timeout=1000)

import os
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("pytestqt")
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QImage
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


def test_mainwindow_routes_coordinate_preview_to_overlay(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow

    overlay_calls = {"show": [], "clear": 0}

    class _FakeOverlay:
        def show_marker(self, x, y, step_idx, step_type, bbox=None):
            overlay_calls["show"].append((x, y, step_idx, step_type, bbox))

        def clear_marker(self):
            overlay_calls["clear"] += 1

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win._coordinate_overlay = _FakeOverlay()
    step = StepData(id="s1", name="Click", type="click_point", click_x=111, click_y=222)
    win.steps = [step]
    win.refresh_step_list()

    win.list.setCurrentRow(0)
    qapp.processEvents()

    assert overlay_calls["show"], "overlay.show_marker should be called from StepList selection routing"
    x, y, idx, stype, bbox = overlay_calls["show"][-1]
    assert (x, y, idx, stype) == (111, 222, 1, "click_point")
    assert bbox is None

    win.close()


def test_mainwindow_coordinate_preview_guard_blocks_when_running(monkeypatch, qapp, qtbot):
    from app.main import MainWindow

    class _FakeOverlay:
        def __init__(self):
            self.show_count = 0

        def show_marker(self, *args, **kwargs):
            self.show_count += 1

        def clear_marker(self):
            pass

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    fake_overlay = _FakeOverlay()
    win._coordinate_overlay = fake_overlay

    payload = {"x": 10, "y": 20, "index": 1, "type": "click_point"}

    win._excel_mode_running = True
    win._on_coordinate_preview_requested(payload)
    assert fake_overlay.show_count == 0

    win._excel_mode_running = False
    win.runner = SimpleNamespace(isRunning=lambda: True)
    win._on_coordinate_preview_requested(payload)
    assert fake_overlay.show_count == 0

    win.runner = None
    win._on_coordinate_preview_requested(payload)
    assert fake_overlay.show_count == 1

    win.close()


def test_mainwindow_image_click_preview_passes_bbox_from_image(monkeypatch, qapp, qtbot, tmp_path):
    from app.core.models import StepData
    from app.main import MainWindow

    class _FakeOverlay:
        def __init__(self):
            self.last = None

        def show_marker(self, x, y, step_idx, step_type, bbox=None):
            self.last = (x, y, step_idx, step_type, bbox)

        def clear_marker(self):
            pass

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    img_path = tmp_path / "anchor.png"
    img = QImage(24, 12, QImage.Format_ARGB32)
    img.fill(0xFF00FF00)
    assert img.save(str(img_path))

    win._coordinate_overlay = _FakeOverlay()
    step = StepData(
        id="s1",
        name="ImageClick",
        type="image_click",
        click_x=300,
        click_y=400,
        image_path=str(img_path),
    )
    win.steps = [step]
    win.refresh_step_list()

    win.list.setCurrentRow(0)
    qapp.processEvents()

    assert win._coordinate_overlay.last is not None
    x, y, idx, stype, bbox = win._coordinate_overlay.last
    assert (x, y, idx, stype) == (300, 400, 1, "image_click")
    assert bbox == (24, 12)

    win.close()

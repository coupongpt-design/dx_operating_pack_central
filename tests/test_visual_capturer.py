import os
import sys

import pytest

pytest.importorskip("pytestqt")
np = pytest.importorskip("numpy")
from PyQt5.QtCore import QRect
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


def test_visual_capture_creates_image_click_step_with_coordinates(monkeypatch, tmp_path, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow
    from app.ui.overlay import VisualImageCaptureOverlay

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(
        MainWindow,
        "_resolve_visual_capture_image_dir",
        lambda self: str(tmp_path),
        raising=False,
    )

    rect = QRect(10, 20, 40, 30)
    crop = np.zeros((30, 40, 3), dtype=np.uint8)
    crop[:, :] = (10, 20, 200)
    virt = (-100, 200, 1920, 1080)
    monkeypatch.setattr(
        VisualImageCaptureOverlay,
        "capture_from_screen",
        staticmethod(lambda parent=None: (rect, crop, virt)),
        raising=False,
    )

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    base = StepData(id="base1", name="base", type="comment", comment="")
    win.steps = [base]
    win.refresh_step_list()
    win.list.setCurrentRow(0)

    win._run_visual_capture("image_click")

    assert len(win.steps) == 2
    new_step = win.steps[1]
    assert new_step.type == "image_click"
    assert new_step.click_x == -70
    assert new_step.click_y == 235
    assert isinstance(new_step.png_bytes, (bytes, bytearray))
    assert new_step.anchor_image_path
    assert os.path.exists(new_step.anchor_image_path)
    assert os.path.commonpath([str(tmp_path), new_step.anchor_image_path]) == str(tmp_path)
    with open(new_step.anchor_image_path, "rb") as fp:
        saved = fp.read()
    assert saved == new_step.png_bytes

    win.close()


def test_visual_capture_cancel_keeps_steps_unchanged(monkeypatch, tmp_path, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow
    from app.ui.overlay import VisualImageCaptureOverlay

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(
        MainWindow,
        "_resolve_visual_capture_image_dir",
        lambda self: str(tmp_path),
        raising=False,
    )
    monkeypatch.setattr(
        VisualImageCaptureOverlay,
        "capture_from_screen",
        staticmethod(lambda parent=None: (QRect(), None, (0, 0, 100, 100))),
        raising=False,
    )

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()

    win.steps = [StepData(id="s1", name="one", type="comment", comment="")]
    win.refresh_step_list()
    before = len(win.steps)
    win._run_visual_capture("wait_for_image")

    assert len(win.steps) == before
    assert list(tmp_path.iterdir()) == []

    win.close()


def test_visual_capture_blocked_while_running(monkeypatch, qapp, qtbot):
    from app.core.models import StepData
    from app.main import MainWindow
    from app.ui.overlay import VisualImageCaptureOverlay

    class _DummyRunner:
        def isRunning(self):
            return True

    called = {"capture": 0}

    def _capture_stub(parent=None):
        called["capture"] += 1
        return QRect(), None, (0, 0, 100, 100)

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)
    monkeypatch.setattr(
        VisualImageCaptureOverlay,
        "capture_from_screen",
        staticmethod(_capture_stub),
        raising=False,
    )

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win.runner = _DummyRunner()
    win.steps = [StepData(id="s1", name="one", type="comment", comment="")]
    win.refresh_step_list()

    win._run_visual_capture("image_click")

    assert len(win.steps) == 1
    assert called["capture"] == 0

    win.close()

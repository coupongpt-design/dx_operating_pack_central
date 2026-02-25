import os

import pytest
pytest.importorskip("pytestqt")

from PyQt5.QtWidgets import QApplication

from app.core.commands import AddRecordedStepsCommand, UndoStack
from app.core.models import StepData
from app.core.smart_recorder import SmartProposal


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_record_cancel_cleans_record_prop_images(monkeypatch, qapp, qtbot, tmp_path):
    from app.main import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_global_hotkey_engine", lambda self: None, raising=False)

    img_path = tmp_path / "record_prop_cancel.png"
    img_path.write_bytes(b"temp-bytes")

    click_step = StepData(id="c1", name="click", type="click_point", click_x=10, click_y=20)
    image_step = StepData(
        id="i1",
        name="img",
        type="image_click",
        image_path=str(img_path),
        anchor_image_path=str(img_path),
        png_bytes=b"temp-bytes",
        click_x=10,
        click_y=20,
    )
    proposal = SmartProposal(
        event_timestamp=1.0,
        x=10,
        y=20,
        click_step=click_step,
        image_step=image_step,
        image_path=str(img_path),
    )

    win = MainWindow()
    qtbot.addWidget(win)
    win.hide()
    win._record_show_summary = False
    win._smart_transformer = None
    win._record_smart_events = [proposal]
    win._record_temp_image_paths = [str(img_path)]
    win._choose_record_proposal_mode = lambda _n: "cancel"

    win._on_record_done([])

    assert len(win.steps) == 0
    assert not img_path.exists()
    win.close()


def test_add_recorded_steps_command_undo_redo_restores_image_file(tmp_path):
    img_path = tmp_path / "record_prop_undo.png"
    initial_bytes = b"record-temp-image"
    img_path.write_bytes(initial_bytes)

    steps: list[StepData] = []
    image_step = StepData(
        id="img1",
        name="Image",
        type="image_click",
        image_path=str(img_path),
        anchor_image_path=str(img_path),
        png_bytes=initial_bytes,
        click_x=1,
        click_y=2,
    )

    stack = UndoStack()
    stack.push(
        AddRecordedStepsCommand(
            steps,
            [image_step],
            index=0,
            managed_image_paths=[str(img_path)],
        )
    )
    assert len(steps) == 1
    assert os.path.exists(img_path)

    stack.undo()
    assert len(steps) == 0
    assert not os.path.exists(img_path)

    stack.redo()
    assert len(steps) == 1
    assert os.path.exists(img_path)
    assert img_path.read_bytes() == initial_bytes

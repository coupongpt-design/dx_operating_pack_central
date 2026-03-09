import os

import pytest
pytest.importorskip("pytestqt")

from PyQt5.QtWidgets import QApplication

from app.core.commands import AddRecordedStepsCommand, UndoStack
from app.core.models import StepData


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


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

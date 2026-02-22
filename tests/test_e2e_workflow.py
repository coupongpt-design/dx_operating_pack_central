import json
import os
from types import SimpleNamespace

import pytest

from app.core.commands import AddStepCommand
from app.core.models import RepeatConfig, StepData
from app.main import MainWindow


class _FakeRunner:
    def __init__(self, steps, **kwargs):
        self.steps = steps
        self.kwargs = kwargs
        self.started = False
        self.log = SimpleNamespace(connect=lambda *a, **k: None)
        self.finished = SimpleNamespace(connect=lambda *a, **k: None)

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started


def _rebuild_list_ui(mw: MainWindow):
    if hasattr(mw, "list"):
        mw.list.clear()
        for s in mw.steps:
            mw.add_list_item(s)


def test_e2e_architect_edit_save(tmp_path, monkeypatch, qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.steps = []
    if hasattr(mw, "list"):
        mw.list.clear()

    # Add OCR step
    s1 = StepData(id="s1", name="OCR Store", type="ocr_store", ocr_store_var="hp")
    mw.undo_stack.push(AddStepCommand(mw.steps, s1))
    mw.add_list_item(s1)

    # Add Jump step
    s2 = StepData(id="s2", name="Jump", type="jump_if", condition_var="hp", condition_operator="<", condition_value=50)
    mw.undo_stack.push(AddStepCommand(mw.steps, s2))
    mw.add_list_item(s2)
    assert len(mw.steps) == 2

    # Undo jump
    mw.undo_stack.undo()
    assert len(mw.steps) == 1
    _rebuild_list_ui(mw)

    # Redo jump
    mw.undo_stack.redo()
    assert len(mw.steps) == 2
    _rebuild_list_ui(mw)

    # Set target window and save
    if hasattr(mw, "edTargetTitle"):
        mw.edTargetTitle.setText("MapleStory")
    save_path = tmp_path / "temp_test.json"
    monkeypatch.setattr("app.main.QFileDialog.getSaveFileName", lambda *a, **k: (str(save_path), None))
    mw.save_macro()

    data = json.loads(save_path.read_text(encoding="utf-8"))
    assert data.get("meta", {}).get("target_window") == "MapleStory"


def test_e2e_commander_load_run(tmp_path, monkeypatch, qtbot):
    # Prepare saved file with target window
    save_path = tmp_path / "temp_test.json"
    payload = {
        "meta": {"version": "1.0", "target_window": "MapleStory"},
        "repeat": RepeatConfig().__dict__,
        "steps": [StepData(id="s1", name="Comment", type="comment").__dict__],
    }
    save_path.write_text(json.dumps(payload), encoding="utf-8")

    # Fake runner and window manager
    calls = {"find": 0, "activate": 0, "runner_init": False, "runner_start": False}

    def fake_find(title):
        calls["find"] += 1
        return 123

    def fake_activate(hwnd):
        calls["activate"] += 1

    monkeypatch.setattr("app.main.MacroRunner", lambda steps, **kw: _FakeRunner(steps, **kw))

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.window_manager = SimpleNamespace(find_window=fake_find, activate_window=fake_activate)

    # Load
    monkeypatch.setattr("app.main.QFileDialog.getOpenFileName", lambda *a, **k: (str(save_path), None))
    mw.load_macro()
    if hasattr(mw, "edTargetTitle"):
        assert mw.edTargetTitle.text() == "MapleStory"

    # Run (uses fake runner)
    mw.run_macro()
    # ensure window activation attempted
    assert calls["find"] == 1
    assert calls["activate"] == 1

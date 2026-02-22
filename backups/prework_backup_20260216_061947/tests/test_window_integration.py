import json
import os
import sys
from types import SimpleNamespace

import pytest

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.models import RepeatConfig, StepData  # noqa: E402
from app.core.runner import MacroRunner  # noqa: E402
from app.main import MainWindow  # noqa: E402


# ---------------- Metadata Save/Load ----------------
def test_save_metadata(tmp_path, monkeypatch, qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.edTargetTitle.setText("MapleStory")
    # avoid dialog UI
    save_path = tmp_path / "out.json"
    monkeypatch.setattr("app.main.QFileDialog.getSaveFileName", lambda *a, **k: (str(save_path), None))
    mw.steps = []
    mw.save_macro()
    data = json.loads(save_path.read_text(encoding="utf-8"))
    assert data.get("meta", {}).get("target_window") == "MapleStory"


def test_load_metadata(tmp_path, monkeypatch, qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    meta_path = tmp_path / "meta.json"
    meta = {"meta": {"target_window": "Notepad"}, "repeat": RepeatConfig().__dict__, "steps": []}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr("app.main.QFileDialog.getOpenFileName", lambda *a, **k: (str(meta_path), None))
    mw.load_macro()
    assert mw.edTargetTitle.text() == "Notepad"


# ---------------- Runner Safety ----------------
class _DummyMSS:
    monitors = [{"left": 0, "top": 0, "width": 1, "height": 1}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def grab(self, region):
        return None


def test_runner_skips_if_no_title(monkeypatch):
    step = StepData(id="s0", name="noop", type="comment")
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True, target_window_title="")
    dummy_wm = SimpleNamespace(find_window=pytest.fail, activate_window=pytest.fail)
    runner._window_manager = dummy_wm  # type: ignore
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=lambda: _DummyMSS()))
    # prevent actual step execution
    runner._exec_step = lambda sct, mon, st, idx: (True, None, 0)  # type: ignore
    runner.run()


def test_runner_continues_if_window_not_found(monkeypatch):
    step = StepData(id="s0", name="noop", type="comment")
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=True, target_window_title="LostGame")
    calls = {"exec": 0, "find": 0}

    def fake_find(title):
        calls["find"] += 1
        return None

    runner._window_manager = SimpleNamespace(find_window=fake_find, activate_window=lambda *a, **k: None)  # type: ignore
    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=lambda: _DummyMSS()))

    def fake_exec(sct, mon, st, idx):
        calls["exec"] += 1
        return True, None, 0

    runner._exec_step = fake_exec  # type: ignore
    runner.run()
    assert calls["find"] == 1
    assert calls["exec"] == 1

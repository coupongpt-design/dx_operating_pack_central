from app.core.models import RepeatConfig, StepData
from app.core.runner import MacroRunner


def test_drag_path_human_uses_human_mouse(monkeypatch):
    step = StepData(
        id="d1",
        name="Drag Path",
        type="drag_path",
        drag_path=[(0, 0, 0.0), (10, 10, 0.1)],
    )
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=False, human_mode=True)

    called = {}

    def fake_drag_path(points, button="left"):
        called["points"] = points
        called["button"] = button

    runner._human_mouse.drag_path = fake_drag_path  # type: ignore

    ok = runner._drag_path(step)

    assert ok is True
    assert called.get("points")
    assert called.get("button") == "left"

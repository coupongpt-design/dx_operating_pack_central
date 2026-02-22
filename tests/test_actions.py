import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.input_emulator import HumanMouse


def test_human_mouse_click_and_move(monkeypatch):
    calls = {}

    def fake_moveTo(x, y, duration=None, _pause=True):
        calls["move"] = (x, y, duration)

    def fake_click(x=None, y=None, _pause=True):
        calls["click"] = (x, y)

    monkeypatch.setattr(
        "app.core.input_emulator.pyautogui",
        SimpleNamespace(
            moveTo=fake_moveTo,
            click=fake_click,
            mouseDown=lambda *a, **k: calls.setdefault("down", True),
            mouseUp=lambda *a, **k: calls.setdefault("up", True),
            position=lambda: (0, 0),
            FAILSAFE=True,
        ),
    )

    hm = HumanMouse(stop_flag=lambda: False, respect_failsafe=True)
    hm.move_to(100, 200, duration=0.1)
    hm.click(100, 200)

    # Duration may be auto-computed and HumanMouse adds jitter; allow small offset.
    assert calls.get("move")
    mx, my, _ = calls["move"]
    assert abs(mx - 100) <= 3 and abs(my - 200) <= 3
    # Implementation may use mouseDown/Up without click; accept either.
    if calls.get("click") is not None:
        assert calls["click"][0:2] == (100, 200)
    else:
        assert calls.get("down") and calls.get("up")


def test_human_mouse_drag(monkeypatch):
    calls = {}

    def fake_moveTo(x, y, duration=None, _pause=True):
        calls.setdefault("path", []).append((x, y, duration))

    def fake_dragTo(x, y, duration=None, button="left", _pause=True):
        calls["drag"] = (x, y, duration, button)

    def fake_mouseDown(button="left", _pause=True):
        calls["down"] = button

    def fake_mouseUp(button="left", _pause=True):
        calls["up"] = button

    monkeypatch.setattr(
        "app.core.input_emulator.pyautogui",
        SimpleNamespace(
            moveTo=fake_moveTo,
            dragTo=fake_dragTo,
            mouseDown=fake_mouseDown,
            mouseUp=fake_mouseUp,
            position=lambda: (0, 0),
            FAILSAFE=True,
        ),
    )

    hm = HumanMouse(stop_flag=lambda: False, respect_failsafe=True)
    hm.drag(0, 0, 10, 20, duration=0.2)

    assert "path" in calls and len(calls["path"]) > 0
    # Implementation may use mouseDown/move/mouseUp instead of dragTo; allow either.
    if calls.get("drag") is not None:
        assert calls["drag"][0:3] == (10, 20, 0.2)
    else:
        assert calls.get("down") == "left"
        assert calls.get("up") == "left"
        # Last move should end near target.
        last_move = calls.get("path", [])[-1]
        assert last_move[0:2] == (10, 20)


def test_keyboard_press(monkeypatch):
    pressed = []

    def fake_press(key, _pause=True):
        pressed.append(key)

    monkeypatch.setattr(
        "app.core.runner.pyautogui",
        SimpleNamespace(press=fake_press, hscroll=lambda *a, **k: None, scroll=lambda *a, **k: None),
    )

    # Use MacroRunner key handler indirectly via step handler map
    from app.core.runner import MacroRunner
    from app.core.models import StepData, RepeatConfig

    step = StepData(id="k1", name="KeyPress", type="key", key_string="F2")
    runner = MacroRunner([step], repeat=RepeatConfig(repeat_count=1), dry_run=False)
    class DummyMSS:
        monitors = [
            {"left": 0, "top": 0, "width": 1, "height": 1},
            {"left": 0, "top": 0, "width": 1, "height": 1},
        ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def grab(self, region):
            return None

    monkeypatch.setattr("app.core.runner.mss", SimpleNamespace(mss=lambda: DummyMSS()))
    runner.run()

    assert pressed == ["f2"] or pressed == ["F2"]

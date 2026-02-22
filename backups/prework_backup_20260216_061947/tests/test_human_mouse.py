import os
import sys
import types
from unittest.mock import call

import pytest

# Ensure repository root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.input_emulator import HumanMouse


class DummyPyAuto:
    def __init__(self):
        self.moves = []
        self.downs = []
        self.ups = []
        self.clicks = []
        self.pos = (0, 0)
        self.FAILSAFE = True

    def position(self):
        return self.pos

    def moveTo(self, x, y):
        self.pos = (x, y)
        self.moves.append((x, y))

    def mouseDown(self, button="left"):
        self.downs.append(button)

    def mouseUp(self, button="left"):
        self.ups.append(button)

    def click(self, x=None, y=None, clicks=1, interval=0.0, button="left"):
        self.clicks.append((x, y, clicks, button))


def test_move_to_generates_curve(monkeypatch):
    fake = DummyPyAuto()
    # Patch pyautogui module used inside HumanMouse
    monkeypatch.setattr("app.core.input_emulator.pyautogui", fake)
    hm = HumanMouse(stop_flag=lambda: False, respect_failsafe=False)
    hm.move_to(100, 50, duration=0.01)  # very short duration for test
    # Should record multiple move points and end near target
    assert len(fake.moves) > 2
    assert fake.moves[-1][0] in range(90, 111)
    assert fake.moves[-1][1] in range(40, 61)


def test_click_calls_move_and_press(monkeypatch):
    fake = DummyPyAuto()
    monkeypatch.setattr("app.core.input_emulator.pyautogui", fake)
    hm = HumanMouse(stop_flag=lambda: False, respect_failsafe=False)
    hm.click(10, 10, button="left", double=False, hold_sec=0.0)
    # Should have moved and produced down/up
    assert fake.moves, "moveTo should be called"
    assert fake.downs and fake.ups


if __name__ == "__main__":
    # Manual visual check (optional): beware this moves your mouse!
    import time
    import pyautogui

    hm = HumanMouse()
    print("Moving to 300,300 with human-like curve...")
    hm.move_to(300, 300)
    time.sleep(0.5)
    print("Clicking at 400, 400...")
    hm.click(400, 400)
    print("Done.")

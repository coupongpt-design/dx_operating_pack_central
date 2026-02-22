import math
import random
import time
from typing import Callable, Optional

import numpy as np
import pyautogui


class HumanMouse:
    """Human-like mouse emulator using bezier curves and easing."""

    def __init__(self, stop_flag: Optional[Callable[[], bool]] = None, respect_failsafe: bool = True):
        self._stop_flag = stop_flag or (lambda: False)
        self._respect_failsafe = respect_failsafe
        if respect_failsafe:
            pyautogui.FAILSAFE = True

    # --- Helpers ---------------------------------------------------------
    def _ease_out_cubic(self, t: float) -> float:
        return 1 - pow(1 - t, 3)

    def _bezier_curve(self, p0, p1, p2, p3, steps: int = 50):
        t_vals = np.linspace(0, 1, steps)
        curve = []
        for t in t_vals:
            inv = 1 - t
            x = (
                inv**3 * p0[0]
                + 3 * inv**2 * t * p1[0]
                + 3 * inv * t**2 * p2[0]
                + t**3 * p3[0]
            )
            y = (
                inv**3 * p0[1]
                + 3 * inv**2 * t * p1[1]
                + 3 * inv * t**2 * p2[1]
                + t**3 * p3[1]
            )
            curve.append((x, y))
        return curve

    def _duration_for_distance(self, dist: float) -> float:
        # Base human-like timing: short hops fast, long hops slower
        base = 0.08
        scale = min(0.6, dist / 600.0)
        jitter = random.uniform(0.0, 0.05)
        return base + scale + jitter

    def _build_curve(self, start, end):
        sx, sy = start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        # Control points with slight randomness to create arc
        ctrl1 = (sx + dx * random.uniform(0.3, 0.5) + random.uniform(-20, 20),
                 sy + dy * random.uniform(0.3, 0.5) + random.uniform(-20, 20))
        ctrl2 = (sx + dx * random.uniform(0.5, 0.8) + random.uniform(-20, 20),
                 sy + dy * random.uniform(0.5, 0.8) + random.uniform(-20, 20))
        return self._bezier_curve((sx, sy), ctrl1, ctrl2, (ex, ey), steps=60)

    def _should_stop(self) -> bool:
        try:
            return bool(self._stop_flag())
        except Exception:
            return False

    # --- Public API ------------------------------------------------------
    def move_to(self, x: int, y: int, duration: float | None = None):
        start = pyautogui.position()
        dist = math.hypot(x - start[0], y - start[1])
        duration = duration if duration is not None else self._duration_for_distance(dist)
        if duration <= 0 or dist < 2:
            pyautogui.moveTo(x, y)
            return

        path = self._build_curve(start, (x, y))
        steps = len(path)
        t0 = time.time()
        for i, (px, py) in enumerate(path):
            if self._should_stop():
                break
            t = i / max(1, steps - 1)
            eased = self._ease_out_cubic(t)
            target_time = t0 + duration * eased
            sleep_for = target_time - time.time()
            if sleep_for > 0:
                time.sleep(min(sleep_for, 0.02))
            pyautogui.moveTo(int(px), int(py))

    def click(self, x: int, y: int, button: str = "left", double: bool = False, hold_sec: float = 0.07):
        # Micro jitter to avoid exact pixel repeat
        jitter = random.randint(-3, 3)
        tx, ty = x + jitter, y + jitter
        self.move_to(tx, ty)
        if self._should_stop():
            return
        if double:
            pyautogui.click(tx, ty, clicks=2, interval=0.08, button=button)
        else:
            pyautogui.mouseDown(button=button)
            if hold_sec > 0:
                time.sleep(hold_sec)
            pyautogui.mouseUp(button=button)

    def drag(self, sx: int, sy: int, ex: int, ey: int, duration: float | None = None, button: str = "left"):
        if self._should_stop():
            return
        pyautogui.moveTo(sx, sy)
        pyautogui.mouseDown(button=button)
        try:
            self.move_to(ex, ey, duration=duration)
        finally:
            pyautogui.mouseUp(button=button)

    def drag_path(self, points: list[tuple[int, int, float | None]], button: str = "left"):
        if not points or len(points) < 2 or self._should_stop():
            return
        sx, sy, _ = points[0]
        pyautogui.moveTo(int(sx), int(sy))
        pyautogui.mouseDown(button=button)
        try:
            prev_t = points[0][2]
            for px, py, ts in points[1:]:
                if self._should_stop():
                    break
                if prev_t is not None and ts is not None:
                    delta = max(0.0, float(ts) - float(prev_t))
                else:
                    delta = 0.0
                if delta > 0:
                    pyautogui.moveTo(int(px), int(py), duration=delta, tween=pyautogui.easeInOutQuad)
                else:
                    pyautogui.moveTo(int(px), int(py))
                prev_t = ts
        finally:
            pyautogui.mouseUp(button=button)

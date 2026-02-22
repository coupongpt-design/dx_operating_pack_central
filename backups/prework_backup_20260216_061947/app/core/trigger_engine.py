import time
import mss
import numpy as np
import cv2
import pyautogui
from PyQt5.QtCore import QThread, pyqtSignal, QObject

from .models import TriggerData, StepData
from ..utils.matcher import Matcher

class TriggerWatcher(QThread):
    triggerFired = pyqtSignal(TriggerData)
    log = pyqtSignal(str)

    def __init__(self, triggers: list[TriggerData], parent=None):
        super().__init__(parent)
        self.triggers = triggers
        self._stop = False
        self._matcher = Matcher()
        self._paused = False

    def update_triggers(self, new_triggers: list[TriggerData]):
        self.triggers = new_triggers

    def stop(self):
        self._stop = True
        self.wait()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def run(self):
        self._stop = False
        self.log.emit("Trigger Watcher Started.")
        
        with mss.mss() as sct:
            mon = sct.monitors[0]
            
            while not self._stop:
                try:
                    if self._paused:
                        time.sleep(0.5)
                        continue

                    now = time.time()
                    frame_bgr = None
                    
                    # Check each trigger
                    for t in list(self.triggers):
                        if not t.enabled:
                            continue
                        
                        # Cooldown check
                        if (now - t.last_fired) * 1000 < t.cooldown_ms:
                            continue
                            
                        try:
                            if frame_bgr is None:
                                frame_bgr = self._capture_frame_bgr(sct, mon)
                                if frame_bgr is None:
                                    break
                            if self._check_condition(sct, mon, t, frame_bgr=frame_bgr):
                                t.last_fired = now
                                self.log.emit(f"[Trigger] Fired: {t.name}")
                                self.triggerFired.emit(t)
                        except Exception as e:
                            self.log.emit(f"[Trigger] Error checking {t.name}: {e}")

                    # Sleep interval
                    time.sleep(0.5) # Check every 500ms
                except Exception as e:
                    # Prevent thread death on unexpected exceptions
                    self.log.emit(f"[Trigger] Loop error: {e}")
                    time.sleep(0.5)

    def _capture_frame_bgr(self, sct, mon):
        try:
            region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
            raw = sct.grab(region)
            if hasattr(raw, "rgb") and hasattr(raw, "height") and hasattr(raw, "width"):
                frame = np.frombuffer(raw.rgb, dtype=np.uint8).reshape(raw.height, raw.width, 3)
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            frame = np.array(raw)
            if frame.ndim == 3 and frame.shape[-1] == 4:
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            if frame.ndim == 3 and frame.shape[-1] == 3:
                return frame
            return None
        except Exception:
            return None

    def _check_condition(self, sct, mon, t: TriggerData, frame_bgr=None) -> bool:
        # Use the condition_step directly with Matcher
        step = t.condition_step
        
        # Ensure template is loaded
        step.ensure_tpl()
            
        # Capture screen
        # Matcher expects BGR image
        # We can capture the whole screen or ROI if defined in step.
        # Matcher.find_best_optimized handles ROI if step.search_roi_enabled is True.
        # But we need to pass the full frame (or at least the ROI area) to it.
        # For simplicity and consistency, let's capture the monitor (or step ROI if we want to optimize capture).
        
        # Optimization: If step has ROI, capture only that region?
        # Matcher.find_best_optimized expects 'frame' to be the search area.
        # If step.search_roi_enabled is True, it crops the frame internally? 
        # No, Matcher.find_best_optimized(frame, step) does:
        # if step.search_roi_enabled: frame = frame[roi]
        # So we should pass the full monitor frame, or capture the ROI and pass it (but then disable ROI in step for the call?).
        # Let's pass the full monitor frame for now to be safe and let Matcher handle it.
        # Performance note: Capturing full screen is slower. 
        # But mss is fast.
        
        if frame_bgr is None:
            frame_bgr = self._capture_frame_bgr(sct, mon)
            if frame_bgr is None:
                return False
        
        mr = self._matcher.find_best_optimized(frame_bgr, step)
        return bool(getattr(mr, "ok", False))

    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

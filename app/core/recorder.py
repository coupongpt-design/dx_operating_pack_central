import time
import uuid
import queue
import threading
import logging
import math
import ctypes
from PyQt5.QtCore import QObject, pyqtSignal, QRect, Qt
from pynput import keyboard, mouse
from .models import StepData
from ..utils.common import hk_normalize, hk_to_tuple, hk_pretty

class InputRecorder(QObject):
    finished = pyqtSignal(list)
    pausedChanged = pyqtSignal(bool)
    raw_event_received = pyqtSignal(dict)
    control_event_received = pyqtSignal(str)

    def __init__(self, ignore_rect: QRect | None, parent=None,
                 typed_gap_ms=500,
                 click_merge_ms=350,
                 click_radius_px=3,
                 scroll_flush_ms=180,
                 scroll_scale_dx=30.0,
                 scroll_scale_dy=120.0,
                 record_delay_enabled: bool = False,
                 lock_hwnd=None,
                 ignore_combos=None,
                 max_queue_size: int = 5000,
                 move_min_distance_px: int = 3,
                 raw_event_callback=None,
                 control_event_callback=None,
                 stop_hotkeys=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self.ignore_rects: list[QRect | tuple] = []
        if ignore_rect:
            if isinstance(ignore_rect, (list, tuple)) and not isinstance(ignore_rect, QRect):
                for r in ignore_rect:
                    if r:
                        self.ignore_rects.append(r)
            else:
                self.ignore_rects.append(ignore_rect)

        self._typed_gap_ms = max(10, typed_gap_ms)
        if typed_gap_ms < 10:
            self.logger.warning("typed_gap_ms too small (%s); clamped to 10ms", typed_gap_ms)
        self._click_merge_ms = max(10, click_merge_ms)
        if click_merge_ms < 10:
            self.logger.warning("click_merge_ms too small (%s); clamped to 10ms", click_merge_ms)
        self._click_merge_px = click_radius_px
        self._scroll_flush_ms = scroll_flush_ms
        self._scroll_scale_dx = scroll_scale_dx
        self._scroll_scale_dy = scroll_scale_dy
        self._move_min_distance_px = max(0, move_min_distance_px)
        self._record_delay_enabled = bool(record_delay_enabled)
        
        self._active = False
        self._paused = False
        self._steps: list[StepData] = []
        
        self._typed_buf = ""
        self._typed_last = 0.0
        self._mods = set()
        
        self._press_pos = None # (btn, x, y, time)
        self._is_dragging = False
        self._drag_points = []
        
        self._scroll_acc = (0, 0)
        self._scroll_pos = None
        self._scroll_last = 0.0
        
        self._ignore_until = 0.0
        self._last_event_ts = 0.0 
        
        self._ignore_combos = set()
        if ignore_combos:
            for c in ignore_combos:
                c = hk_normalize(c)
                if c:
                    self._ignore_combos.add(c)
        
        # Queue and Worker
        self._max_queue_size = max_queue_size
        self._queue = queue.Queue(maxsize=self._max_queue_size)
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._stop_event = threading.Event()
        self._last_drop_log = 0.0
        self._last_move_pos = None  # (x, y)
        self._last_move_ts = 0.0
        self._raw_mods = set()
        self._raw_event_callback = raw_event_callback
        self._control_event_callback = control_event_callback
        self._self_hwnd = int(lock_hwnd) if lock_hwnd else None
        self._stop_hotkeys = {
            hk.lower()
            for hk in (stop_hotkeys or ("esc", "f12"))
            if isinstance(hk, str) and hk.strip()
        }
        self._win32_available = hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32")

        # Metrics
        self._processed_events = 0
        self._latency_sum = 0.0
        self._metrics_last_log = time.time()
        self.metrics = {
            "total": 0,
            "dropped_move": 0,
            "dropped_scroll": 0,
            "max_queue": 0,
            "start_time": 0,
        }

        self._kb = None
        self._ms = None
        self._create_listeners()

    def _create_listeners(self):
        self._kb = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release, suppress=False)
        self._ms = mouse.Listener(on_click=self._on_click, on_move=self._on_move, on_scroll=self._on_scroll)

    def _clear_queue(self):
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    def _emit_raw_event(self, payload: dict):
        try:
            self.raw_event_received.emit(payload)
        except Exception:
            pass
        if self._raw_event_callback:
            try:
                self._raw_event_callback(payload)
            except Exception as e:
                self.logger.debug("raw_event callback failed and was ignored: %s", e)

    def _emit_control_event(self, event_name: str):
        try:
            self.control_event_received.emit(event_name)
        except Exception:
            pass
        if self._control_event_callback:
            try:
                self._control_event_callback(event_name)
            except Exception as e:
                self.logger.debug("control callback failed and was ignored: %s", e)

    def _window_from_point(self, x: int, y: int) -> int | None:
        if not self._win32_available:
            return None
        try:
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            hwnd = int(ctypes.windll.user32.WindowFromPoint(POINT(int(x), int(y))))
            return hwnd or None
        except Exception:
            return None

    def _foreground_hwnd(self) -> int | None:
        if not self._win32_available:
            return None
        try:
            hwnd = int(ctypes.windll.user32.GetForegroundWindow())
            return hwnd or None
        except Exception:
            return None

    def _normalize_hwnd(self, hwnd: int | None) -> int | None:
        if not hwnd:
            return None
        if not self._win32_available:
            return int(hwnd)
        try:
            # GA_ROOT = 2
            root = int(ctypes.windll.user32.GetAncestor(int(hwnd), 2))
            return root or int(hwnd)
        except Exception:
            return int(hwnd)

    def _is_self_capture_hwnd(self, hwnd: int | None) -> bool:
        if not hwnd or not self._self_hwnd:
            return False
        return self._normalize_hwnd(hwnd) == self._normalize_hwnd(self._self_hwnd)

    # --- Internal helpers ---
    def _enqueue_event(self, etype: str, *payload):
        """Safely enqueue an event with flood protection."""
        self.metrics["total"] += 1
        self.metrics["max_queue"] = max(self.metrics["max_queue"], self._queue.qsize())
        if self._queue.full():
            now = time.time()
            if etype == "move":
                self.metrics["dropped_move"] += 1
            elif etype == "scroll":
                self.metrics["dropped_scroll"] += 1
            if now - self._last_drop_log > 1.0:
                self.logger.warning(
                    "Recorder queue full (%s). Dropped: move=%s, scroll=%s",
                    self._max_queue_size,
                    self.metrics["dropped_move"],
                    self.metrics["dropped_scroll"],
                )
                self._last_drop_log = now
            return
        self._queue.put((etype, time.time(), *payload))
        self.metrics["max_queue"] = max(self.metrics["max_queue"], self._queue.qsize())

    def _maybe_log_metrics(self):
        now = time.time()
        if now - self._metrics_last_log < 5.0:
            return
        avg_latency_ms = 0.0
        if self._processed_events:
            avg_latency_ms = (self._latency_sum / self._processed_events) * 1000.0
        self.logger.debug(
            "[Recorder] Events processed: %s, Queue: %s/%s, Avg latency: %.4f ms",
            self._processed_events,
            self._queue.qsize(),
            self._max_queue_size,
            avg_latency_ms,
        )
        self._processed_events = 0
        self._latency_sum = 0.0
        self._metrics_last_log = now

    def _resample_path(self, points, target_count: int = 20):
        if not points or len(points) < 3 or target_count < 2:
            return points
        # Separate coords and times
        xs, ys, ts = zip(*points)
        distances = [0.0]
        for i in range(1, len(points)):
            distances.append(math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]) + distances[-1])
        total_dist = distances[-1]
        if total_dist == 0:
            return points
        start_t, end_t = ts[0], ts[-1]
        new_points = []
        for i in range(target_count):
            ratio = i / (target_count - 1)
            target_d = ratio * total_dist
            # find segment
            idx = 1
            while idx < len(distances) and distances[idx] < target_d:
                idx += 1
            if idx >= len(distances):
                idx = len(distances) - 1
            prev_d = distances[idx - 1]
            seg_len = distances[idx] - prev_d if distances[idx] - prev_d != 0 else 1e-6
            seg_ratio = (target_d - prev_d) / seg_len
            nx = xs[idx - 1] + (xs[idx] - xs[idx - 1]) * seg_ratio
            ny = ys[idx - 1] + (ys[idx] - ys[idx - 1]) * seg_ratio
            nt = start_t + (end_t - start_t) * ratio
            new_points.append((nx, ny, nt))
        return new_points

    def _calc_delay_ms(self, ts: float) -> int:
        if not self._record_delay_enabled:
            return 0
        if not self._last_event_ts:
            return 0
        return max(0, int((ts - self._last_event_ts) * 1000))

    def start(self):
        if self._active or (self._worker_thread and self._worker_thread.is_alive()):
            self.logger.warning("Recorder already running")
            return
        self._active = True
        self._paused = False
        self._typed_buf = ""
        self._mods.clear()
        self._raw_mods.clear()
        self._steps = []
        self._press_pos = None
        self._is_dragging = False
        self._drag_points = []
        self._scroll_acc = (0, 0)
        self._last_move_pos = None
        self._clear_queue()
        self._stop_event.clear()
        # reset metrics per session
        self.metrics.update(
            {
                "total": 0,
                "dropped_move": 0,
                "dropped_scroll": 0,
                "max_queue": 0,
                "start_time": time.time(),
            }
        )
        if self._worker_thread and not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        self._create_listeners()
        self._kb.start()
        self._ms.start()
        self._ignore_until = time.time() + 0.25
        self._last_event_ts = time.time()

    def stop(self):
        self._active = False
        try:
            if self._kb:
                self._kb.stop()
            if self._ms:
                self._ms.stop()
            if self._kb:
                self._kb.join(timeout=1.0)
            if self._ms:
                self._ms.join(timeout=1.0)
            if self._kb and self._kb.is_alive():
                self.logger.warning("Keyboard listener did not stop within timeout.")
            if self._ms and self._ms.is_alive():
                self.logger.warning("Mouse listener did not stop within timeout.")
        except Exception as e:
            self.logger.warning("Failed to stop input listeners cleanly: %s", e)
        
        # Signal worker to stop
        self._emit_control_event("stop_requested")
        try:
            self._queue.put_nowait(("stop", time.time()))
        except queue.Full:
            pass
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._clear_queue()
        self.finished.emit(self._steps)
        return self.metrics

    def _process_queue(self):
        while True:
            try:
                # Wait for event
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                # Check flush timers if idle
                self._check_flush_timers()
                if self._stop_event.is_set():
                    self._flush_all(True)
                    break
                continue

            etype = event[0]
            ts = event[1]
            
            if etype == "stop":
                self._flush_all(True)
                break
            
            if etype == "key_press":
                self._handle_key_press(ts, event[2])
            elif etype == "key_release":
                self._handle_key_release(ts, event[2])
            elif etype == "click":
                self._handle_click(ts, event[2], event[3], event[4], event[5])
            elif etype == "move":
                self._handle_move(ts, event[2], event[3])
            elif etype == "scroll":
                self._handle_scroll(ts, event[2], event[3], event[4], event[5])
            
            self._queue.task_done()
            self._processed_events += 1
            self._latency_sum += max(0.0, time.time() - ts)
            self._maybe_log_metrics()

    def _check_flush_timers(self):
        now = time.time()
        if self._typed_buf and (now - self._typed_last) * 1000 >= self._typed_gap_ms:
            self._flush_text(False)
        if self._scroll_acc != (0, 0) and (now - self._scroll_last) * 1000 >= self._scroll_flush_ms:
            self._flush_scroll(True)

    def _flush_all(self, force=True):
        self._flush_text(force)
        self._flush_click(force)
        self._flush_scroll(force)

    # --- Event Handlers (Consumer) ---

    def _handle_key_press(self, ts, k):
        self._flush_click(True)
        self._flush_scroll(True)
        
        if ts < self._ignore_until:
            return
            
        try:
            if self._should_ignore_keypress(k):
                self._ignore_until = ts + 0.08
                return
        except Exception as e:
            self.logger.debug("Ignore-combo check failed; continuing key handling: %s", e)
            
        if k == keyboard.Key.f8:
            self._flush_all(True)
            self._paused = not self._paused
            self.pausedChanged.emit(self._paused)
            return
            
        if self._paused:
            return
            
        tok = self._key_token(k)
        if tok in ('shift', 'ctrl', 'alt', 'win'):
            self._mods.add(tok)
            return
            
        # Normal key
        try:
            combo = None
            if self._mods:
                base = self._token_from_key(k)
                if base:
                    parts = sorted(list(self._mods)) + [base]
                    combo = "+".join(parts)
            
            if combo:
                combo_norm = hk_normalize(combo) or combo
                combo_name = hk_pretty(combo_norm) or combo_norm
                self._flush_text(True)
                delay_ms = self._calc_delay_ms(ts)
                
                self._steps.append(StepData(
                    id=str(uuid.uuid4())[:8], name=f"Hotkey {combo_name}", type="key", 
                    key_string=combo_norm,
                    pre_delay_ms=int(delay_ms)
                ))
                self._last_event_ts = ts
            else:
                # Typing
                ch = None
                if isinstance(k, keyboard.KeyCode) and k.char:
                    ch = k.char
                elif k == keyboard.Key.space: ch = " "
                elif k == keyboard.Key.enter: ch = "\n"
                elif k == keyboard.Key.tab: ch = "\t"
                
                if ch:
                    self._typed_last = ts
                    self._typed_buf += ch
                else:
                    base = self._token_from_key(k)
                    if base:
                        self._flush_text(True)
                        delay_ms = self._calc_delay_ms(ts)
                        
                        self._steps.append(StepData(
                            id=str(uuid.uuid4())[:8], name=f"Key {base}", type="key", 
                            key_string=base,
                            pre_delay_ms=int(delay_ms)
                        ))
                        self._last_event_ts = ts
        except Exception as e:
            self.logger.warning("Key press handling failed; event skipped: %s", e)

    def _handle_key_release(self, ts, k):
        tok = self._key_token(k)
        if tok in ('shift', 'ctrl', 'alt', 'win'):
            self._mods.discard(tok)
            return
        # Flush checks are done in _check_flush_timers loop

    def _handle_click(self, ts, x, y, button, pressed):
        self._flush_text(True)
        
        if ts < self._ignore_until or self._paused:
            return
        if self._in_ignore(x, y):
            return
        
        btn = self._btn_name(button)

        if pressed:
            self._press_pos = (btn, x, y, ts)
            self._is_dragging = True
            self._drag_points = [(x, y, ts)]
            return

        # Released
        if not self._press_pos:
            return
        
        p_btn, px, py, pt = self._press_pos
        self._press_pos = None
        self._is_dragging = False
        
        dist = ((x - px)**2 + (y - py)**2)**0.5
        
        # Drag check
        if dist > self._click_merge_px:
            sx, sy = px, py
            ex, ey = x, y
            st, et = pt, ts
            
            delay_ms = self._calc_delay_ms(st)
            drag_path = self._resample_path(self._drag_points, target_count=20)

            self._steps.append(StepData(
                id=str(uuid.uuid4())[:8], name=f"Path Drag ({sx},{sy})->({ex},{ey})",
                type="drag_path",
                drag_from_x=sx, drag_from_y=sy, drag_to_x=ex, drag_to_y=ey,
                drag_duration_ms=int((et - st) * 1000),
                pre_delay_ms=int(delay_ms),
                drag_path=drag_path
            ))
            self._last_event_ts = ts
            self._drag_points = []
            return

        # Click check
        delay_ms = self._calc_delay_ms(pt)
        
        self._steps.append(StepData(
            id=str(uuid.uuid4())[:8], name=f"Click {btn} ({x},{y})", type="click_point",
            click_x=x, click_y=y, click_btn=btn,
            pre_delay_ms=int(delay_ms)
        ))
        self._last_event_ts = ts

    def _handle_move(self, ts, x, y):
        if self._is_dragging:
            # Downsample drag points to avoid memory explosion
            if not self._drag_points or (ts - self._drag_points[-1][2] > 0.02): # 50Hz max
                self._drag_points.append((x, y, ts))

    def _handle_scroll(self, ts, x, y, dx, dy):
        self._flush_text(True)
        self._flush_click(True)
        
        if ts < self._ignore_until or self._paused:
            return
        if self._in_ignore(x, y):
            return
        self._scroll_acc = (self._scroll_acc[0] + dx, self._scroll_acc[1] + dy)
        self._scroll_pos = (x, y)
        self._scroll_last = ts

    # --- Helpers ---

    def _flush_text(self, force=False):
        if not self._typed_buf:
            return
        text = self._typed_buf
        self._typed_buf = ""
        
        now = time.time() # Use current time for flush event
        delay_ms = self._calc_delay_ms(now)
            
        self._steps.append(StepData(
            id=str(uuid.uuid4())[:8], name=f"Type '{text}'", type="key", 
            key_string=text,
            pre_delay_ms=int(delay_ms)
        ))
        self._last_event_ts = now

    def _flush_click(self, force=False):
        if not self._press_pos:
            return
        # If pending click exists, it means drag didn't happen or finished abruptly
        # But usually _handle_click handles release. 
        # This is for forced flush (e.g. stop)
        pass

    def _flush_scroll(self, force: bool):
        if self._scroll_acc == (0, 0):
            return
        now = time.time()
        if not force and (now - self._scroll_last) * 1000 < self._scroll_flush_ms:
            return
        sx, sy = self._scroll_acc

        delay_ms = self._calc_delay_ms(now)

        self._steps.append(StepData(
            id=str(uuid.uuid4())[:8], name=f"Scroll {sx},{sy}", type="scroll",
            scroll_dx=int(sx * self._scroll_scale_dx),
            scroll_dy=int(sy * self._scroll_scale_dy),
            scroll_x=self._scroll_pos[0] if self._scroll_pos else None,
            scroll_y=self._scroll_pos[1] if self._scroll_pos else None,
            scroll_times=1, scroll_interval_ms=0,
            pre_delay_ms=int(delay_ms)
        ))
        self._scroll_acc = (0, 0)
        self._scroll_pos = None
        self._last_event_ts = now

    def _btn_name(self, b):
        s = str(b).replace('Button.', '')
        if s == 'left': return 'left'
        if s == 'right': return 'right'
        if s == 'middle': return 'middle'
        return 'left'

    def _in_ignore(self, x, y) -> bool:
        if not self.ignore_rects:
            return False
        for r in self.ignore_rects:
            if isinstance(r, QRect):
                if (r.left() <= x <= r.right()) and (r.top() <= y <= r.bottom()):
                    return True
            elif isinstance(r, tuple) and len(r) == 4:
                left, top, right, bottom = r
                if left <= x <= right and top <= y <= bottom:
                    return True
        return False

    def _token_from_key(self, k) -> str | None:
        try:
            mapping = {
                keyboard.Key.enter: 'enter', keyboard.Key.esc: 'esc', keyboard.Key.space: 'space',
                keyboard.Key.tab: 'tab', keyboard.Key.backspace: 'backspace', keyboard.Key.delete: 'delete',
                keyboard.Key.home: 'home', keyboard.Key.end: 'end', keyboard.Key.insert: 'insert',
                keyboard.Key.page_up: 'pageup', keyboard.Key.page_down: 'pagedown',
                keyboard.Key.left: 'left', keyboard.Key.right: 'right', keyboard.Key.up: 'up', keyboard.Key.down: 'down',
                keyboard.Key.ctrl: 'ctrl', keyboard.Key.ctrl_l: 'ctrl', keyboard.Key.ctrl_r: 'ctrl',
                keyboard.Key.alt: 'alt', keyboard.Key.alt_l: 'alt', keyboard.Key.alt_r: 'alt',
                keyboard.Key.shift: 'shift', keyboard.Key.shift_l: 'shift', keyboard.Key.shift_r: 'shift',
                keyboard.Key.cmd: 'win', keyboard.Key.cmd_l: 'win', keyboard.Key.cmd_r: 'win'
            }
            if isinstance(k, keyboard.KeyCode) and k.char is not None:
                ch = k.char.lower()
                if ch: return ch
            for i in range(1, 25):
                try:
                    if k == getattr(keyboard.Key, f"f{i}"): return f"f{i}"
                except AttributeError: pass
            if k in mapping: return mapping[k]
        except Exception: pass
        return None

    def _key_token(self, k) -> str | None:
        return self._token_from_key(k)

    def _match_combo(self, mods_set, base_token, want_combo: str | None) -> bool:
        if not want_combo: return False
        req_mods, req_base = hk_to_tuple(hk_normalize(want_combo))
        if not req_base: return False
        # wildcard base (*) matches any base token when modifiers align
        if req_base != "*" and base_token != req_base:
            return False
        return req_mods.issubset(mods_set)

    def _should_ignore_keypress(self, k) -> bool:
        base = self._token_from_key(k)
        if not base: return False
        for ig in self._ignore_combos:
            if self._match_combo(self._mods, base, ig): return True
        return False

    # --- Callbacks (Producer) ---

    def _on_key_press(self, k):
        tok = self._key_token(k)
        if tok in ('shift', 'ctrl', 'alt', 'win'):
            self._raw_mods.add(tok)
        hwnd = self._foreground_hwnd()
        if tok and tok.lower() in self._stop_hotkeys:
            self._emit_control_event("stop_hotkey")
            return
        if self._is_self_capture_hwnd(hwnd):
            return
        self._emit_raw_event({
            "timestamp": time.time(),
            "type": "key",
            "x": None,
            "y": None,
            "button": None,
            "key_code": tok,
            "modifiers": sorted(self._raw_mods),
            "hwnd": hwnd,
            "phase": "press",
        })
        self._enqueue_event("key_press", k)

    def _on_key_release(self, k):
        tok = self._key_token(k)
        if tok in ('shift', 'ctrl', 'alt', 'win'):
            self._raw_mods.discard(tok)
        hwnd = self._foreground_hwnd()
        if tok and tok.lower() in self._stop_hotkeys:
            return
        if self._is_self_capture_hwnd(hwnd):
            return
        self._emit_raw_event({
            "timestamp": time.time(),
            "type": "key",
            "x": None,
            "y": None,
            "button": None,
            "key_code": tok,
            "modifiers": sorted(self._raw_mods),
            "hwnd": hwnd,
            "phase": "release",
        })
        self._enqueue_event("key_release", k)

    def _on_click(self, x, y, button, pressed):
        # Ignore regions first
        if self._in_ignore(x, y):
            return
        hwnd = self._window_from_point(x, y)
        if self._is_self_capture_hwnd(hwnd):
            return
        self._emit_raw_event({
            "timestamp": time.time(),
            "type": "click",
            "x": int(x),
            "y": int(y),
            "button": self._btn_name(button),
            "key_code": None,
            "modifiers": sorted(self._raw_mods),
            "hwnd": hwnd,
            "phase": "press" if pressed else "release",
        })
        self._enqueue_event("click", x, y, button, pressed)

    def _on_move(self, x, y):
        # Distance filter to cut noise
        now = time.time()
        if self._last_move_pos:
            dist = math.hypot(x - self._last_move_pos[0], y - self._last_move_pos[1])
            dt = now - self._last_move_ts
            if dist < self._move_min_distance_px and dt < 0.02:
                return
        self._last_move_pos = (x, y)
        self._last_move_ts = now
        if self._in_ignore(x, y):
            return
        if self._is_self_capture_hwnd(self._window_from_point(x, y)):
            return
        self._enqueue_event("move", x, y)

    def _on_scroll(self, x, y, dx, dy):
        if self._in_ignore(x, y):
            return
        if self._is_self_capture_hwnd(self._window_from_point(x, y)):
            return
        self._enqueue_event("scroll", x, y, dx, dy)

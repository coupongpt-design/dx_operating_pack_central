import time
import traceback
import logging
import uuid
import threading
from contextlib import contextmanager
import re
import os
from pathlib import Path
import random
import cv2
import mss
import numpy as np
import pyautogui
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication

from .vision import ImageProcessor
from .input_emulator import HumanMouse
from .window_manager import WindowManager
from .evaluator import ConditionEvaluator
from .input_lock import (
    GlobalInputManager,
    InputLockTimeoutError,
    get_global_input_manager,
)
from .exceptions import (
    ActionError,
    ExecutionError,
    MacroBaseError,
    ResourceError,
    TargetWindowError,
)

from .models import StepData, RepeatConfig
from .ocr_runtime import configure_tesseract_cmd
from .template_processor import TemplateProcessor
from ..utils.matcher import Matcher
from ..utils.common import info, err, hk_to_tuple, hk_normalize, hk_pretty
from ..utils.logging_setup import setup_file_logger
from ..utils.structured_jsonl import StructuredJsonlLogger
from ..io.macro_io import MacroIO
from ..io.data_loader import load_data_rows

PHYSICAL_KEY_NAMES = {
    "enter", "space", "tab", "backspace", "delete", "home", "end", "insert",
    "esc", "pageup", "pagedown", "up", "down", "left", "right",
    "capslock", "printscreen", "scrolllock", "pause", "win"
}
PHYSICAL_KEY_NAMES.update({f"f{i}" for i in range(1, 25)})
MODIFIER_KEY_MAP = {
    "ctrl": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "win": "win",
}
# Constants used in _build_target_step
BRANCH_TARGET_MATCH_FIELDS = [
    "min_confidence",
    "threshold",
    "match_quality",
    "top_k",
    "pre_gray",
    "pre_blur_ksize",
    "pre_clahe",
    "pre_edge",
    "pre_sharpen",
    "match_color",
    "color_match_tolerance",
    "budget_ms",
    "tpl_cache_limit",
    "ms_enable",
    "ms_min_scale",
    "ms_max_scale",
    "ms_step",
    "max_scales",
    "rot_enable",
    "rot_min_deg",
    "rot_max_deg",
    "rot_step_deg",
    "max_rotations",
    "feat_fallback_enable",
    "feat_nfeatures",
    "feat_match_ratio",
    "feat_ransac_reproj_thresh",
    "mask_enable",
    "mask_auto_edge",
    "mask_thresh",
    "top_k",
    "detect_consecutive",
    "budget_ms",
    "max_rotations",
    "max_scales",
]

BRANCH_TARGET_CLICK_FIELDS = [
    "click_button",
    "click_double",
    "image_action",
    "click_anchor",
    "click_offset_x",
    "click_offset_y",
    "jitter",
    "pre_move_sleep_ms",
    "press_duration_ms",
    "post_click_sleep_ms",
]

class MacroRunner(QThread):
    def _log_enter_subscript(self) -> bool:
        """Emit log when entering a sub-script."""
        try:
            self.log.emit("Enter sub-script")
        except Exception as e:
            logger = getattr(self, "logger", logging.getLogger(__name__ + ".MacroRunner"))
            logger.debug("Failed to emit sub-script entry log: %s", e)
        return True
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)
    requestCrosshair = pyqtSignal(int, int, int)
    errorOccurred = pyqtSignal(str)
    debugEvent = pyqtSignal(dict)
    stepChanged = pyqtSignal(int)
    stepStarted = pyqtSignal(str, str)
    stepSucceeded = pyqtSignal(str)
    stepFailed = pyqtSignal(str, str, str)

    def __init__(
        self,
        steps: list[StepData],
        repeat: RepeatConfig | None = None,
        dry_run: bool = False,
        start_index: int = 0,
        capture_on_fail: bool = False,
        human_mode: bool = False,
        parent=None,
        current_file_path: str | None = None,
        target_window_title: str | None = None,
        perf_mode: bool = False,
        structured_logging: bool = False,
        structured_log_dir: str | None = None,
        input_lock_enabled: bool = True,
        input_lock_timeout_sec: float = 10.0,
        input_lock_manager: GlobalInputManager | None = None,
        auto_enter_after_text: bool = False,
    ):
        super().__init__(parent)
        self.steps = steps
        self.repeat = repeat or RepeatConfig()
        self.dry_run = dry_run
        self.start_index = start_index
        self.capture_on_fail = capture_on_fail
        self.human_mode = human_mode
        self.perf_mode = bool(perf_mode)
        self.current_file_path = current_file_path
        self.logger = logging.getLogger(__name__ + ".MacroRunner")
        self._logger = self.logger
        self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.structured_log_path: str = ""
        self._structured_logger = StructuredJsonlLogger(
            run_id=self.run_id,
            log_dir=structured_log_dir or os.path.join(os.getcwd(), "logs"),
            enabled=bool(structured_logging),
        )
        self._input_lock_enabled = bool(input_lock_enabled)
        self._input_lock_timeout_sec = max(0.05, float(input_lock_timeout_sec))
        self._input_lock_manager = input_lock_manager or get_global_input_manager()
        self._auto_enter_after_text = bool(auto_enter_after_text)
        self._resource_retry_default_attempts = 2
        self._resource_retry_default_delay_ms = 250
        self._self_heal_mouse_home = (10, 10)
        self._step_started_at: dict[str, float] = {}
        self._run_finish_emitted = False
        self.engine_state = "IDLE"
        self._pyautogui_defaults = {
            "PAUSE": getattr(pyautogui, "PAUSE", 0),
            "MINIMUM_DURATION": getattr(pyautogui, "MINIMUM_DURATION", 0),
            "MINIMUM_SLEEP": getattr(pyautogui, "MINIMUM_SLEEP", 0),
        }
        if target_window_title is None:
            target_window_title = ""
        self.target_window_title = str(target_window_title or "").strip()
        self._stop = False
        self._killed = False
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._matcher = Matcher()
        self._loop_counters = {}
        self._data_list: list[str] | None = None
        self._data_index: int = 0
        self._max_duration_fired = False
        # Assuming fail_captures is relative to this file or app root. 
        # Using app root for safety.
        self._fail_capture_dir = os.path.join(os.getcwd(), "fail_captures")
        self._data_rows: list[dict[str, str]] | None = None
        self._data_row_values: list[list[str]] | None = None
        self._data_columns: list[str] = []
        self._primary_data_column: str | None = None
        # Context memory for OCR/variables
        self.variable_context: dict[str, object] = {}
        self._human_mouse = HumanMouse(stop_flag=lambda: self._stop, respect_failsafe=True)
        self._logger = setup_file_logger("MacroRunner")
        self._window_manager = WindowManager()
        ip = getattr(self, "_image_processor", None)
        self.evaluator = ConditionEvaluator(ip)
        self.call_stack: list[dict[str, object]] = []
        self._max_call_depth: int = 5
        self._switch_steps = None
        self._switch_path = None

        # Counters for dynamic strings
        self._counters = {}
        self._default_counter = 1
        self._resume_state: dict | None = None
        # CPU guard for main loop
        self.poll_interval: float = 0.0 if self.perf_mode else 0.1
        
        self.current_step_index = 0 # Track current step index
        
        # Dispatch map for faster step execution
        self._step_handlers = {
            "comment": lambda sct, mon, s, idx: (True, None, 0),
            "image_click": self._image_click,
            "wait_for_image": self._wait_for_image,
            "image_branch": lambda sct, mon, s, idx: (*self._image_branch(sct, mon, s), 0), # Adapter for different signature
            "text": lambda sct, mon, s, idx: (self._text_paste(s), None, 0),
            "key": lambda sct, mon, s, idx: (*self._key_press(s), 0),
            "key_down": lambda sct, mon, s, idx: (*self._key_down(s), 0),
            "key_up": lambda sct, mon, s, idx: (*self._key_up(s), 0),
            "key_hold": lambda sct, mon, s, idx: (*self._key_hold(s), 0),
            "keyboard": lambda sct, mon, s, idx: (*self._keyboard(s), 0),
            "mouse": lambda sct, mon, s, idx: (*self._mouse(s), 0),
            "screen_check": lambda sct, mon, s, idx: (*self._screen_check(sct, mon, s), 0),
            "mouse_move": lambda sct, mon, s, idx: (self._mouse_move(s), None, 0),
            "click": lambda sct, mon, s, idx: (*self._generic_click(s), 0),
            "click_point": lambda sct, mon, s, idx: (*self._click_point(s), 0),
            "drag": lambda sct, mon, s, idx: (self._drag(s), None, 0),
            "drag_path": lambda sct, mon, s, idx: (self._drag_path(s), None, 0),
            "scroll": lambda sct, mon, s, idx: (*self._scroll(s), 0),
            "wait": lambda sct, mon, s, idx: (self._wait_step(s), None, 0),
            "pixel_check": lambda sct, mon, s, idx: (*self._pixel_check(s), 0),
            "start_loop": self._handle_start_loop,
            "loop": lambda sct, mon, s, idx: (self._loop_placeholder(s), None, 0),
            "compare_images": lambda sct, mon, s, idx: (*self._compare_images(s), 0),
            "screenshot_roi": lambda sct, mon, s, idx: (self._screenshot_roi(sct, s), None, 0),
            "ocr_check_text": lambda sct, mon, s, idx: (*self._ocr_check_text(sct, mon, s), 0),
            "ocr_jump_if": lambda sct, mon, s, idx: self._ocr_jump_if(sct, mon, s),
            "ocr_store": lambda sct, mon, s, idx: (self._ocr_store(sct, mon, s), None, 0),
            "load_data_file": lambda sct, mon, s, idx: (self._load_data_file(s), None, 0),
            "file_action": lambda sct, mon, s, idx: (*self._file_action(s), 0),
            "end_loop": lambda sct, mon, s, idx: (*self._end_loop(s), 0),
            "jump_if": lambda sct, mon, s, idx: self._jump_if(s),
            "run_macro": lambda sct, mon, s, idx: (self._log_enter_subscript() and self._handle_run_macro(s), None, 0),
        }

    def _handle_start_loop(self, sct, mon, s: StepData, idx: int) -> tuple[bool, str | None, int]:
        if s.id not in self._loop_counters:
            self._loop_counters[s.id] = max(0, int(s.loop_count))
        return (True, None, 0)

    def _runtime_step_uuid(self, step: StepData) -> str:
        source = str(getattr(step, "source_step_id", "") or "").strip()
        if source:
            return source
        return str(getattr(step, "id", "") or "").strip()

    def _normalize_step_template_path(self, step: StepData) -> None:
        path = str(getattr(step, "anchor_image_path", "") or getattr(step, "image_path", "") or "").strip()
        if not path:
            return
        try:
            resolved = os.path.expandvars(os.path.expanduser(path))
            if not os.path.isabs(resolved):
                base = ""
                if self.current_file_path:
                    base = os.path.dirname(os.path.abspath(self.current_file_path))
                resolved = os.path.abspath(os.path.join(base or os.getcwd(), resolved))
            step.anchor_image_path = resolved
        except Exception as e:
            if isinstance(e, MacroBaseError):
                raise
            self.logger.debug("Failed to normalize template path '%s': %s", path, e)

    def _set_engine_state(self, state: str):
        self.engine_state = str(state or "IDLE").upper()

    def _release_runtime_controls(self):
        # Best-effort release to prevent lingering input ownership on failures.
        for button in ("left", "right", "middle"):
            try:
                pyautogui.mouseUp(button=button)
            except Exception:
                pass
        for key in ("shift", "ctrl", "alt", "win", "command"):
            try:
                pyautogui.keyUp(key)
            except Exception:
                pass

    def _is_resource_retry_target_step(self, step: StepData) -> bool:
        return str(getattr(step, "type", "") or "") in {
            "image_click",
            "wait_for_image",
            "image_branch",
            "compare_images",
        }

    def _resolve_resource_retry_attempts(self, step: StepData) -> int:
        raw = getattr(step, "resource_retry_count", None)
        if raw is None:
            raw = getattr(step, "retry_count", None)
        try:
            value = int(raw)
        except Exception:
            value = int(self._resource_retry_default_attempts)
        return max(0, min(value, 10))

    def _resolve_resource_retry_delay_ms(self, step: StepData) -> int:
        raw = getattr(step, "resource_retry_delay_ms", None)
        if raw is None:
            raw = getattr(step, "retry_delay_ms", None)
        try:
            value = int(raw)
        except Exception:
            value = int(self._resource_retry_default_delay_ms)
        return max(0, value)

    def _attempt_action_error_recovery(self, step: StepData, idx: int, error: ActionError) -> bool:
        recovered = False
        step_no = int(idx) + 1
        try:
            self._release_runtime_controls()
            recovered = True
        except Exception:
            pass

        if not self.dry_run:
            try:
                with self._acquire_input_lock("self_heal_escape"):
                    pyautogui.press("esc")
                recovered = True
            except Exception as e:
                self.logger.debug("self-heal escape failed at step %s: %s", step_no, e)
            try:
                home_x, home_y = self._self_heal_mouse_home
                with self._acquire_input_lock("self_heal_mouse_home"):
                    pyautogui.moveTo(int(home_x), int(home_y), duration=0)
                recovered = True
            except Exception as e:
                self.logger.debug("self-heal mouse-home failed at step %s: %s", step_no, e)

        self._write_structured_event(
            "WARN",
            "step_recovery",
            step_uuid=self._runtime_step_uuid(step),
            step_index=int(idx),
            step_name=str(getattr(step, "name", "") or ""),
            exception_type=error.__class__.__name__,
            recovered=bool(recovered),
        )
        if recovered:
            self.log.emit(f"  -> Self-heal recovery applied at step {step_no}.")
        else:
            self.log.emit(f"  !! Self-heal recovery unavailable at step {step_no}.")
        return recovered

    def _to_macro_error(self, exc: Exception, step: StepData | None = None, idx: int | None = None) -> MacroBaseError:
        if isinstance(exc, MacroBaseError):
            return exc
        step_name = str(getattr(step, "name", "") or "")
        step_type = str(getattr(step, "type", "") or "")
        step_no = (int(idx) + 1) if isinstance(idx, int) and idx >= 0 else -1
        if isinstance(exc, InputLockTimeoutError):
            return ActionError(f"input lock timeout at step {step_no} ({step_name})")
        if isinstance(exc, FileNotFoundError):
            return ResourceError(f"file not found at step {step_no} ({step_name})")
        if step is not None and step_type in {
            "image_click",
            "wait_for_image",
            "image_branch",
            "compare_images",
            "run_macro",
            "load_data_file",
        }:
            return ResourceError(f"resource failure at step {step_no} ({step_name}): {exc}")
        if step is not None:
            return ActionError(f"action failed at step {step_no} ({step_name}): {exc}")
        return ExecutionError(str(exc))

    def _emit_step_exception_telemetry(self, step: StepData, idx: int, error: MacroBaseError):
        self._write_structured_event(
            "ERROR",
            "step_exception",
            step_uuid=self._runtime_step_uuid(step),
            step_index=int(idx),
            step_name=str(getattr(step, "name", "") or ""),
            exception_type=error.__class__.__name__,
            error=str(error),
        )

    def _validate_step_resources(self, step: StepData):
        step_type = str(getattr(step, "type", "") or "")
        has_embedded_template = bool(getattr(step, "png_bytes", None))
        def _skip_precheck_for_dynamic_path(raw_path: str) -> bool:
            text = str(raw_path or "")
            # Runtime template tokens may resolve differently at execution time.
            return any(token in text for token in ("{", "}", "#", "@", "?"))
        if step_type in {"image_click", "wait_for_image", "image_branch"} and not has_embedded_template:
            raw = str(getattr(step, "anchor_image_path", "") or getattr(step, "image_path", "") or "").strip()
            if raw:
                if _skip_precheck_for_dynamic_path(raw):
                    return
                resolved = self._resolve_path(raw)
                if resolved and not os.path.exists(resolved):
                    raise ResourceError(f"template image not found: {resolved}")
        if step_type == "compare_images":
            for field_name in ("image_a_path", "image_b_path"):
                raw = str(getattr(step, field_name, "") or "").strip()
                if not raw:
                    continue
                if _skip_precheck_for_dynamic_path(raw):
                    continue
                resolved = self._resolve_path(raw)
                if resolved and not os.path.exists(resolved):
                    raise ResourceError(f"compare resource not found ({field_name}): {resolved}")

    def _write_structured_event(self, level: str, event: str, **payload):
        try:
            self._structured_logger.write(level=level, event=event, payload=payload)
        except Exception as e:
            self.logger.debug("structured event write failed: %s", e)

    @contextmanager
    def _acquire_input_lock(self, operation: str):
        if self.dry_run or not self._input_lock_enabled:
            yield
            return

        timeout_sec = float(self._input_lock_timeout_sec)
        op = str(operation or "input")
        self._write_structured_event(
            "INFO",
            "input_lock_waiting",
            operation=op,
            timeout_sec=timeout_sec,
        )
        try:
            with self._input_lock_manager.acquire(
                timeout_sec=timeout_sec,
                owner=str(self.run_id or ""),
                operation=op,
            ) as token:
                self._write_structured_event(
                    "INFO",
                    "input_lock_acquired",
                    operation=op,
                    wait_ms=int(token.wait_ms),
                )
                held_start = time.perf_counter()
                try:
                    yield
                finally:
                    held_ms = max(0, int((time.perf_counter() - held_start) * 1000))
                    self._write_structured_event(
                        "INFO",
                        "input_lock_released",
                        operation=op,
                        held_ms=held_ms,
                    )
        except InputLockTimeoutError:
            self._write_structured_event(
                "ERROR",
                "input_lock_timeout",
                operation=op,
                timeout_sec=timeout_sec,
            )
            raise

    def _consume_step_duration_ms(self, step_uuid: str) -> int | None:
        started = self._step_started_at.pop(step_uuid, None)
        if started is None:
            return None
        return max(0, int((time.perf_counter() - started) * 1000))

    def _start_structured_run_log(self, resumed: bool):
        self._run_finish_emitted = False
        self._step_started_at.clear()
        try:
            path = self._structured_logger.open()
            if path is not None:
                self.structured_log_path = str(path)
        except Exception as e:
            self.logger.debug("structured log open failed: %s", e)
        event_name = "run_resumed" if resumed else "run_started"
        self._write_structured_event(
            "INFO",
            event_name,
            dry_run=bool(self.dry_run),
            human_mode=bool(self.human_mode),
            perf_mode=bool(self.perf_mode),
            start_index=int(self.start_index),
            repeat_count=int(getattr(self.repeat, "repeat_count", 0) or 0),
            stop_on_fail=bool(getattr(self.repeat, "stop_on_fail", False)),
            max_duration_ms=int(getattr(self.repeat, "max_duration_ms", 0) or 0),
            target_window_title=str(self.target_window_title or ""),
        )

    def _finish_run(self, success: bool, reason: str = ""):
        if self._run_finish_emitted:
            return
        self._run_finish_emitted = True
        duration_ms = None
        try:
            started_at = float(getattr(self, "_run_started_at", 0) or 0)
            if started_at > 0:
                duration_ms = max(0, int((time.time() - started_at) * 1000))
        except Exception:
            duration_ms = None
        self._write_structured_event(
            "INFO" if success else "ERROR",
            "run_finished",
            success=bool(success),
            reason=str(reason or ""),
            duration_ms=duration_ms,
        )
        self.finished.emit(bool(success))

    def _emit_step_started(self, step: StepData):
        step_uuid = self._runtime_step_uuid(step)
        step_name = str(getattr(step, "name", "") or "")
        self._step_started_at[step_uuid] = time.perf_counter()
        self._write_structured_event(
            "INFO",
            "step_started",
            step_uuid=step_uuid,
            step_name=step_name,
            step_type=str(getattr(step, "type", "") or ""),
        )
        try:
            self.stepStarted.emit(step_uuid, step_name)
        except Exception as e:
            self.logger.debug("stepStarted emit failed: %s", e)

    def _emit_step_succeeded(self, step: StepData):
        step_uuid = self._runtime_step_uuid(step)
        step_name = str(getattr(step, "name", "") or "")
        duration_ms = self._consume_step_duration_ms(step_uuid)
        self._write_structured_event(
            "INFO",
            "step_succeeded",
            step_uuid=step_uuid,
            step_name=step_name,
            duration_ms=duration_ms,
        )
        try:
            self.stepSucceeded.emit(step_uuid)
        except Exception as e:
            self.logger.debug("stepSucceeded emit failed: %s", e)

    def _emit_step_failed(self, step: StepData, error_message: str):
        step_uuid = self._runtime_step_uuid(step)
        step_name = str(getattr(step, "name", "") or "")
        message = str(error_message or "step failed")
        duration_ms = self._consume_step_duration_ms(step_uuid)
        self._write_structured_event(
            "ERROR",
            "step_failed",
            step_uuid=step_uuid,
            step_name=step_name,
            error=message,
            duration_ms=duration_ms,
        )
        try:
            self.stepFailed.emit(step_uuid, step_name, message)
        except Exception as e:
            self.logger.debug("stepFailed emit failed: %s", e)

    def stop(self):
        self._stop = True
        self._pause_event.set()
        self._write_structured_event("INFO", "run_stop_requested")

    def kill(self, reason: str = "hotkey_kill"):
        self._killed = True
        self._stop = True
        self._paused = False
        self._pause_event.set()
        self._write_structured_event("ERROR", "run_killed", reason=str(reason or "hotkey_kill"))

    def pause(self) -> bool:
        if self._stop or self._paused:
            return False
        self._paused = True
        self._pause_event.clear()
        self._write_structured_event("INFO", "run_paused")
        return True

    def resume_run(self) -> bool:
        if not self._paused:
            return False
        self._paused = False
        self._pause_event.set()
        self._write_structured_event("INFO", "run_resumed")
        return True

    def is_paused(self) -> bool:
        return bool(self._paused)

    def _wait_if_paused(self) -> bool:
        while self._paused and not self._stop:
            self._pause_event.wait()
        return bool(self._stop)

    def snapshot_state(self) -> dict:
        return {
            "variable_context": dict(self.variable_context) if self.variable_context else {},
            "counters": dict(self._counters) if self._counters else {},
            "default_counter": self._default_counter,
            "data_list": list(self._data_list) if self._data_list else None,
            "data_rows": list(self._data_rows) if self._data_rows else None,
            "data_row_values": list(self._data_row_values) if self._data_row_values else None,
            "data_columns": list(self._data_columns) if self._data_columns else [],
            "primary_data_column": self._primary_data_column,
            "data_index": self._data_index,
            "loop_counters": dict(self._loop_counters) if self._loop_counters else {},
            "call_stack": list(self.call_stack) if self.call_stack else [],
            "steps": self.steps,
            "current_file_path": self.current_file_path,
            "run_id": self.run_id,
            "run_started_at": getattr(self, "_run_started_at", None),
            "max_duration_fired": self._max_duration_fired,
        }

    def resume(self, start_index: int, resume_state: dict | None = None) -> None:
        if self.isRunning():
            return
        try:
            self.start_index = int(start_index)
        except Exception:
            self.start_index = 0
        if resume_state is not None:
            self._resume_state = resume_state
        super().start()

    def _apply_perf_settings(self):
        try:
            if self.perf_mode:
                pyautogui.PAUSE = 0
                if hasattr(pyautogui, "MINIMUM_DURATION"):
                    pyautogui.MINIMUM_DURATION = 0
                if hasattr(pyautogui, "MINIMUM_SLEEP"):
                    pyautogui.MINIMUM_SLEEP = 0
            else:
                pyautogui.PAUSE = self._pyautogui_defaults.get("PAUSE", 0)
                if hasattr(pyautogui, "MINIMUM_DURATION"):
                    pyautogui.MINIMUM_DURATION = self._pyautogui_defaults.get("MINIMUM_DURATION", 0)
                if hasattr(pyautogui, "MINIMUM_SLEEP"):
                    pyautogui.MINIMUM_SLEEP = self._pyautogui_defaults.get("MINIMUM_SLEEP", 0)
        except Exception as e:
            self.logger.warning("Failed to apply performance settings: %s", e)

    def run(self):
        self._stop = False
        self._killed = False
        self._paused = False
        self._pause_event.set()
        self._apply_perf_settings()
        resume_state = self._resume_state
        self._resume_state = None
        if resume_state is not None:
            self._max_duration_fired = bool(resume_state.get("max_duration_fired", False))
            restored_run_id = str(resume_state.get("run_id", "") or "").strip()
            if restored_run_id:
                self.run_id = restored_run_id
                try:
                    self._structured_logger.run_id = self.run_id
                except Exception:
                    pass
            started_at = resume_state.get("run_started_at")
            self._run_started_at = started_at if isinstance(started_at, (int, float)) else time.time()
            self._counters = dict(resume_state.get("counters") or {})
            self._default_counter = int(resume_state.get("default_counter") or 1)
            self._data_list = resume_state.get("data_list")
            self._data_index = int(resume_state.get("data_index") or 0)
            self._data_rows = resume_state.get("data_rows")
            self._data_row_values = resume_state.get("data_row_values")
            self._data_columns = list(resume_state.get("data_columns") or [])
            self._primary_data_column = resume_state.get("primary_data_column")
            self.variable_context = dict(resume_state.get("variable_context") or {})
            self._loop_counters = dict(resume_state.get("loop_counters") or {})
            self.call_stack = list(resume_state.get("call_stack") or [])
            steps = resume_state.get("steps")
            if steps is not None:
                self.steps = steps
            path = resume_state.get("current_file_path")
            if path is not None:
                self.current_file_path = path
        else:
            self._max_duration_fired = False
            self._run_started_at = time.time()
            self._counters = {}
            self._default_counter = 1
            self._data_list = None
            self._data_index = 0
            self._data_rows = None
            self._data_row_values = None
            self._data_columns = []
            self._primary_data_column = None
            self.variable_context = {}
            self._loop_counters = {}
        run_started_at = self._run_started_at
        self._start_structured_run_log(resume_state is not None)
        self._set_engine_state("RUNNING")
        
        try:
        # Attempt to activate target window before capture loop
            if self.target_window_title:
                try:
                    hwnd = self._window_manager.find_window(self.target_window_title)
                    if hwnd:
                        self._window_manager.activate_window(hwnd)
                    else:
                        self.logger.warning(
                            "Target window '%s' not found. Continuing anyway...", self.target_window_title
                        )
                except Exception:
                    # Do not abort if activation fails
                    tw_error = TargetWindowError(
                        f"target window activation failed: {self.target_window_title}"
                    )
                    self._write_structured_event(
                        "ERROR",
                        "target_window_error",
                        exception_type=tw_error.__class__.__name__,
                        error=str(tw_error),
                    )
                    self.logger.exception("Failed to activate target window (continuing)")
            with mss.mss() as sct:
                mon = sct.monitors[0]
                loop_idx = 0
                
                while not self._stop:
                    if self._wait_if_paused():
                        break
                    if self._max_duration_expired(run_started_at):
                        self._finish_run(False, reason="max_duration")
                        return

                    if self.repeat.repeat_count > 0 and loop_idx >= self.repeat.repeat_count:
                        self.log.emit(f"Finished {self.repeat.repeat_count} loops.")
                        break
                    
                    if loop_idx > 0:
                        self.log.emit(f"--- Loop {loop_idx + 1} ---")
                    else:
                        self.log.emit("--- Started ---")

                    # Execute steps
                    i = self.start_index if loop_idx == 0 else 0
                    hops = 0
                    id2idx = {s.id: idx for idx, s in enumerate(self.steps)}
                    
                    while True:
                        if self._wait_if_paused():
                            break
                        if i >= len(self.steps):
                            if self.call_stack:
                                state = self.call_stack.pop()
                                self.steps = state["steps"]
                                self.current_file_path = state.get("path")
                                i = state["index"] + 1
                                id2idx = {s.id: idx for idx, s in enumerate(self.steps)}
                                self.log.emit("Returning from sub-script to parent.")
                                continue
                            else:
                                break
                        if self._stop: break
                        if self._max_duration_expired(run_started_at):
                            self._finish_run(False, reason="max_duration")
                            return
                        
                        if hops > 2000:
                            self.log.emit("!! Too many jumps (infinite loop?). Stopping.")
                            self._finish_run(False, reason="too_many_jumps")
                            return

                        self.current_step_index = i # Update current step index
                        if not self.call_stack:
                            try:
                                self.stepChanged.emit(i)
                            except Exception as e:
                                self.logger.debug("stepChanged emit failed at index %s: %s", i, e)
                        step = self.steps[i]
                        self._emit_step_started(step)
                        emitted_failed = False
                        retry_attempts = 0
                        max_retry_attempts = self._resolve_resource_retry_attempts(step)
                        retry_delay_ms = self._resolve_resource_retry_delay_ms(step)
                        ok = False
                        fail_goto_id = None
                        steps_consumed = 0
                        while True:
                            try:
                                ok, fail_goto_id, steps_consumed = self._exec_step(sct, mon, step, i)
                                if retry_attempts > 0:
                                    self.log.emit(
                                        f"  -> Retry success at step {i+1} after {retry_attempts} attempt(s)."
                                    )
                                    self._write_structured_event(
                                        "INFO",
                                        "step_retry_success",
                                        step_uuid=self._runtime_step_uuid(step),
                                        step_index=int(i),
                                        step_name=str(getattr(step, "name", "") or ""),
                                        retry_attempts=int(retry_attempts),
                                    )
                                break
                            except Exception as e:
                                macro_error = self._to_macro_error(e, step=step, idx=i)
                                can_retry = (
                                    isinstance(macro_error, ResourceError)
                                    and self._is_resource_retry_target_step(step)
                                    and retry_attempts < max_retry_attempts
                                    and not self._stop
                                )
                                if can_retry:
                                    retry_attempts += 1
                                    self.log.emit(
                                        f"  -> Retry {retry_attempts}/{max_retry_attempts} for step {i+1}: {macro_error}"
                                    )
                                    self._write_structured_event(
                                        "WARN",
                                        "step_retry",
                                        step_uuid=self._runtime_step_uuid(step),
                                        step_index=int(i),
                                        step_name=str(getattr(step, "name", "") or ""),
                                        retry_attempt=int(retry_attempts),
                                        retry_max=int(max_retry_attempts),
                                        retry_delay_ms=int(retry_delay_ms),
                                        exception_type=macro_error.__class__.__name__,
                                        error=str(macro_error),
                                    )
                                    if retry_delay_ms > 0:
                                        self.msleep(int(retry_delay_ms))
                                    if self._stop:
                                        break
                                    continue

                                self.log.emit(
                                    f"!! Step {i+1} error [{macro_error.__class__.__name__}]: {macro_error}"
                                )
                                traceback.print_exc()
                                if isinstance(macro_error, ActionError):
                                    self._attempt_action_error_recovery(step, i, macro_error)
                                self._emit_step_exception_telemetry(step, i, macro_error)
                                self._emit_step_failed(
                                    step,
                                    f"[{macro_error.__class__.__name__}] {macro_error}",
                                )
                                emitted_failed = True
                                ok = False
                                fail_goto_id = None
                                steps_consumed = 0
                                break
                        # Handle sub-script switch
                        if self._switch_steps is not None:
                            self.steps = self._switch_steps
                            self.current_file_path = self._switch_path
                            self._switch_steps = None
                            self._switch_path = None
                            id2idx = {s.id: idx for idx, s in enumerate(self.steps)}
                            i = -1  # will become 0 after increment
                            continue

                        if not ok:
                            if not emitted_failed:
                                self._emit_step_failed(step, "step returned failure")
                            if self.capture_on_fail:
                                self._screenshot_roi(sct, StepData(
                                    id="fail_cap", name="Fail Capture", type="screenshot_roi",
                                    screenshot_filepath=os.path.join(self._fail_capture_dir, f"fail_loop{loop_idx+1}_step{i+1}_{int(time.time())}.png"),
                                    screenshot_roi_x=0, screenshot_roi_y=0, screenshot_roi_w=0, screenshot_roi_h=0
                                ))
                            
                            if step.branch_on_fail_goto_id:
                                jump_to_idx = id2idx.get(step.branch_on_fail_goto_id)
                                if jump_to_idx is not None:
                                    self.log.emit(f"  -> Step FAIL. Jumping to {jump_to_idx + 1}")
                                    i = jump_to_idx
                                    hops += 1
                                    continue
                                else:
                                    self.log.emit(f"  !! Jump target {step.branch_on_fail_goto_id} not found.")
                            
                            if self.repeat.stop_on_fail:
                                self.log.emit(f"Step {i+1} ('{step.name}') FAILED. Stopping.")
                                self._finish_run(False, reason="step_failed_stop_on_fail")
                                return
                        else:
                            self._emit_step_succeeded(step)
                            # Success
                            if fail_goto_id: # Actually success_goto_id in this context (e.g. from compare/branch)
                                jump_to_idx = id2idx.get(fail_goto_id)
                                if jump_to_idx is not None:
                                    self.log.emit(f"  -> Condition MET. Jumping to {jump_to_idx + 1}")
                                    i = jump_to_idx
                                    hops += 1
                                    continue
                        
                        # small guard sleep to avoid tight CPU spinning
                        if self.poll_interval and self.poll_interval > 0:
                            self.msleep(int(self.poll_interval * 1000))
                        i += 1 + steps_consumed
                    
                    loop_idx += 1
                    if self.repeat.repeat_count > 0 and loop_idx >= self.repeat.repeat_count:
                        break
                        
                    # Cooldown
                    remaining = self.repeat.repeat_cooldown_ms / 1000.0
                    while remaining > 0 and not self._stop:
                        if self._wait_if_paused():
                            break
                        if self._max_duration_expired(run_started_at):
                            self._finish_run(False, reason="max_duration")
                            return
                        chunk = min(0.25, remaining)
                        self.msleep(int(chunk * 1000))
                        remaining -= chunk

            if self._killed:
                self._finish_run(False, reason="killed")
            else:
                self._finish_run(True, reason="completed")
        except MacroBaseError as e:
            self.log.emit(f"!! runner exception [{e.__class__.__name__}]: {e}")
            self._logger.exception("Runner macro exception", exc_info=e)
            self.errorOccurred.emit(f"{e.__class__.__name__}: {e}")
            self._write_structured_event(
                "ERROR",
                "run_exception",
                exception_type=e.__class__.__name__,
                step_index=int(getattr(self, "current_step_index", -1)),
                error=str(e),
            )
            self._finish_run(False, reason=e.__class__.__name__)
        except Exception as e:
            macro_error = self._to_macro_error(e, idx=getattr(self, "current_step_index", -1))
            self.log.emit(f"!! runner exception [{macro_error.__class__.__name__}]: {macro_error}")
            tb = traceback.format_exc()
            self.log.emit(tb)
            self._logger.exception("Runner exception", exc_info=macro_error)
            self.errorOccurred.emit(f"{macro_error.__class__.__name__}: {macro_error}")
            self._write_structured_event(
                "ERROR",
                "run_exception",
                exception_type=macro_error.__class__.__name__,
                step_index=int(getattr(self, "current_step_index", -1)),
                error=str(macro_error),
            )
            self._finish_run(False, reason=macro_error.__class__.__name__)
        finally:
            self._set_engine_state("IDLE")
            self._paused = False
            self._pause_event.set()
            try:
                self._release_runtime_controls()
            except Exception:
                pass
            try:
                self._structured_logger.close()
            except Exception:
                pass

    def _max_duration_expired(self, start_time):
        if self.repeat.max_duration_ms > 0:
            if (time.time() - start_time) * 1000 > self.repeat.max_duration_ms:
                if not self._max_duration_fired:
                    self.log.emit("Max duration reached.")
                    self._max_duration_fired = True
                return True
        return False

    def _exec_step(self, sct, mon, s: StepData, idx: int) -> tuple[bool, str | None, int]:
        if hasattr(s, 'pre_delay_ms') and s.pre_delay_ms > 10:
            self.log.emit(f"  -> Pre-delay: {s.pre_delay_ms} ms")
            self.msleep(int(s.pre_delay_ms))

        steps_consumed = 0
        self._validate_step_resources(s)

        handler = self._step_handlers.get(s.type)
        if handler:
            # Normalize signatures if needed, but for now we used lambdas in __init__ to adapt them
            # Some handlers take (sct, mon, s, idx), others take less.
            # The lambdas in _step_handlers ensure they all accept (sct, mon, s, idx) and return (ok, goto_id, steps_consumed)
            try:
                return handler(sct, mon, s, idx)
            except Exception as e:
                raise self._to_macro_error(e, step=s, idx=idx) from e
        
        raise ActionError(f"unknown step type: {s.type}")

    def msleep(self, ms):
        if ms <= 0: return
        end_time = time.time() + (ms / 1000.0)
        while time.time() < end_time:
            if self._wait_if_paused():
                break
            if self._stop: break
            rem = end_time - time.time()
            time.sleep(min(0.01, rem))

    def _image_click(self, sct, mon, s: StepData, idx: int) -> tuple[bool, str | None, int]:
        # Logic for image matching and clicking
        # Simplified for brevity, but should include full logic
        t0 = time.time()
        self._normalize_step_template_path(s)
        
        # Determine ROI
        capture_region = self._region_for_step(mon, s)
        if capture_region is None:
            capture_region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
        
        capture_region = dict(capture_region) # copy
        
        while (time.time() - t0) * 1000 <= int(s.timeout_ms):
            if self._wait_if_paused():
                return (False, None, 0)
            if self._stop: return (False, None, 0)
            
            raw = sct.grab(capture_region)
            frame = np.frombuffer(raw.rgb, dtype=np.uint8).reshape(raw.height, raw.width, 3)
            
            # Find all targets if requested
            if s.find_all_targets:
                results = self._matcher.find_all(frame, s)
                if results:
                    self.log.emit(f"  -> Found {len(results)} targets.")
                    for (cx, cy, score) in results:
                        if self._wait_if_paused():
                            return (False, None, 0)
                        if self._stop:
                            break
                        real_x = capture_region["left"] + cx
                        real_y = capture_region["top"] + cy
                        real_x, real_y = self._resolve_click_anchor_xy(s, real_x, real_y)
                        if self.dry_run:
                            self.requestCrosshair.emit(real_x, real_y, 200)
                        else:
                            self._perform_click(real_x, real_y, s)
                    return (True, None, 0)
            
            # Single target
            mr = self._matcher.find_best_optimized(frame, s)
            if mr.ok:
                cx = capture_region["left"] + int(mr.x)
                cy = capture_region["top"] + int(mr.y)
                click_x, click_y = self._resolve_click_anchor_xy(
                    s,
                    cx,
                    cy,
                    int(getattr(mr, "w", 0) or 0),
                    int(getattr(mr, "h", 0) or 0),
                )
                self.log.emit(f"  -> Match: {s.name} ({mr.score:.2f}) at {cx},{cy}")
                try:
                    self.debugEvent.emit({"rect": (cx - 20, cy - 20, 40, 40), "text": f"{s.name} {mr.score:.2f}", "color": (0, 255, 0)})
                except Exception as e:
                    self.logger.debug("debugEvent emit failed for image_click: %s", e)
                
                s._last_match_xy = (click_x, click_y)
                if self.dry_run:
                    self.requestCrosshair.emit(click_x, click_y, 200)
                else:
                    self._perform_click(click_x, click_y, s)

                # Loop until the image disappears (optional)
                if getattr(s, "loop_until_hide", False):
                    end_ts = time.time() + (max(1, int(s.timeout_ms)) / 1000.0)
                    while not self._stop and time.time() < end_ts:
                        if self._wait_if_paused():
                            return (False, None, 0)
                        self.msleep(int(s.poll_ms))
                        raw2 = sct.grab(capture_region)
                        frame2 = np.frombuffer(raw2.rgb, dtype=np.uint8).reshape(raw2.height, raw2.width, 3)
                        mr2 = self._matcher.find_best_optimized(frame2, s)
                        if mr2.ok:
                            cx2 = capture_region["left"] + int(mr2.x)
                            cy2 = capture_region["top"] + int(mr2.y)
                            click_x2, click_y2 = self._resolve_click_anchor_xy(
                                s,
                                cx2,
                                cy2,
                                int(getattr(mr2, "w", 0) or 0),
                                int(getattr(mr2, "h", 0) or 0),
                            )
                            self.log.emit(f"  -> Still visible ({mr2.score:.2f}), re-click at {cx2},{cy2}")
                            if not self.dry_run:
                                self._perform_click(click_x2, click_y2, s)
                            continue
                        # image disappeared -> success
                        self.log.emit("  -> Image hidden; stop clicking.")
                        return (True, s.on_match_goto_id, 0)
                    # timeout while still visible
                    self.log.emit("  !! loop_until_hide: timeout while image still visible.")
                    return (False, None, 0)

                if getattr(s, "hold_until_next", False):
                    next_img = self._peek_next_image_step(idx + 1)
                    if next_img and not self._hold_until_next_image(sct, mon, s, next_img):
                        return (False, None, 0)
                return (True, s.on_match_goto_id, 0)
            
            self.msleep(int(s.poll_ms))
            
        self.log.emit(f"  !! Timeout: {s.name}")
        return (False, None, 0)

    def _wait_for_image(self, sct, mon, s: StepData, idx: int) -> tuple[bool, str | None, int]:
        t0 = time.time()
        self._normalize_step_template_path(s)

        capture_region = self._region_for_step(mon, s)
        if capture_region is None:
            capture_region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
        capture_region = dict(capture_region)

        while (time.time() - t0) * 1000 <= int(s.timeout_ms):
            if self._wait_if_paused():
                return (False, None, 0)
            if self._stop:
                return (False, None, 0)

            raw = sct.grab(capture_region)
            frame = np.frombuffer(raw.rgb, dtype=np.uint8).reshape(raw.height, raw.width, 3)
            mr = self._matcher.find_best_optimized(frame, s)
            if mr.ok:
                cx = capture_region["left"] + int(mr.x)
                cy = capture_region["top"] + int(mr.y)
                anchor_x, anchor_y = self._resolve_click_anchor_xy(
                    s,
                    cx,
                    cy,
                    int(getattr(mr, "w", 0) or 0),
                    int(getattr(mr, "h", 0) or 0),
                )
                s._last_match_xy = (anchor_x, anchor_y)
                self.log.emit(f"  -> Wait match: {s.name} ({mr.score:.2f}) at {cx},{cy}")
                try:
                    self.debugEvent.emit(
                        {"rect": (cx - 20, cy - 20, 40, 40), "text": f"{s.name} {mr.score:.2f}", "color": (0, 180, 255)}
                    )
                except Exception as e:
                    self.logger.debug("debugEvent emit failed for wait_for_image: %s", e)
                if self.dry_run:
                    self.requestCrosshair.emit(anchor_x, anchor_y, 200)
                return (True, s.on_match_goto_id, 0)
            self.msleep(int(s.poll_ms))

        self.log.emit(f"  !! Timeout(wait_for_image): {s.name}")
        return (False, None, 0)

    def _image_branch(self, sct, mon, step: StepData) -> tuple[bool, str | None]:
        self._normalize_step_template_path(step)
        # Support variable/OCR-based branching when branch_mode == "variable"
        if getattr(step, "branch_mode", "image") == "variable":
            source = getattr(step, "branch_value_source", "variable") or "variable"
            var_name = getattr(step, "branch_var", "") or ""
            op = getattr(step, "branch_op", "")
            val = getattr(step, "branch_value", "")
            true_id = getattr(step, "target_true_id", None) or getattr(step, "branch_true_goto_id", None)
            false_id = getattr(step, "target_false_id", None) or getattr(step, "branch_false_goto_id", None)

            ctx_val = None
            if source == "ocr":
                # perform OCR on ROI
                if sct is None or mon is None:
                    self.log.emit("  !! OCR branch: no screen capture available. Branch FALSE.")
                else:
                    roi = {
                        "left": getattr(step, "ocr_roi_x", 0),
                        "top": getattr(step, "ocr_roi_y", 0),
                        "width": getattr(step, "ocr_roi_w", 0),
                        "height": getattr(step, "ocr_roi_h", 0),
                    }
                    if roi["width"] <= 0 or roi["height"] <= 0:
                        roi = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
                    raw = sct.grab(roi)
                    frame = np.frombuffer(raw.rgb, dtype=np.uint8).reshape(raw.height, raw.width, 3).copy()
                    try:
                        scale = self._resolve_ocr_scale(frame, step)
                        ip = ImageProcessor(
                            scale_factor=scale,
                            invert=bool(getattr(step, "ocr_invert", False)),
                            threshold_mode=getattr(step, "ocr_preprocess_mode", "otsu") or "otsu",
                        )
                        ctx_val = ip.extract_number(frame, psm_mode=6)
                    except Exception as e:
                        self.log.emit(f"  !! OCR branch error: {e}")
                        ctx_val = None
                    self.log.emit(f"  -> OCR branch read: {ctx_val}")
                    if getattr(step, "ocr_save_enabled", False):
                        varname = getattr(step, "ocr_save_var", "") or ""
                        if varname:
                            self.variable_context[varname] = ctx_val
                            self.log.emit(f"  -> OCR Branch: Saved {ctx_val} to {varname}")
            else:
                ctx_val = self.variable_context.get(var_name, None) if var_name else None

            result = False
            if ctx_val is None:
                self.log.emit(f"  !! Branch source value missing. Branch FALSE.")
                result = False
            else:
                try:
                    result, _ = self.evaluator.evaluate(step, self.variable_context, actual_value=ctx_val)
                except Exception:
                    self.logger.exception("branch evaluate failed; treating as FALSE.")
                    result = False
                self.log.emit(f"  -> Branch check: {source} {var_name} {op} {val} => {result}")
            goto = true_id if result else false_id
            return True, goto

        t0 = time.time()
        capture_region = self._region_for_step(mon, step)
        if capture_region is None:
            capture_region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
        capture_region = dict(capture_region)
        
        while (time.time() - t0) * 1000 <= int(step.timeout_ms):
            if self._wait_if_paused():
                return (False, None)
            if self._stop: return (False, None)
            
            raw = sct.grab(capture_region)
            frame = np.frombuffer(raw.rgb, dtype=np.uint8).reshape(raw.height, raw.width, 3).copy()
            
            for target in step.conditional_targets:
                # Build temporary step for matching
                temp_step = self._build_target_step(step, target)
                
                # Note: If temp_step has a specific ROI, we are currently matching against the PARENT step's ROI capture.
                # If strict ROI matching is needed for branches, we would need to re-capture or crop 'frame'.
                # For performance, we use the parent capture. If target ROI is critical, user should ensure parent ROI covers it.
                
                mr = self._matcher.find_best_optimized(frame, temp_step)
                if mr.ok:
                    target_region = capture_region
                    
                    cx = target_region["left"] + int(mr.x)
                    cy = target_region["top"] + int(mr.y)
                    click_x, click_y = self._resolve_click_anchor_xy(
                        temp_step,
                        cx,
                        cy,
                        int(getattr(mr, "w", 0) or 0),
                        int(getattr(mr, "h", 0) or 0),
                    )
                    self.log.emit(f"  -> Branch found: '{target.get('name', '')}' at ({cx},{cy})")
                    try:
                        self.debugEvent.emit({"rect": (cx - 20, cy - 20, 40, 40), "text": f"{target.get('name','')} {mr.score:.2f}", "color": (0, 200, 255)})
                    except Exception as e:
                        self.logger.debug("debugEvent emit failed for conditional branch: %s", e)
                    
                    if not self.dry_run:
                        self._perform_click(click_x, click_y, temp_step)
                    else:
                        self.requestCrosshair.emit(click_x, click_y, 200)
                        
                    return (True, target.get('goto_id'))
            
            self.msleep(int(step.poll_ms))
            
        self.log.emit("  !! Branch timeout: No target found.")
        return (False, None)

    def _peek_next_image_step(self, start_index: int) -> StepData | None:
        for j in range(start_index, len(self.steps)):
            candidate = self.steps[j]
            if candidate.type in {"image_click", "wait_for_image"}:
                return candidate
        return None

    def _hold_until_next_image(self, sct, mon, current_step: StepData, next_step: StepData) -> bool:
        timeout_ms = int(getattr(current_step, "hold_timeout_ms", current_step.timeout_ms or 0) or 0)
        interval_ms = max(10, int(getattr(current_step, "hold_reclick_interval_ms", 500) or 500))
        release_consecutive = max(1, int(getattr(current_step, "hold_release_consecutive", 1) or 1))
        reacquire = bool(getattr(current_step, "hold_reacquire_each_time", False))
        region_a = self._region_for_step(mon, current_step)
        region_b = self._region_for_step(mon, next_step)
        if region_a is None:
            region_a = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
        if region_b is None:
            region_b = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
        t0 = time.time()
        last_click = time.time()
        consecutive_matches = 0
        while timeout_ms <= 0 or (time.time() - t0) * 1000 <= timeout_ms:
            if self._wait_if_paused():
                return False
            if self._stop:
                return False
            try:
                frameB = np.array(sct.grab(region_b), dtype=np.uint8)[:, :, :3].copy()
            except Exception:
                break
            mrB = self._matcher.find_best_optimized(frameB, next_step)
            if mrB and mrB.ok:
                consecutive_matches += 1
                if consecutive_matches >= release_consecutive:
                    self.log.emit("  -> Next image detected. Releasing hold.")
                    return True
            else:
                consecutive_matches = 0
            if (time.time() - last_click) * 1000 >= interval_ms:
                ax = ay = None
                if reacquire or not getattr(current_step, "_last_match_xy", None):
                    try:
                        frameA = np.array(sct.grab(region_a), dtype=np.uint8)[:, :, :3].copy()
                        mrA = self._matcher.find_best_optimized(frameA, current_step)
                        if mrA and mrA.ok:
                            ax = region_a["left"] + int(mrA.x)
                            ay = region_a["top"] + int(mrA.y)
                            ax, ay = self._resolve_click_anchor_xy(
                                current_step,
                                ax,
                                ay,
                                int(getattr(mrA, "w", 0) or 0),
                                int(getattr(mrA, "h", 0) or 0),
                            )
                            current_step._last_match_xy = (ax, ay)
                    except Exception:
                        ax = ay = None
                else:
                    ax, ay = current_step._last_match_xy
                if ax is not None and ay is not None:
                    if self.dry_run:
                        self.requestCrosshair.emit(int(ax), int(ay), 200)
                    else:
                        self._perform_click(int(ax), int(ay), current_step)
                    last_click = time.time()
            self.msleep(int(current_step.poll_ms))
        return False

    def _build_target_step(self, parent_step: StepData, target: dict) -> StepData:
        temp_step = StepData(
            id=target.get("id", "target"),
            name=target.get("name", "target"),
            type="image_click",
            png_bytes=target.get("png_bytes"),
        )
        for field in BRANCH_TARGET_MATCH_FIELDS + BRANCH_TARGET_CLICK_FIELDS:
            parent_val = getattr(parent_step, field, None)
            value = target.get(field, parent_val)
            try:
                setattr(temp_step, field, value)
            except Exception as e:
                self.logger.debug("Failed to copy field '%s' to branch target step: %s", field, e)
        
        if not getattr(temp_step, "threshold", None):
            temp_step.threshold = float(getattr(temp_step, "min_confidence", parent_step.min_confidence))
        temp_step.min_confidence = float(getattr(temp_step, "min_confidence", temp_step.threshold))
        
        # ROI override
        if target.get("search_roi_enabled"):
            temp_step.search_roi_enabled = True
            temp_step.search_roi_left = int(target.get("search_roi_left", 0))
            temp_step.search_roi_top = int(target.get("search_roi_top", 0))
            temp_step.search_roi_width = int(target.get("search_roi_width", 0))
            temp_step.search_roi_height = int(target.get("search_roi_height", 0))
        else:
            temp_step.search_roi_enabled = parent_step.search_roi_enabled
            temp_step.search_roi_left = parent_step.search_roi_left
            temp_step.search_roi_top = parent_step.search_roi_top
            temp_step.search_roi_width = parent_step.search_roi_width
            temp_step.search_roi_height = parent_step.search_roi_height
            
        return temp_step

    def _perform_click(self, x, y, s: StepData):
        action = self._resolve_action_mode(s)
        if action == "none":
            return
        
        # Jitter
        if s.jitter > 0:
            x += np.random.randint(-s.jitter, s.jitter + 1)
            y += np.random.randint(-s.jitter, s.jitter + 1)
            
        # Offset
        x += int(s.click_offset_x)
        y += int(s.click_offset_y)
        
        # Pre-move sleep
        if s.pre_move_sleep_ms > 0:
            self.msleep(s.pre_move_sleep_ms)
            
        # Move
        # Move & Click
        btn = getattr(s, "click_button", None) or getattr(s, "click_btn", None) or "left"
        double_click = bool(getattr(s, "click_double", False))
        if btn == "double":
            btn = "left"
            double_click = True
        if btn in ("move_only", "none", None, ""):
            btn = "left"
        duration = max(0, getattr(s, "press_duration_ms", 70)) / 1000.0

        with self._acquire_input_lock("click"):
            if self.dry_run:
                self.requestCrosshair.emit(int(x), int(y), 200)
            elif self.human_mode:
                self._human_mouse.click(int(x), int(y), button=btn, double=double_click, hold_sec=duration)
            else:
                pyautogui.moveTo(x, y)
                if action != "move":
                    if double_click:
                        for tap in range(2):
                            pyautogui.mouseDown(button=btn)
                            if duration > 0:
                                time.sleep(duration)
                            pyautogui.mouseUp(button=btn)
                            if tap == 0:
                                self.msleep(50)
                    else:
                        pyautogui.mouseDown(button=btn)
                        if duration > 0:
                            time.sleep(duration)
                        pyautogui.mouseUp(button=btn)
        # Post-click sleep (applies to human/direct)
        post_sleep = getattr(s, "post_click_sleep_ms", 0)
        if post_sleep > 0:
            self.msleep(post_sleep)

    def _resolve_click_anchor_xy(
        self,
        step: StepData,
        center_x: int,
        center_y: int,
        match_w: int = 0,
        match_h: int = 0,
    ) -> tuple[int, int]:
        anchor = str(getattr(step, "click_anchor", "center") or "center").strip().lower()
        if anchor in {"center", "centre"}:
            return int(center_x), int(center_y)

        w = int(match_w or 0)
        h = int(match_h or 0)
        if w <= 0 or h <= 0:
            tpl = step.ensure_tpl()
            if tpl is not None:
                h, w = tpl.shape[:2]
        if w <= 0 or h <= 0:
            return int(center_x), int(center_y)

        left = int(center_x) - int(w // 2)
        top = int(center_y) - int(h // 2)
        anchor_map: dict[str, tuple[int, int]] = {
            "top-left": (left, top),
            "topleft": (left, top),
            "top-right": (left + w - 1, top),
            "topright": (left + w - 1, top),
            "bottom-left": (left, top + h - 1),
            "bottomleft": (left, top + h - 1),
            "bottom-right": (left + w - 1, top + h - 1),
            "bottomright": (left + w - 1, top + h - 1),
        }
        return anchor_map.get(anchor, (int(center_x), int(center_y)))

    def _resolve_action_mode(self, step: StepData) -> str:
        action = getattr(step, "image_action", None)
        if action in {"click", "move", "none"}:
            return action
        legacy_button = getattr(step, "click_button", None) or getattr(step, "click_btn", None) or ""
        if legacy_button == "move_only":
            action = "move"
        elif legacy_button == "none":
            action = "none"
        else:
            action = "click"
        step.image_action = action
        return action

    def _split_key_action(self, raw: str | None) -> dict | None:
        text = self._process_dynamic_string(raw or "").strip()
        if not text:
            return None
        normalized = hk_normalize(text)
        mods, base = hk_to_tuple(normalized) if normalized else (set(), None)
        # Non-ASCII 단일 문자는 실제 키 코드로 보내면 실패하므로 text로 처리한다.
        if mods or (base and (len(base) == 1 or base in PHYSICAL_KEY_NAMES)):
            if base and len(base) == 1 and not base.isascii():
                return {"mods": set(), "base": None, "text": text}
            return {"mods": mods, "base": base, "text": None}
        if len(text) == 1:
            if not text.isascii():
                return {"mods": set(), "base": None, "text": text}
            return {"mods": set(), "base": text, "text": None}
        return {"mods": set(), "base": None, "text": text}

    def _text_paste(self, s: StepData) -> bool:
        """Paste text exactly using clipboard to handle IME/non-ASCII safely."""
        txt = self._process_dynamic_string(s.key_string or "")
        if not txt:
            return False
        if TemplateProcessor.has_unresolved_placeholder(txt):
            self.log.emit("!! text paste blocked: unresolved placeholder remains.")
            return False
        times = max(1, int(getattr(s, "key_times", 1) or 1))
        try:
            prev = self._get_clipboard_text()
            if not self._set_clipboard_text(txt):
                self.log.emit("!! clipboard unavailable for text paste.")
                return False
            self.msleep(30)
            if not self.dry_run:
                with self._acquire_input_lock("keyboard_paste"):
                    for _ in range(times):
                        pyautogui.hotkey("ctrl", "v")
                        if self._auto_enter_after_text:
                            pyautogui.press("enter")
                        self.msleep(20)
            self.msleep(30)
            if prev is not None:
                self._set_clipboard_text(prev)
            return True
        except Exception as e:
            self.log.emit(f"!! text paste error: {e}")
            return False

    def _get_clipboard_text(self) -> str | None:
        # Try pyperclip first (works from worker threads), fall back to QApplication
        pyperclip = None
        try:
            import pyperclip
        except Exception as e:
            self.logger.debug("pyperclip import failed (clipboard fallback): %s", e)
        if pyperclip is not None:
            try:
                return pyperclip.paste()
            except Exception as e:
                self.logger.debug("pyperclip paste failed; using QApplication clipboard: %s", e)
        try:
            return QApplication.clipboard().text()
        except Exception:
            return None

    def _set_clipboard_text(self, text: str) -> bool:
        pyperclip = None
        try:
            import pyperclip
        except Exception as e:
            self.logger.debug("pyperclip import failed (clipboard set fallback): %s", e)
        if pyperclip is not None:
            try:
                pyperclip.copy(text)
                return True
            except Exception as e:
                self.logger.debug("pyperclip copy failed; using QApplication clipboard: %s", e)
        try:
            QApplication.clipboard().setText(text)
            return True
        except Exception:
            return False

    def _map_key_name(self, key: str | None) -> str | None:
        if not key:
            return None
        key = key.lower()
        aliases = {
            "return": "enter",
            "esc": "esc",
            "escape": "esc",
            "pgup": "pageup",
            "pgdn": "pagedown",
            "caps": "capslock",
            "spacebar": "space",
        }
        if key in aliases:
            return aliases[key]
        return key

    def _press_with_modifiers(self, mods: set[str], base: str) -> bool:
        key_name = self._map_key_name(base)
        if not key_name:
            return False
        mod_names = [self._map_key_name(m) for m in sorted(mods)]
        if self.dry_run:
            return True
        with self._acquire_input_lock("keyboard_press"):
            try:
                for mk in mod_names:
                    if mk:
                        pyautogui.keyDown(mk)
                pyautogui.press(key_name)
            finally:
                for mk in reversed(mod_names):
                    if mk:
                        pyautogui.keyUp(mk)
        return True

    def _region_for_step(self, mon, step: StepData) -> dict | None:
        enabled = step.search_roi_enabled
        if enabled:
            return {
                "left": step.search_roi_left,
                "top": step.search_roi_top,
                "width": step.search_roi_width,
                "height": step.search_roi_height
            }
        return None

    def _key_press(self, s: StepData) -> tuple[bool, str | None]:
        data = self._split_key_action(s.key_string)
        if not data:
            return (False, None)
        repeat = max(1, int(getattr(s, "key_times", 1) or 1))
        if data["text"] is not None:
            if TemplateProcessor.has_unresolved_placeholder(data["text"]):
                self.log.emit("!! key typewrite blocked: unresolved placeholder remains.")
                return (False, None)
            if self.dry_run:
                return (True, None)
            with self._acquire_input_lock("keyboard_typewrite"):
                for _ in range(repeat):
                    pyautogui.typewrite(data["text"], interval=0)
                    if self._auto_enter_after_text and str(getattr(s, "type", "")).lower() in {"text", "keyboard"}:
                        pyautogui.press("enter")
            return (True, None)
        base = data["base"]
        if not base:
            return (False, None)
        pretty = hk_pretty(s.key_string) if s.key_string else base
        self.log.emit(f"  -> Key {pretty}")
        for _ in range(repeat):
            if not self._press_with_modifiers(data["mods"], base):
                return (False, None)
        return (True, None)

    def _key_down(self, s: StepData) -> tuple[bool, str | None]:
        data = self._split_key_action(s.key_string)
        if not data or data["text"] is not None or not data["base"]:
            return (False, None)
        key_name = self._map_key_name(data["base"])
        if not key_name:
            return (False, None)
        if self.dry_run:
            return (True, None)
        with self._acquire_input_lock("keyboard_keydown"):
            for mod in sorted(data["mods"]):
                mod_name = self._map_key_name(mod)
                if mod_name:
                    pyautogui.keyDown(mod_name)
            pyautogui.keyDown(key_name)
        return (True, None)

    def _key_up(self, s: StepData) -> tuple[bool, str | None]:
        data = self._split_key_action(s.key_string)
        if not data or data["text"] is not None or not data["base"]:
            return (False, None)
        key_name = self._map_key_name(data["base"])
        if not key_name:
            return (False, None)
        if self.dry_run:
            return (True, None)
        with self._acquire_input_lock("keyboard_keyup"):
            pyautogui.keyUp(key_name)
            for mod in sorted(data["mods"], reverse=True):
                mod_name = self._map_key_name(mod)
                if mod_name:
                    pyautogui.keyUp(mod_name)
        return (True, None)

    def _key_hold(self, s: StepData) -> tuple[bool, str | None]:
        data = self._split_key_action(s.key_string)
        if not data or data["text"] is not None or not data["base"]:
            return (False, None)
        key_name = self._map_key_name(data["base"])
        if not key_name:
            return (False, None)
        if self.dry_run:
            return (True, None)
        with self._acquire_input_lock("keyboard_keyhold"):
            try:
                for mod in sorted(data["mods"]):
                    mod_name = self._map_key_name(mod)
                    if mod_name:
                        pyautogui.keyDown(mod_name)
                pyautogui.keyDown(key_name)
                self.msleep(max(0, int(getattr(s, "hold_ms", 0))))
            finally:
                pyautogui.keyUp(key_name)
                for mod in sorted(data["mods"], reverse=True):
                    mod_name = self._map_key_name(mod)
                    if mod_name:
                        pyautogui.keyUp(mod_name)
        return (True, None)

    def _keyboard(self, s: StepData) -> tuple[bool, str | None]:
        mode = getattr(s, "keyboard_mode", None) or "text"
        if mode == "text":
            return (self._text_paste(s), None)
        if mode == "key":
            return self._key_press(s)
        if mode == "key_down":
            return self._key_down(s)
        if mode == "key_up":
            return self._key_up(s)
        if mode == "key_hold":
            return self._key_hold(s)
        self.log.emit(f"  !! Unknown keyboard mode: {mode}")
        return (False, None)

    def _mouse(self, s: StepData) -> tuple[bool, str | None]:
        mode = getattr(s, "mouse_mode", None) or "click_point"
        if mode == "drag":
            return (self._drag(s), None)
        if mode == "scroll":
            return self._scroll(s)
        if mode == "click_point":
            return self._click_point(s)
        self.log.emit(f"  !! Unknown mouse mode: {mode}")
        return (False, None)

    def _screen_check(self, sct, mon, s: StepData) -> tuple[bool, str | None]:
        mode = getattr(s, "screen_check_mode", None) or "pixel_check"
        if mode == "ocr_check_text":
            return self._ocr_check_text(sct, mon, s)
        if mode == "pixel_check":
            return self._pixel_check(s)
        self.log.emit(f"  !! Unknown screen_check mode: {mode}")
        return (False, None)

    def _file_action(self, s: StepData) -> tuple[bool, str | None]:
        mode = getattr(s, "file_action_mode", None) or "load_data_file"
        if mode == "run_macro":
            ok = self._log_enter_subscript() and self._handle_run_macro(s)
            return (ok, None)
        if mode == "load_data_file":
            return (self._load_data_file(s), None)
        self.log.emit(f"  !! Unknown file_action mode: {mode}")
        return (False, None)

    def _click_point(self, s: StepData) -> tuple[bool, str | None]:
        if s.click_x is None or s.click_y is None: return (False, None)
        if self.dry_run:
            self.requestCrosshair.emit(int(s.click_x), int(s.click_y), 200)
            return (True, None)
        try:
            btn = s.click_btn or "left"
            with self._acquire_input_lock("click_point"):
                if self.human_mode:
                    self._human_mouse.click(int(s.click_x), int(s.click_y), button=btn, double=bool(s.click_double))
                else:
                    pyautogui.moveTo(int(s.click_x), int(s.click_y))
                    if s.click_double:
                        pyautogui.doubleClick(button=btn)
                    else:
                        pyautogui.click(button=btn)
            return (True, None)
        except Exception as e:
            self.log.emit(f"!! click_point error: {e}")
            return (False, None)

    def _drag(self, s: StepData) -> bool:
        if None in (s.drag_from_x, s.drag_from_y, s.drag_to_x, s.drag_to_y):
            return False
        if self.dry_run:
            self.requestCrosshair.emit(int(s.drag_from_x), int(s.drag_from_y), 200)
            self.requestCrosshair.emit(int(s.drag_to_x), int(s.drag_to_y), 200)
            return True
        try:
            duration_sec = max(0.0, s.drag_duration_ms / 1000.0)
            with self._acquire_input_lock("drag"):
                if self.human_mode:
                    self._human_mouse.drag(int(s.drag_from_x), int(s.drag_from_y), int(s.drag_to_x), int(s.drag_to_y), duration=duration_sec)
                else:
                    pyautogui.moveTo(int(s.drag_from_x), int(s.drag_from_y))
                    pyautogui.mouseDown()
                    pyautogui.moveTo(int(s.drag_to_x), int(s.drag_to_y), duration=duration_sec, tween=pyautogui.easeInOutQuad)
                    pyautogui.mouseUp()
            return True
        except Exception as e:
            self.log.emit(f"!! drag error: {e}")
            return False

    def _mouse_move(self, s: StepData) -> bool:
        if s.click_x is None or s.click_y is None:
            return False
        if self.dry_run:
            self.requestCrosshair.emit(int(s.click_x), int(s.click_y), 200)
            return True
        try:
            with self._acquire_input_lock("mouse_move"):
                if self.human_mode:
                    self._human_mouse.move_to(int(s.click_x), int(s.click_y))
                else:
                    pyautogui.moveTo(int(s.click_x), int(s.click_y))
            return True
        except Exception as e:
            self.log.emit(f"!! mouse_move error: {e}")
            return False

    def _generic_click(self, s: StepData) -> tuple[bool, str | None]:
        btn = getattr(s, "click_btn", None) or "left"
        double = bool(getattr(s, "click_double", False))
        try:
            with self._acquire_input_lock("click"):
                if s.click_x is not None and s.click_y is not None:
                    if self.dry_run:
                        self.requestCrosshair.emit(int(s.click_x), int(s.click_y), 200)
                    else:
                        if self.human_mode:
                            self._human_mouse.move_to(int(s.click_x), int(s.click_y))
                        else:
                            pyautogui.moveTo(int(s.click_x), int(s.click_y))
                if self.dry_run:
                    return (True, None)
                if self.human_mode:
                    self._human_mouse.click(int(s.click_x or 0), int(s.click_y or 0), button=btn, double=double)
                else:
                    if double:
                        pyautogui.doubleClick(button=btn)
                    else:
                        pyautogui.click(button=btn)
            return (True, None)
        except Exception as e:
            self.log.emit(f"!! click error: {e}")
            return (False, None)

    def _drag_path(self, s: StepData) -> bool:
        path = s.drag_path or []
        if len(path) < 2:
            return self._drag(s)
        try:
            points = [(int(px), int(py), float(pt)) for px, py, pt in path]
        except Exception:
            points = []
            for node in path:
                try:
                    px, py = int(node[0]), int(node[1])
                    pt = float(node[2]) if len(node) > 2 else None
                    points.append((px, py, pt))
                except Exception:
                    continue
        if len(points) < 2:
            return self._drag(s)
        if self.dry_run:
            for px, py, _ in points[::max(1, len(points)//5)]:
                self.requestCrosshair.emit(px, py, 200)
            return True
        try:
            button = s.click_btn or s.click_button or "left"
            with self._acquire_input_lock("drag_path"):
                if self.human_mode:
                    self._human_mouse.drag_path(points, button=button)
                else:
                    pyautogui.moveTo(points[0][0], points[0][1])
                    pyautogui.mouseDown(button=button)
                    prev_t = points[0][2]
                    for px, py, ts in points[1:]:
                        if prev_t is not None and ts is not None:
                            delta = max(0.0, ts - prev_t)
                            if delta > 0.0:
                                time.sleep(delta)
                        pyautogui.moveTo(px, py)
                        prev_t = ts
                    pyautogui.mouseUp(button=button)
            return True
        except Exception as e:
            self.log.emit(f"!! drag_path error: {e}")
            return False

    def _wait_step(self, s: StepData) -> bool:
        duration = max(0, int(getattr(s, "wait_ms", 0) or 0))
        if duration > 0:
            self.log.emit(f"  -> Wait {duration} ms")
            self.msleep(duration)
        return True

    def _loop_placeholder(self, s: StepData) -> bool:
        self.log.emit("  -> Loop step encountered (no operation).")
        return True

    def _scroll(self, s: StepData) -> tuple[bool, str | None]:
        try:
            with self._acquire_input_lock("scroll"):
                for _ in range(max(1, int(s.scroll_times))):
                    pyautogui.hscroll(int(s.scroll_dx))
                    pyautogui.scroll(int(s.scroll_dy))
                    self.msleep(max(0, int(s.scroll_interval_ms)))
            return (True, None)
        except Exception as e:
            self.log.emit(f"!! scroll error: {e}")
            return (False, None)

    def _pixel_check(self, s: StepData) -> tuple[bool, str | None]:
        if s.pixel_x is None or s.pixel_y is None or not s.pixel_color_hex:
            return (False, None)
        try:
            target_rgb = self._hex_to_rgb(s.pixel_color_hex)
            screen_rgb = pyautogui.pixel(s.pixel_x, s.pixel_y)
            tolerance = s.pixel_color_tolerance
            diff_r = abs(target_rgb[0] - screen_rgb[0])
            diff_g = abs(target_rgb[1] - screen_rgb[1])
            diff_b = abs(target_rgb[2] - screen_rgb[2])
            if diff_r <= tolerance and diff_g <= tolerance and diff_b <= tolerance:
                self.log.emit(f"  -> Pixel match SUCCESS at ({s.pixel_x},{s.pixel_y})")
                return (True, s.pixel_success_goto_id)
            else:
                self.log.emit(f"  -> Pixel match FAIL: screen {screen_rgb} vs target {target_rgb}")
                return (False, None)
        except Exception as e:
            self.log.emit(f"!! pixel_check error: {e}")
            return (False, None)

    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _compare_images(self, s: StepData) -> tuple[bool, str | None]:
        try:
            path_a = self._resolve_path(self._process_dynamic_string(s.image_a_path or ""))
            path_b = self._resolve_path(self._process_dynamic_string(s.image_b_path or ""))
            if not path_a or not path_b:
                return (False, None)
            
            # Load images (simplified)
            # In real implementation, use cv2.imdecode with numpy for unicode support
            # For now using standard cv2.imread (might fail with unicode paths on Windows if not handled)
            # Better:
            def imread_safe(path):
                with open(path, "rb") as stream:
                    raw_bytes = bytearray(stream.read())
                numpyarray = np.asarray(raw_bytes, dtype=np.uint8)
                return cv2.imdecode(numpyarray, cv2.IMREAD_COLOR)

            img_a = imread_safe(path_a)
            img_b = imread_safe(path_b)

            if img_a is None or img_b is None:
                return (False, None)

            roi_w = int(getattr(s, "compare_roi_w", 0) or 0)
            roi_h = int(getattr(s, "compare_roi_h", 0) or 0)
            if roi_w > 0 and roi_h > 0:
                roi_x = max(0, int(getattr(s, "compare_roi_x", 0) or 0))
                roi_y = max(0, int(getattr(s, "compare_roi_y", 0) or 0))
                ax2 = min(roi_x + roi_w, img_a.shape[1])
                ay2 = min(roi_y + roi_h, img_a.shape[0])
                bx2 = min(roi_x + roi_w, img_b.shape[1])
                by2 = min(roi_y + roi_h, img_b.shape[0])
                if ax2 <= roi_x or ay2 <= roi_y or bx2 <= roi_x or by2 <= roi_y:
                    self.log.emit("!! compare_images: ROI out of bounds.")
                    return (False, None)
                img_a = img_a[roi_y:ay2, roi_x:ax2]
                img_b = img_b[roi_y:by2, roi_x:bx2]

            mode = str(getattr(s, "compare_mode", "mse") or "mse").lower()
            threshold = float(getattr(s, "compare_threshold", 0.0) or 0.0)

            def to_gray(img: np.ndarray) -> np.ndarray:
                if img.ndim == 3 and img.shape[-1] == 3:
                    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                return img

            def ssim_score(a: np.ndarray, b: np.ndarray) -> float:
                a = to_gray(a).astype(np.float64)
                b = to_gray(b).astype(np.float64)
                if a.shape != b.shape:
                    return -1.0
                mu_a = a.mean()
                mu_b = b.mean()
                var_a = ((a - mu_a) ** 2).mean()
                var_b = ((b - mu_b) ** 2).mean()
                cov_ab = ((a - mu_a) * (b - mu_b)).mean()
                c1 = (0.01 * 255) ** 2
                c2 = (0.03 * 255) ** 2
                num = (2 * mu_a * mu_b + c1) * (2 * cov_ab + c2)
                den = (mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2)
                if den == 0:
                    return -1.0
                return float(num / den)

            def dhash(img: np.ndarray) -> np.ndarray:
                gray = to_gray(img)
                resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
                diff = resized[:, 1:] > resized[:, :-1]
                return diff.flatten()

            is_match = False
            if mode == "mse":
                if img_a.shape != img_b.shape:
                    self.log.emit("!! compare_images: size mismatch for MSE.")
                    return (False, None)
                err = np.mean((img_a.astype("float") - img_b.astype("float")) ** 2)
                is_match = err <= threshold
            elif mode == "ssim":
                if img_a.shape != img_b.shape:
                    self.log.emit("!! compare_images: size mismatch for SSIM.")
                    return (False, None)
                score = ssim_score(img_a, img_b)
                is_match = score >= threshold
            elif mode == "hash":
                hash_a = dhash(img_a)
                hash_b = dhash(img_b)
                dist = int(np.count_nonzero(hash_a != hash_b))
                is_match = dist <= threshold
            else:
                self.log.emit(f"!! compare_images: unknown mode '{mode}'.")
                return (False, None)

            return (True, s.on_match_goto_id) if is_match else (False, None)
        except Exception as e:
            self.log.emit(f"!! compare error: {e}")
            return (False, None)

    def _screenshot_roi(self, sct, s: StepData) -> bool:
        save_path = getattr(s, "screenshot_save_path", None) or getattr(s, "screenshot_filepath", None)
        if not save_path:
            return False
        try:
            filepath = self._resolve_path(self._process_dynamic_string(save_path))
            dir_name = os.path.dirname(filepath)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name)
            if s.screenshot_roi_w > 0 and s.screenshot_roi_h > 0:
                region = {
                    "left": s.screenshot_roi_x,
                    "top": s.screenshot_roi_y,
                    "width": s.screenshot_roi_w,
                    "height": s.screenshot_roi_h,
                }
            else:
                try:
                    mon = sct.monitors[0]
                    region = {
                        "left": mon["left"],
                        "top": mon["top"],
                        "width": mon["width"],
                        "height": mon["height"],
                    }
                except Exception:
                    return False
            if region["width"] <= 0 or region["height"] <= 0:
                return False
            grab = sct.grab(region)
            if hasattr(grab, "rgb"):
                # Dummy grab with .rgb buffer
                buf = np.frombuffer(grab.rgb, dtype=np.uint8)
                img_bgra = buf.reshape(grab.height, grab.width, 3)
                img_bgra = cv2.cvtColor(img_bgra, cv2.COLOR_RGB2BGRA)
            else:
                img_bgra = np.array(grab)
            img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
            
            # Save with unicode support
            is_success, im_buf_arr = cv2.imencode(".png", img_bgr)
            if is_success:
                im_buf_arr.tofile(filepath)
                
            self.log.emit(f"  -> Screenshot saved: {filepath}")
            return True
        except Exception as e:
            self.log.emit(f"!! screenshot error: {e}")
            return False

    def _resolve_ocr_scale(self, img_bgr: np.ndarray, s: StepData) -> float:
        scale = float(getattr(s, "ocr_scale", 2.0) or 2.0)
        target_h = int(getattr(s, "ocr_target_height", 0) or 0)
        if target_h > 0 and img_bgr is not None:
            try:
                h = int(img_bgr.shape[0])
            except Exception:
                h = 0
            if h > 0:
                scale = float(target_h) / float(h)
        if scale <= 0:
            scale = 1.0
        return max(1.0, scale)

    def _preprocess_ocr_image(self, img_bgr: np.ndarray, mode: str, invert: bool) -> np.ndarray:
        if img_bgr is None:
            return img_bgr
        if img_bgr.ndim == 3:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_bgr.copy()

        mode = str(mode or "none").lower()
        processed = gray
        if mode in ("none", "no", "off"):
            processed = gray
        elif mode in ("blur", "gaussian"):
            processed = cv2.GaussianBlur(gray, (3, 3), 0)
            _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        elif mode in ("adaptive", "adapt"):
            processed = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            _, processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        if invert:
            processed = cv2.bitwise_not(processed)
        return processed

    def _ocr_text_with_options(self, img_bgr: np.ndarray, s: StepData) -> str:
        if img_bgr is None:
            return ""
        img = img_bgr
        scale = self._resolve_ocr_scale(img, s)
        try:
            h = int(img.shape[0])
            w = int(img.shape[1])
        except Exception:
            h = 0
            w = 0
        if h > 0 and w > 0 and scale != 1.0:
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        img = self._preprocess_ocr_image(
            img,
            getattr(s, "ocr_preprocess_mode", "none") or "none",
            bool(getattr(s, "ocr_invert", False)),
        )
        whitelist = getattr(s, "ocr_whitelist", None)
        config = None
        if whitelist:
            wl = str(whitelist).strip()
            if wl:
                config = f"-c tessedit_char_whitelist={wl}"
        try:
            configure_tesseract_cmd()
            import pytesseract
            if config:
                return pytesseract.image_to_string(img, lang=s.ocr_lang or "eng", config=config)
            return pytesseract.image_to_string(img, lang=s.ocr_lang or "eng")
        except Exception:
            return ""

    def _ocr_check_text(self, sct, mon, s: StepData) -> tuple[bool, str | None]:
        try:
            # Determine region
            if s.ocr_roi_w > 0 and s.ocr_roi_h > 0:
                region = {
                    "left": s.ocr_roi_x,
                    "top": s.ocr_roi_y,
                    "width": s.ocr_roi_w,
                    "height": s.ocr_roi_h,
                }
            else:
                region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}

            raw = sct.grab(region)
            if hasattr(raw, "rgb"):
                buf = np.frombuffer(raw.rgb, dtype=np.uint8)
                img_bgra = buf.reshape(raw.height, raw.width, 3)
                img_bgra = cv2.cvtColor(img_bgra, cv2.COLOR_RGB2BGRA)
            else:
                img_bgra = np.array(raw)
            if img_bgra.ndim == 3 and img_bgra.shape[-1] == 4:
                img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
            elif img_bgra.ndim == 3 and img_bgra.shape[-1] == 3:
                img_bgr = img_bgra
            else:
                # Fallback: create blank image if grab is unexpected
                img_bgr = np.zeros((region["height"], region["width"], 3), dtype=np.uint8)

            scale = self._resolve_ocr_scale(img_bgr, s)
            ip = ImageProcessor(
                scale_factor=scale,
                invert=bool(getattr(s, "ocr_invert", False)),
                threshold_mode=getattr(s, "ocr_preprocess_mode", "otsu") or "otsu",
            )
            val = ip.extract_number(img_bgr, psm_mode=6)
            self.log.emit(f"  -> OCR text value: {val}")

            expected = getattr(s, "ocr_expected_text", None) or ""
            if getattr(s, "ocr_use_dynamic_data", False):
                expected = self._process_dynamic_string(expected)
            expected = expected.strip()

            ok = False
            goto = None

            if expected:
                # First try numeric compare
                try:
                    exp_val = float(expected.replace("%", "").strip())
                except Exception:
                    exp_val = None
                if val is not None and exp_val is not None and abs(val - exp_val) < 1e-6:
                    ok = True
                else:
                    # Fallback: text OCR comparison (case-insensitive substring)
                    raw_text = self._ocr_text_with_options(img_bgr, s)
                    if raw_text and expected.lower() in raw_text.lower():
                        ok = True
                goto = s.on_match_goto_id if ok else None
            else:
                ok = val is not None
                goto = s.on_match_goto_id if ok else None

            try:
                region_rect = (region["left"], region["top"], region["width"], region["height"])
                col = (0, 255, 0) if ok else (255, 0, 0)
                self.debugEvent.emit({"rect": region_rect, "text": f"OCR: {val}", "color": col})
            except Exception as e:
                self.logger.debug("debugEvent emit failed for OCR compare: %s", e)

            # Store in context if var_name provided
            var_name = getattr(s, "ocr_store_var", None)
            if var_name:
                self.variable_context[var_name] = val

            return (ok, goto)
        except Exception as e:
            self.log.emit(f"  !! OCR error: {e}")
            return (False, None)

    def _ocr_jump_if(self, sct, mon, s: StepData) -> tuple[bool, str | None, int]:
        if sct is None or mon is None:
            self.log.emit("  !! OCR jump: no screen capture available.")
            return (True, None, 0)
        try:
            if s.ocr_roi_w > 0 and s.ocr_roi_h > 0:
                region = {
                    "left": s.ocr_roi_x,
                    "top": s.ocr_roi_y,
                    "width": s.ocr_roi_w,
                    "height": s.ocr_roi_h,
                }
            else:
                region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}

            raw = sct.grab(region)
            if hasattr(raw, "rgb"):
                buf = np.frombuffer(raw.rgb, dtype=np.uint8)
                img_bgra = buf.reshape(raw.height, raw.width, 3)
                img_bgra = cv2.cvtColor(img_bgra, cv2.COLOR_RGB2BGRA)
            else:
                img_bgra = np.array(raw)
            if img_bgra.ndim == 3 and img_bgra.shape[-1] == 4:
                img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
            elif img_bgra.ndim == 3 and img_bgra.shape[-1] == 3:
                img_bgr = img_bgra
            else:
                img_bgr = np.zeros((region["height"], region["width"], 3), dtype=np.uint8)

            scale = self._resolve_ocr_scale(img_bgr, s)
            ip = ImageProcessor(
                scale_factor=scale,
                invert=bool(getattr(s, "ocr_invert", False)),
                threshold_mode=getattr(s, "ocr_preprocess_mode", "otsu") or "otsu",
            )
            val = ip.extract_number(img_bgr, psm_mode=6)
            compare_to = getattr(s, "condition_value", None)
            use_text = False
            if compare_to not in (None, ""):
                try:
                    float(str(compare_to).replace("%", "").strip())
                except Exception:
                    use_text = True

            actual_value = val
            if use_text:
                raw_text = self._ocr_text_with_options(img_bgr, s)
                actual_value = raw_text.strip() if raw_text else ""

            if actual_value in (None, ""):
                self.log.emit("  !! OCR jump: value not found.")
                return (True, None, 0)

            op = getattr(s, "condition_operator", None) or getattr(s, "condition_op", None) or getattr(s, "operator", None) or "=="
            target = getattr(s, "condition_value", None)
            is_true, _ = self.evaluator.evaluate(s, self.variable_context, actual_value=actual_value)

            try:
                region_rect = (region["left"], region["top"], region["width"], region["height"])
                col = (0, 255, 0) if is_true else (255, 0, 0)
                self.debugEvent.emit({"rect": region_rect, "text": f"OCR: {actual_value}", "color": col})
            except Exception as e:
                self.logger.debug("debugEvent emit failed for OCR jump_if: %s", e)

            if is_true:
                jump_id = getattr(s, "target_true_id", None) or getattr(s, "jump_to_step_id", None)
                jump_idx = getattr(s, "target_true_index", None) if hasattr(s, "target_true_index") else getattr(s, "jump_to_index", None)
                goto_id = None

                if jump_id:
                    for idx, st in enumerate(self.steps):
                        if getattr(st, "id", None) == jump_id:
                            goto_id = st.id
                            self.log.emit(f"  -> OCR TRUE ({actual_value} {op} {target}); jump to ID {jump_id} (index {idx}).")
                            break

                if goto_id is None and jump_idx is not None:
                    try:
                        jump_idx = int(jump_idx)
                        if 0 <= jump_idx < len(self.steps):
                            goto_id = self.steps[jump_idx].id
                            self.log.emit(f"  -> OCR TRUE ({actual_value} {op} {target}); falling back to index {jump_idx}.")
                    except Exception:
                        goto_id = None

                if goto_id is None:
                    self.log.emit(f"  !! ocr_jump_if: condition true but target not found (id={jump_id}, idx={jump_idx}).")
                    return (True, None, 0)

                return (True, goto_id, 0)

            self.log.emit(f"  -> OCR FALSE ({actual_value} {op} {target}); continue.")
            return (True, None, 0)
        except Exception as e:
            self.log.emit(f"  !! OCR jump error: {e}")
            return (False, None, 0)

    def _ocr_store(self, sct, mon, s: StepData) -> bool:
        """OCR, store value into variable_context by var name."""
        var_name = getattr(s, "ocr_store_var", None) or getattr(s, "var_name", None)
        if not var_name:
            self.log.emit("  !! OCR store: var_name not set.")
            return False
        # Reuse _ocr_check_text but always store regardless of expected match
        ok, _ = self._ocr_check_text(sct, mon, s)
        val = self.variable_context.get(var_name, None)
        # If _ocr_check_text didn't store, attempt direct extraction
        if val is None:
            try:
                if s.ocr_roi_w > 0 and s.ocr_roi_h > 0:
                    region = {
                        "left": s.ocr_roi_x,
                        "top": s.ocr_roi_y,
                        "width": s.ocr_roi_w,
                        "height": s.ocr_roi_h,
                    }
                else:
                    region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
                raw = sct.grab(region)
                img_bgra = np.array(raw)
                if img_bgra.shape[-1] == 4:
                    img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
                else:
                    img_bgr = img_bgra
                scale = self._resolve_ocr_scale(img_bgr, s)
                ip = ImageProcessor(
                    scale_factor=scale,
                    invert=bool(getattr(s, "ocr_invert", False)),
                    threshold_mode=getattr(s, "ocr_preprocess_mode", "otsu") or "otsu",
                )
                val = ip.extract_number(img_bgr, psm_mode=6)
                self.variable_context[var_name] = val
            except Exception as e:
                self.log.emit(f"  !! OCR store error: {e}")
                return False
        self.log.emit(f"  -> OCR stored [{var_name}]: {val}")
        return val is not None

    def _handle_run_macro(self, s: StepData) -> bool:
        """Handle run_macro step with call stack and recursion guard."""
        target_path = self._resolve_path(getattr(s, "target_macro_path", "") or "")
        if not target_path:
            self.log.emit("  !! run_macro: target path not set.")
            return False

        if len(self.call_stack) >= self._max_call_depth:
            self.log.emit("  !! run_macro: max call depth exceeded.")
            return False

        path_obj = Path(target_path).expanduser()
        if not path_obj.exists():
            self.log.emit(f"  !! run_macro: file not found: {path_obj}")
            return False

        new_steps = self._load_macro_file(path_obj)
        if not new_steps:
            self.log.emit(f"  !! run_macro: failed to load {path_obj}")
            return False

        # Push current state
        self.call_stack.append(
            {
                "steps": self.steps,
                "index": self.current_step_index,
                "path": self.current_file_path,
            }
        )

        # Switch to sub-script
        self._switch_steps = new_steps
        self._switch_path = str(path_obj)
        self.log.emit(f"  -> Enter sub-script: {path_obj}")
        return True

    def _run_sub_macro(self, s: StepData) -> bool:
        path = self._resolve_path(getattr(s, "target_macro_path", None) or "")
        if not path:
            self.log.emit("  !! run_macro: target path not set.")
            return False
        if len(self.call_stack) >= self._max_call_depth:
            self.log.emit("  !! run_macro: max depth exceeded.")
            return False
        try:
            new_steps = self._load_macro_file(path)
            if not new_steps:
                self.log.emit(f"  !! run_macro: failed to load {path}")
                return False
            # Push current state
            self.call_stack.append({
                "steps": self.steps,
                "index": self.current_step_index,
                "path": self.current_file_path,
            })
            self._switch_steps = new_steps
            self._switch_path = path
            self.log.emit(f"  -> Enter sub-script: {path}")
            return True
        except Exception as e:
            self.log.emit(f"  !! run_macro error: {e}")
            self._logger.exception("run_macro error", exc_info=e)
            return False

    def _jump_if(self, s: StepData) -> tuple[bool, str | None, int]:
        var_name = getattr(s, "condition_var", None) or getattr(s, "condition_var_name", None)
        op = getattr(s, "condition_operator", None) or getattr(s, "operator", None) or getattr(s, "condition_op", None) or "=="
        target = getattr(s, "condition_value", None)

        if not var_name:
            self.log.emit("  !! jump_if: condition_var not set.")
            return (True, None, 0)

        if var_name not in self.variable_context:
            self.log.emit(f"  !! jump_if: variable '{var_name}' not found. Continue.")
            return (True, None, 0)

        current_val = self.variable_context.get(var_name)
        try:
            is_true, _ = self.evaluator.evaluate(s, self.variable_context, actual_value=current_val)
        except Exception:
            self.logger.exception("jump_if evaluation failed; treating as FALSE.")
            is_true = False

        if is_true:
            jump_id = getattr(s, "target_true_id", None) or getattr(s, "jump_to_step_id", None)
            jump_idx = getattr(s, "target_true_index", None) if hasattr(s, "target_true_index") else getattr(s, "jump_to_index", None)
            goto_id = None

            # 1) ID 우선: 현재 step 리스트에서 일치 ID 찾기
            if jump_id:
                for idx, st in enumerate(self.steps):
                    if getattr(st, "id", None) == jump_id:
                        goto_id = st.id
                        self.log.emit(f"  -> Condition TRUE ({var_name} {op} {target}); jump to ID {jump_id} (index {idx}).")
                        break

            # 2) Fallback: ID 없거나 못 찾으면 인덱스로 시도
            if goto_id is None and jump_idx is not None:
                try:
                    jump_idx = int(jump_idx)
                    if 0 <= jump_idx < len(self.steps):
                        goto_id = self.steps[jump_idx].id
                        self.log.emit(f"  -> Condition TRUE ({var_name} {op} {target}); falling back to index {jump_idx}.")
                except Exception:
                    goto_id = None

            # 3) 실패 시 경고 후 계속
            if goto_id is None:
                self.log.emit(f"  !! jump_if: condition true but target not found (id={jump_id}, idx={jump_idx}).")
                return (True, None, 0)

            return (True, goto_id, 0)

        self.log.emit(f"  -> Condition FALSE ({var_name} {op} {target}); continue.")
        return (True, None, 0)

    def _collect_required_data_columns(self) -> set[str]:
        """
        Collect data-column placeholder tokens used in runtime string fields.
        Tokens like {data}/{seq} are runtime built-ins and excluded.
        """
        required: set[str] = set()
        builtins = {"data", "seq"}
        pattern = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")
        target_fields = ("key_string", "ocr_expected_text")

        for step in self.steps:
            for field_name in target_fields:
                raw = getattr(step, field_name, None)
                if not isinstance(raw, str) or "{" not in raw:
                    continue
                for m in pattern.finditer(raw):
                    token = m.group(1) or m.group(2)
                    if token in builtins:
                        continue
                    required.add(token)
        return required

    def _load_data_file(self, s: StepData) -> bool:
        path = self._resolve_path(self._process_dynamic_string(s.data_file_path or ""))
        if not path: return False

        success, data, error = load_data_rows(path)

        if not success:
            self.log.emit(f"!! load_data error: {error}")
            return False

        if not data:
            self.log.emit("!! load_data error: usable rows are empty.")
            return False

        self._data_rows = data
        self._data_columns = list(data[0].keys())
        self._primary_data_column = self._data_columns[0] if self._data_columns else None
        self._data_row_values = [[str(row.get(col, "")) for col in self._data_columns] for row in data]
        self._data_list = [str(row.get(self._primary_data_column or "", "")) for row in data]

        required = self._collect_required_data_columns()
        missing = sorted(col for col in required if col not in set(self._data_columns))
        if missing:
            self.log.emit(
                "!! load_data error: missing columns in data file -> "
                + ", ".join(missing)
            )
            return False

        self._data_index = 0
        self.log.emit(
            f"  -> Loaded data file: {len(data)} rows, columns={self._data_columns}."
        )
        return True

    def _load_macro_file(self, path: str | Path) -> list[StepData] | None:
        try:
            path_obj = Path(path)
            if path_obj.suffix.lower() == ".macro":
                steps, _ = MacroIO.load_macro(str(path_obj))
                return steps
            # assume json with {"steps": [dicts]} or direct list
            import json
            with path_obj.open("r", encoding="utf-8") as f:
                data = json.load(f)
            steps_data = data.get("steps", data if isinstance(data, list) else [])
            new_steps = []
            for d in steps_data:
                try:
                    new_steps.append(StepData(**d))
                except Exception:
                    continue
            return new_steps
        except Exception as e:
            self.log.emit(f"!! load_macro_file error: {e}")
            self._logger.exception("load_macro_file error", exc_info=e)
            return None

    def _resolve_path(self, path: str) -> str:
        text = (path or "").strip()
        if not text:
            return ""
        expanded = os.path.expanduser(os.path.expandvars(text))
        try:
            path_obj = Path(expanded)
        except Exception:
            return expanded
        if path_obj.is_absolute():
            return str(path_obj)
        base = None
        if self.current_file_path:
            try:
                base = Path(self.current_file_path).parent
            except Exception:
                base = None
        if base:
            return str(base / path_obj)
        return str(path_obj)

    def _end_loop(self, s: StepData) -> tuple[bool, str | None]:
        start_id = s.start_loop_id
        if not start_id or start_id not in self._loop_counters:
            return (False, None)
            
        count = self._loop_counters[start_id]
        
        if self._data_list is not None:
            self._data_index += 1
            if self._data_index < len(self._data_list):
                return (True, start_id)
            return (True, None)
            
        if count == 0: # infinite
            return (True, start_id)
            
        if count > 1:
            self._loop_counters[start_id] -= 1
            return (True, start_id)
            
        del self._loop_counters[start_id]
        return (True, None)

    def _process_dynamic_string(self, text: str) -> str:
        # Replace {counter} or {data}
        # Simplified implementation
        def replace_counter(match):
            name = match.group(1)
            if name not in self._counters:
                self._counters[name] = 1
            val = self._counters[name]
            self._counters[name] += 1
            return str(val)
            
        text = re.sub(r"\{counter:(\w+)\}", replace_counter, text)

        # Sequential number: {seq} or {seq:name}
        def replace_seq(match):
            name = match.group(1) or "default"
            key = f"seq_{name}"
            if key not in self._counters:
                self._counters[key] = 1
            val = self._counters[key]
            self._counters[key] += 1
            return str(val)
        text = re.sub(r"\{seq(?::(\w+))?\}", replace_seq, text)

        # Random single-char tokens: # (A-Z), @ (a-z), ? (0-9)
        def replace_random(match):
            t = match.group(0)
            if t == "#":
                return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            if t == "@":
                return random.choice("abcdefghijklmnopqrstuvwxyz")
            if t == "?":
                return random.choice("0123456789")
            return t
        text = re.sub(r"[#@?]", replace_random, text)

        mapping: dict[str, object] = dict(self.variable_context or {})
        if self._data_list and 0 <= self._data_index < len(self._data_list):
            mapping["data"] = str(self._data_list[self._data_index])
            row_vals = self._get_current_row_values()
            if row_vals:
                for idx, col in enumerate(self._data_columns):
                    if idx < len(row_vals):
                        mapping[str(col)] = row_vals[idx]

        return TemplateProcessor.render(text, mapping)

    def _get_current_row_values(self) -> list[str] | None:
        if self._data_row_values is not None and 0 <= self._data_index < len(self._data_row_values):
            return self._data_row_values[self._data_index]
        return None

    def _compare_condition(self, current, target, op: str) -> bool:
        """Compare two values with the given operator, attempting numeric compare first."""
        def to_num(val):
            if isinstance(val, (int, float)):
                return float(val)
            try:
                return float(str(val).replace("%", "").strip())
            except Exception:
                return None

        a_num = to_num(current)
        b_num = to_num(target)
        if a_num is not None and b_num is not None:
            a, b = a_num, b_num
        else:
            a, b = str(current), str(target)

        if op == ">":
            return a > b
        if op == "<":
            return a < b
        if op == ">=":
            return a >= b
        if op == "<=":
            return a <= b
        if op == "!=":
            return a != b
        # Default equality check
        return a == b

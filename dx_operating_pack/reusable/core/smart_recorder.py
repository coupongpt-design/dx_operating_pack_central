from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import time
import uuid

import cv2
import numpy as np

from .models import StepData


_TEXT_FLUSH_KEYS = {
    "backspace",
    "delete",
    "left",
    "right",
    "up",
    "down",
    "home",
    "end",
    "tab",
    "enter",
}
_MODIFIER_KEYS = {"ctrl", "alt", "win"}
_IGNORED_KEYS = {"shift"}


@dataclass
class SmartStep:
    step_type: str
    text: str | None = None
    key: str | None = None
    timestamp: float = 0.0
    reason: str = ""

    def to_step_data(self) -> StepData:
        sid = str(uuid.uuid4())[:8]
        if self.step_type == "type_text":
            return StepData(
                id=sid,
                name=f"Type '{self.text or ''}'",
                type="key",
                keyboard_mode="text",
                key_string=self.text or "",
            )
        if self.step_type == "key_press":
            return StepData(
                id=sid,
                name=f"Key {self.key or ''}",
                type="key",
                keyboard_mode="key",
                key_string=self.key or "",
            )
        if self.step_type == "click_point":
            return StepData(
                id=sid,
                name=f"Click ({self.key or ''})",
                type="click_point",
            )
        raise ValueError(f"Unsupported step_type: {self.step_type}")


@dataclass
class SmartProposal:
    event_timestamp: float
    x: int
    y: int
    click_step: StepData
    image_step: StepData | None
    image_path: str | None


class SmartTransformer:
    def __init__(
        self,
        *,
        typed_gap: float = 1.5,
        click_capture_size: int = 60,
        image_dir: str | Path = "images",
        capture_provider: Callable[[int, int, int, int], np.ndarray | None] | None = None,
    ):
        self.typed_gap = max(0.1, float(typed_gap))
        self.click_capture_size = max(10, int(click_capture_size))
        self.image_dir = Path(image_dir)
        self.capture_provider = capture_provider

        self._text_buffer: list[str] = []
        self._last_text_ts: float | None = None

    def reset(self):
        self._text_buffer.clear()
        self._last_text_ts = None

    def process_event(self, raw_event: dict) -> list[SmartStep | SmartProposal]:
        outputs: list[SmartStep | SmartProposal] = []
        etype = str(raw_event.get("type") or "").lower()
        phase = str(raw_event.get("phase") or "press").lower()
        ts = float(raw_event.get("timestamp") or time.time())

        outputs.extend(self._flush_text_if_timeout(ts))

        if etype == "key" and phase == "press":
            outputs.extend(self._process_key_event(raw_event, ts))
            return outputs

        if etype == "click" and phase == "release":
            outputs.append(self._build_click_proposal(raw_event, ts))
            return outputs

        return outputs

    def finalize(self) -> list[SmartStep]:
        return self._flush_text(force=True, reason="finalize")

    def _process_key_event(self, event: dict, ts: float) -> list[SmartStep]:
        out: list[SmartStep] = []
        key_code = (event.get("key_code") or "").strip()
        token = key_code.lower()
        modifiers = {str(m).lower() for m in (event.get("modifiers") or [])}

        if not token:
            return out
        if token in _IGNORED_KEYS:
            return out

        if token in _MODIFIER_KEYS or (modifiers & _MODIFIER_KEYS):
            out.extend(self._flush_text(force=True, reason="modifier"))
            out.append(SmartStep(step_type="key_press", key=token, timestamp=ts, reason="modifier"))
            return out

        if token in _TEXT_FLUSH_KEYS:
            out.extend(self._flush_text(force=True, reason="flush_key"))
            out.append(SmartStep(step_type="key_press", key=token, timestamp=ts, reason="flush_key"))
            return out

        if self._is_printable_token(key_code):
            self._text_buffer.append(key_code)
            self._last_text_ts = ts
            return out

        out.extend(self._flush_text(force=True, reason="non_printable"))
        out.append(SmartStep(step_type="key_press", key=token, timestamp=ts, reason="non_printable"))
        return out

    def _is_printable_token(self, value: str) -> bool:
        return len(value) == 1 and value.isprintable()

    def _flush_text_if_timeout(self, current_ts: float) -> list[SmartStep]:
        if not self._text_buffer or self._last_text_ts is None:
            return []
        if (current_ts - self._last_text_ts) > self.typed_gap:
            return self._flush_text(force=True, reason="typed_gap")
        return []

    def _flush_text(self, *, force: bool, reason: str) -> list[SmartStep]:
        if not force or not self._text_buffer:
            return []
        text = "".join(self._text_buffer)
        self._text_buffer.clear()
        self._last_text_ts = None
        return [
            SmartStep(
                step_type="type_text",
                text=text,
                timestamp=time.time(),
                reason=reason,
            )
        ]

    def _build_click_proposal(self, event: dict, ts: float) -> SmartProposal:
        x = int(event.get("x") or 0)
        y = int(event.get("y") or 0)
        click_step = StepData(
            id=str(uuid.uuid4())[:8],
            name=f"Click ({x},{y})",
            type="click_point",
            click_x=x,
            click_y=y,
            click_btn=(event.get("button") or "left"),
        )

        image_step = None
        image_path = None
        captured = self._capture_near_click(x, y)
        if captured is not None and captured.size > 0:
            self.image_dir.mkdir(parents=True, exist_ok=True)
            image_path = str(self.image_dir / f"record_prop_{int(ts * 1000)}_{uuid.uuid4().hex[:6]}.png")
            cv2.imwrite(image_path, captured)
            png_bytes = None
            try:
                ok, enc = cv2.imencode(".png", captured)
                if ok:
                    png_bytes = enc.tobytes()
            except Exception:
                png_bytes = None
            image_step = StepData(
                id=str(uuid.uuid4())[:8],
                name=f"Image Click ({x},{y})",
                type="image_click",
                anchor_image_path=image_path,
                image_path=image_path,
                png_bytes=png_bytes,
                click_x=x,
                click_y=y,
                click_btn=(event.get("button") or "left"),
            )

        return SmartProposal(
            event_timestamp=ts,
            x=x,
            y=y,
            click_step=click_step,
            image_step=image_step,
            image_path=image_path,
        )

    def _capture_near_click(self, x: int, y: int) -> np.ndarray | None:
        if not self.capture_provider:
            return None
        half = self.click_capture_size // 2
        left = x - half
        top = y - half
        width = self.click_capture_size
        height = self.click_capture_size
        try:
            img = self.capture_provider(left, top, width, height)
            if img is None:
                return None
            if not isinstance(img, np.ndarray):
                return None
            return img
        except Exception:
            return None

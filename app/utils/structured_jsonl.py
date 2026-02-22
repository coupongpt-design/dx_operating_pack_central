from __future__ import annotations

import datetime as _dt
import json
import threading
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class StructuredJsonlLogger:
    def __init__(
        self,
        *,
        run_id: str,
        log_dir: str | Path = "logs",
        prefix: str = "run_events",
        enabled: bool = True,
    ) -> None:
        self.run_id = str(run_id or "").strip()
        self.log_dir = Path(log_dir)
        self.prefix = str(prefix or "run_events").strip() or "run_events"
        self.enabled = bool(enabled)
        self.path: Path | None = None
        self._handle = None
        self._lock = threading.Lock()

    def open(self) -> Path | None:
        if not self.enabled:
            return None
        with self._lock:
            if self._handle is not None:
                return self.path

            self.log_dir.mkdir(parents=True, exist_ok=True)
            if self.path is None:
                ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                rid = self.run_id or "run_unknown"
                self.path = self.log_dir / f"{self.prefix}_{ts}_{rid}.jsonl"

            self._handle = self.path.open("a", encoding="utf-8")
            return self.path

    def write(
        self,
        *,
        level: str,
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        row = {
            "timestamp": _utc_now_iso(),
            "run_id": self.run_id,
            "level": str(level or "INFO").upper(),
            "event": str(event or "").strip(),
        }
        if payload:
            for key, value in payload.items():
                if value is None:
                    continue
                row[str(key)] = value

        with self._lock:
            handle = self._handle
            if handle is None:
                opened = self.open()
                if opened is None:
                    return
                handle = self._handle
            if handle is None:
                return
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()

    def close(self) -> None:
        with self._lock:
            if self._handle is None:
                return
            try:
                self._handle.flush()
            except Exception:
                pass
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None

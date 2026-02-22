from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import os


@dataclass
class RunSummary:
    run_id: str
    file_path: str
    started_at: str
    finished_at: str
    status: str
    duration_ms: int | None
    total_steps: int
    failed_steps: int
    slowest_step_name: str
    slowest_duration_ms: int | None
    sort_key: float


def _parse_iso_ts(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def load_run_events(path: str | Path) -> list[dict[str, Any]]:
    src = Path(path)
    rows: list[dict[str, Any]] = []
    if not src.exists():
        return rows
    for raw in src.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


def summarize_run_events(events: list[dict[str, Any]], file_path: str | Path = "") -> RunSummary | None:
    if not events:
        return None

    run_id = ""
    started_at = ""
    finished_at = ""
    status = "running"
    duration_ms: int | None = None
    total_steps = 0
    failed_steps = 0
    slowest_step_name = "-"
    slowest_duration_ms: int | None = None

    start_ts: float | None = None
    finish_ts: float | None = None

    for row in events:
        row_run_id = str(row.get("run_id") or "").strip()
        if row_run_id and not run_id:
            run_id = row_run_id

        event = str(row.get("event") or "").strip()
        ts_text = str(row.get("timestamp") or "").strip()
        ts_value = _parse_iso_ts(ts_text)

        if event in ("run_started", "run_resumed"):
            if not started_at and ts_text:
                started_at = ts_text
            if start_ts is None and ts_value is not None:
                start_ts = ts_value

        if event == "run_finished":
            if ts_text:
                finished_at = ts_text
            if ts_value is not None:
                finish_ts = ts_value
            ok = row.get("success")
            status = "success" if bool(ok) else "failed"
            run_duration = _to_int(row.get("duration_ms"))
            if run_duration is not None and run_duration >= 0:
                duration_ms = run_duration

        if event == "step_started":
            total_steps += 1
        elif event == "step_failed":
            failed_steps += 1

        if event in ("step_succeeded", "step_failed"):
            step_duration = _to_int(row.get("duration_ms"))
            if step_duration is not None and step_duration >= 0:
                if slowest_duration_ms is None or step_duration > slowest_duration_ms:
                    slowest_duration_ms = step_duration
                    step_name = str(row.get("step_name") or "").strip()
                    slowest_step_name = step_name or str(row.get("step_uuid") or "-")

    if duration_ms is None and start_ts is not None and finish_ts is not None and finish_ts >= start_ts:
        duration_ms = int((finish_ts - start_ts) * 1000)

    if not run_id:
        stem = Path(file_path).stem if file_path else ""
        run_id = stem or "-"

    if not started_at and events:
        started_at = str(events[0].get("timestamp") or "")
        start_ts = _parse_iso_ts(started_at)

    if not finished_at and events:
        finished_at = str(events[-1].get("timestamp") or "")
        if finish_ts is None:
            finish_ts = _parse_iso_ts(finished_at)

    if status == "running" and finished_at:
        status = "incomplete"

    if start_ts is None:
        try:
            start_ts = os.path.getmtime(str(file_path)) if file_path else 0.0
        except Exception:
            start_ts = 0.0

    return RunSummary(
        run_id=run_id,
        file_path=str(file_path or ""),
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        duration_ms=duration_ms,
        total_steps=total_steps,
        failed_steps=failed_steps,
        slowest_step_name=slowest_step_name,
        slowest_duration_ms=slowest_duration_ms,
        sort_key=float(start_ts or 0.0),
    )


def list_run_summaries(log_dir: str | Path = "logs", limit: int = 300) -> list[RunSummary]:
    root = Path(log_dir)
    if not root.exists():
        return []
    files = sorted(root.glob("run_events_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[RunSummary] = []
    max_items = max(1, int(limit))
    for path in files:
        summary = summarize_run_events(load_run_events(path), file_path=path)
        if summary is None:
            continue
        out.append(summary)
        if len(out) >= max_items:
            break
    out.sort(key=lambda row: row.sort_key, reverse=True)
    return out

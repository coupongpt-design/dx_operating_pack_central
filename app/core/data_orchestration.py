from __future__ import annotations

import heapq
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Iterable, Optional


@dataclass
class OrchestrationJob:
    job_id: str
    row_index: int
    payload: dict[str, Any]
    max_retry: int
    attempt: int = 0
    next_retry_at: float = 0.0
    last_error: str = ""
    last_consumer_id: str = ""


class ResultAggregator:
    def __init__(
        self,
        total_jobs: int,
        result_sink: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        self._lock = threading.Lock()
        self._total_jobs = int(total_jobs)
        self._succeeded = 0
        self._failed = 0
        self._retried = 0
        self._rows: Dict[str, dict[str, Any]] = {}
        self._result_sink = result_sink

    def _emit(self, event: str, **payload):
        if self._result_sink is None:
            return
        try:
            data = {"event": event}
            data.update(payload)
            self._result_sink(data)
        except Exception:
            # sink failures must never break orchestration flow
            return

    def on_dispatched(self, job: OrchestrationJob, consumer_id: str):
        with self._lock:
            row = self._rows.get(job.job_id)
            if row is None:
                row = {
                    "job_id": job.job_id,
                    "row_index": int(job.row_index),
                    "status": "running",
                    "attempts": 0,
                    "error_reason": "",
                    "last_consumer_id": str(consumer_id or ""),
                }
                self._rows[job.job_id] = row
            row["status"] = "running"
            row["attempts"] = int(row.get("attempts", 0)) + 1
            row["last_consumer_id"] = str(consumer_id or "")
        self._emit("job_dispatched", job_id=job.job_id, row_index=job.row_index, consumer_id=consumer_id)

    def on_retry(self, job: OrchestrationJob, error_reason: str, next_retry_at: float):
        with self._lock:
            self._retried += 1
            row = self._rows[job.job_id]
            row["status"] = "retry_scheduled"
            row["error_reason"] = str(error_reason or "")
            row["last_consumer_id"] = str(job.last_consumer_id or "")
        self._emit(
            "job_retry_scheduled",
            job_id=job.job_id,
            row_index=job.row_index,
            next_retry_at=float(next_retry_at),
            error_reason=str(error_reason or ""),
            consumer_id=str(job.last_consumer_id or ""),
        )

    def on_success(self, job: OrchestrationJob):
        with self._lock:
            self._succeeded += 1
            row = self._rows[job.job_id]
            row["status"] = "success"
            row["error_reason"] = ""
            row["last_consumer_id"] = str(job.last_consumer_id or "")
        self._emit("job_succeeded", job_id=job.job_id, row_index=job.row_index, consumer_id=job.last_consumer_id)

    def on_failed(self, job: OrchestrationJob, error_reason: str):
        with self._lock:
            self._failed += 1
            row = self._rows[job.job_id]
            row["status"] = "failed"
            row["error_reason"] = str(error_reason or "")
            row["last_consumer_id"] = str(job.last_consumer_id or "")
        self._emit(
            "job_failed",
            job_id=job.job_id,
            row_index=job.row_index,
            error_reason=str(error_reason or ""),
            consumer_id=job.last_consumer_id,
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = sorted(self._rows.values(), key=lambda r: int(r["row_index"]))
            return {
                "total_jobs": self._total_jobs,
                "succeeded": self._succeeded,
                "failed": self._failed,
                "retried": self._retried,
                "rows": [dict(r) for r in rows],
            }


class JobQueueManager:
    def __init__(
        self,
        rows: Iterable[dict[str, Any]],
        *,
        max_retry: int = 2,
        retry_delay_sec: float = 0.2,
        result_sink: Optional[Callable[[dict[str, Any]], None]] = None,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self._lock = threading.Lock()
        self._time_fn = time_fn
        self._base_retry_delay_sec = max(0.001, float(retry_delay_sec))
        self._max_retry = max(0, int(max_retry))
        self._ready: Deque[OrchestrationJob] = deque()
        self._delayed: list[tuple[float, int, OrchestrationJob]] = []
        self._inflight: Dict[str, OrchestrationJob] = {}
        self._push_seq = 0
        self._aggregator = ResultAggregator(total_jobs=0, result_sink=result_sink)

        prepared: list[OrchestrationJob] = []
        for idx, row in enumerate(rows):
            payload = dict(row or {})
            job_id = str(payload.get("job_id") or f"row-{idx}")
            prepared.append(
                OrchestrationJob(
                    job_id=job_id,
                    row_index=idx,
                    payload=payload,
                    max_retry=self._max_retry,
                )
            )
        self._ready.extend(prepared)
        self._aggregator = ResultAggregator(total_jobs=len(prepared), result_sink=result_sink)

    @property
    def aggregator(self) -> ResultAggregator:
        return self._aggregator

    def _schedule_retry_locked(self, job: OrchestrationJob, now: float):
        delay = self._base_retry_delay_sec * (2 ** max(0, job.attempt - 1))
        delay = min(delay, 5.0)
        job.next_retry_at = now + delay
        heapq.heappush(self._delayed, (job.next_retry_at, self._push_seq, job))
        self._push_seq += 1

    def _promote_delayed_locked(self, now: float):
        while self._delayed and self._delayed[0][0] <= now:
            _, _, job = heapq.heappop(self._delayed)
            self._ready.append(job)

    def request_job(self, consumer_id: str = "") -> OrchestrationJob | None:
        cid = str(consumer_id or "")
        with self._lock:
            now = self._time_fn()
            self._promote_delayed_locked(now)
            if not self._ready:
                return None
            job = self._ready.popleft()
            job.last_consumer_id = cid
            self._inflight[job.job_id] = job
        self._aggregator.on_dispatched(job, consumer_id=cid)
        return job

    def ack_success(self, job_id: str, consumer_id: str = "") -> bool:
        jid = str(job_id or "")
        if not jid:
            return False
        cid = str(consumer_id or "")
        with self._lock:
            current = self._inflight.pop(jid, None)
        if current is None:
            return False
        if cid:
            current.last_consumer_id = cid
        self._aggregator.on_success(current)
        return True

    def acknowledge_success(self, job: OrchestrationJob):
        if job is None:
            return
        self.ack_success(job.job_id, consumer_id=str(getattr(job, "last_consumer_id", "") or ""))

    def ack_fail(self, job_id: str, error_reason: str, consumer_id: str = "") -> bool:
        jid = str(job_id or "")
        if not jid:
            return False
        cid = str(consumer_id or "")
        should_retry = False
        now = self._time_fn()
        with self._lock:
            current = self._inflight.pop(jid, None)
            if current is None:
                return False
            if cid:
                current.last_consumer_id = cid
            current.last_error = str(error_reason or "")
            current.attempt += 1
            if current.attempt <= current.max_retry:
                self._schedule_retry_locked(current, now=now)
                should_retry = True

        if should_retry:
            self._aggregator.on_retry(current, error_reason=current.last_error, next_retry_at=current.next_retry_at)
            return True

        self._aggregator.on_failed(current, error_reason=current.last_error)
        return False

    def acknowledge_failure(self, job: OrchestrationJob, error_reason: str) -> bool:
        if job is None:
            return False
        return self.ack_fail(
            job.job_id,
            error_reason=error_reason,
            consumer_id=str(getattr(job, "last_consumer_id", "") or ""),
        )

    def get_recommended_sleep_sec(
        self,
        *,
        default_sleep_sec: float = 0.02,
        max_sleep_sec: float = 0.5,
        default_backoff: float | None = None,
    ) -> float:
        if default_backoff is not None:
            default_sleep_sec = float(default_backoff)
        low = max(0.001, float(default_sleep_sec))
        high = max(low, float(max_sleep_sec))
        with self._lock:
            now = self._time_fn()
            self._promote_delayed_locked(now)
            if self._ready:
                return 0.0
            if self._delayed:
                wait = max(0.0, self._delayed[0][0] - now)
                return min(high, max(low, wait))
            if self._inflight:
                return low
            return 0.0

    def is_fully_done(self) -> bool:
        with self._lock:
            now = self._time_fn()
            self._promote_delayed_locked(now)
            return not self._ready and not self._delayed and not self._inflight

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = self._time_fn()
            self._promote_delayed_locked(now)
            ready = len(self._ready)
            delayed = len(self._delayed)
            inflight = len(self._inflight)
        agg = self._aggregator.snapshot()
        agg["ready"] = ready
        agg["delayed"] = delayed
        agg["inflight"] = inflight
        return agg

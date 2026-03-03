from __future__ import annotations

import threading
from typing import Any, Protocol

from .data_orchestration import JobQueueManager, OrchestrationJob


class RunnerLike(Protocol):
    def execute_job(self, payload: dict[str, Any]) -> Any:
        ...


class SessionJobAdapter:
    def __init__(
        self,
        orchestrator: JobQueueManager,
        runner: RunnerLike,
        consumer_id: str,
        *,
        stop_event: threading.Event | None = None,
    ):
        self._orchestrator = orchestrator
        self._runner = runner
        self._consumer_id = str(consumer_id or "")
        self._stop_event = stop_event or threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str = ""

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    @property
    def last_error(self) -> str:
        return self._last_error

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._worker_loop,
            name=f"SessionJobAdapter-{self._consumer_id or 'consumer'}",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def join(self, timeout: float | None = None):
        t = self._thread
        if t is not None:
            t.join(timeout)

    def is_alive(self) -> bool:
        t = self._thread
        return bool(t and t.is_alive())

    def _safe_ack_fail(self, job: OrchestrationJob, reason: str):
        try:
            self._orchestrator.ack_fail(
                job.job_id,
                error_reason=str(reason or "worker_error"),
                consumer_id=self._consumer_id,
            )
        except Exception:
            return

    def _worker_loop(self):
        current_job: OrchestrationJob | None = None
        try:
            while not self._stop_event.is_set():
                job = self._orchestrator.request_job(consumer_id=self._consumer_id)
                if job is None:
                    if self._orchestrator.is_fully_done():
                        break
                    sleep_sec = self._orchestrator.get_recommended_sleep_sec(default_backoff=1.0)
                    self._stop_event.wait(timeout=max(0.001, float(sleep_sec)))
                    continue

                current_job = job
                try:
                    self._runner.execute_job(job.payload)
                except TimeoutError as e:
                    self._orchestrator.ack_fail(
                        job.job_id,
                        error_reason=f"timeout: {e}",
                        consumer_id=self._consumer_id,
                    )
                    current_job = None
                except Exception as e:
                    self._orchestrator.ack_fail(
                        job.job_id,
                        error_reason=f"error: {e}",
                        consumer_id=self._consumer_id,
                    )
                    current_job = None
                else:
                    self._orchestrator.ack_success(job.job_id, consumer_id=self._consumer_id)
                    current_job = None
        except BaseException as e:
            self._last_error = str(e)
            if current_job is not None:
                self._safe_ack_fail(current_job, f"worker_crash: {e}")
                current_job = None
        finally:
            if current_job is not None:
                self._safe_ack_fail(current_job, "worker_stopped_while_inflight")
            self._stop_event.set()


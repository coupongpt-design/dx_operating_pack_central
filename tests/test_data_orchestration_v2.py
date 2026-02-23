import random
import threading
import time

from app.core.data_orchestration import JobQueueManager


def _drain_worker(manager: JobQueueManager, consumer_id: str, seen: set[str], seen_lock: threading.Lock):
    while not manager.is_fully_done():
        job = manager.request_job(consumer_id=consumer_id)
        if job is None:
            time.sleep(manager.get_recommended_sleep_sec(default_sleep_sec=0.0005, max_sleep_sec=0.01))
            continue
        with seen_lock:
            if job.job_id in seen:
                raise AssertionError(f"duplicate dispatch detected: {job.job_id}")
            seen.add(job.job_id)
        manager.acknowledge_success(job)


def test_distribution_no_duplicate():
    rows = [{"value": i} for i in range(200)]
    manager = JobQueueManager(rows, max_retry=0, retry_delay_sec=0.001)
    seen: set[str] = set()
    seen_lock = threading.Lock()
    threads = [
        threading.Thread(target=_drain_worker, args=(manager, f"c{i}", seen, seen_lock), daemon=True)
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(3.0)

    snap = manager.snapshot()
    assert len(seen) == 200
    assert snap["succeeded"] == 200
    assert snap["failed"] == 0
    assert snap["retried"] == 0
    assert manager.is_fully_done() is True


def _request_until_job(manager: JobQueueManager, consumer_id: str, timeout_sec: float = 1.0):
    started = time.perf_counter()
    while time.perf_counter() - started <= timeout_sec:
        job = manager.request_job(consumer_id=consumer_id)
        if job is not None:
            return job
        if manager.is_fully_done():
            return None
        time.sleep(manager.get_recommended_sleep_sec(default_sleep_sec=0.0005, max_sleep_sec=0.01))
    return None


def test_retry_cap():
    manager = JobQueueManager([{"row": 1}], max_retry=2, retry_delay_sec=0.001)

    for i in range(3):
        job = _request_until_job(manager, consumer_id="retry")
        assert job is not None
        retried = manager.acknowledge_failure(job, error_reason=f"boom-{i}")
        if i < 2:
            assert retried is True
        else:
            assert retried is False

    snap = manager.snapshot()
    assert snap["succeeded"] == 0
    assert snap["failed"] == 1
    assert snap["retried"] == 2
    row = snap["rows"][0]
    assert row["status"] == "failed"
    assert row["error_reason"] == "boom-2"


def test_failure_isolation():
    rows = [{"row": 0}, {"row": 1}, {"row": 2}]
    manager = JobQueueManager(rows, max_retry=0, retry_delay_sec=0.001)

    failed_job = _request_until_job(manager, consumer_id="iso")
    assert failed_job is not None
    assert manager.acknowledge_failure(failed_job, error_reason="bad-row") is False

    while not manager.is_fully_done():
        job = manager.request_job(consumer_id="iso")
        if job is None:
            time.sleep(manager.get_recommended_sleep_sec(default_sleep_sec=0.0005, max_sleep_sec=0.01))
            continue
        manager.acknowledge_success(job)

    snap = manager.snapshot()
    assert snap["failed"] == 1
    assert snap["succeeded"] == 2


def test_aggregation_correctness():
    manager = JobQueueManager([{"x": i} for i in range(4)], max_retry=2, retry_delay_sec=0.001)
    dispatch_count: dict[str, int] = {}
    while not manager.is_fully_done():
        j = manager.request_job("agg")
        if j is None:
            time.sleep(manager.get_recommended_sleep_sec(default_sleep_sec=0.0005, max_sleep_sec=0.01))
            continue
        jid = j.job_id
        dispatch_count[jid] = dispatch_count.get(jid, 0) + 1
        dcount = dispatch_count[jid]
        if jid == "row-0":
            manager.acknowledge_success(j)
        elif jid == "row-1":
            if dcount == 1:
                assert manager.acknowledge_failure(j, "temp") is True
            else:
                manager.acknowledge_success(j)
        elif jid == "row-2":
            expect_retry = dcount < 3
            assert manager.acknowledge_failure(j, f"f{dcount}") is expect_retry
        elif jid == "row-3":
            manager.acknowledge_success(j)
        else:
            raise AssertionError(f"unexpected job id: {jid}")

    snap = manager.snapshot()
    assert snap["total_jobs"] == 4
    assert snap["succeeded"] == 3
    assert snap["failed"] == 1
    assert snap["retried"] == 3

    rows = {r["job_id"]: r for r in snap["rows"]}
    assert rows["row-2"]["status"] == "failed"
    assert rows["row-2"]["error_reason"] == "f3"
    assert rows["row-1"]["status"] == "success"


def test_multithread_stress():
    total_jobs = 1000
    fail_prob = 0.2
    max_retry = 2
    manager = JobQueueManager(
        [{"payload": i} for i in range(total_jobs)],
        max_retry=max_retry,
        retry_delay_sec=0.0005,
    )

    def worker(worker_idx: int):
        rng = random.Random(1000 + worker_idx)
        while not manager.is_fully_done():
            job = manager.request_job(consumer_id=f"w{worker_idx}")
            if job is None:
                time.sleep(manager.get_recommended_sleep_sec(default_sleep_sec=0.0005, max_sleep_sec=0.01))
                continue
            time.sleep(rng.uniform(0.0, 0.001))
            if rng.random() < fail_prob:
                manager.acknowledge_failure(job, error_reason="random_fail")
            else:
                manager.acknowledge_success(job)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20.0)

    snap = manager.snapshot()
    assert manager.is_fully_done() is True
    assert snap["total_jobs"] == total_jobs
    assert snap["succeeded"] + snap["failed"] == total_jobs
    assert snap["inflight"] == 0
    assert snap["ready"] == 0
    assert snap["delayed"] == 0
    assert snap["retried"] > 0


def test_retry_backoff_delays_redispatch_until_next_retry_time():
    now = {"t": 100.0}
    manager = JobQueueManager(
        [{"row": 1}],
        max_retry=1,
        retry_delay_sec=0.5,
        time_fn=lambda: now["t"],
    )

    job = manager.request_job("bk")
    assert job is not None
    assert manager.acknowledge_failure(job, error_reason="temp") is True

    assert manager.request_job("bk") is None
    sleep_sec = manager.get_recommended_sleep_sec(default_sleep_sec=0.01, max_sleep_sec=10.0)
    assert sleep_sec >= 0.49

    now["t"] += 0.49
    assert manager.request_job("bk") is None

    now["t"] += 0.02
    retried = manager.request_job("bk")
    assert retried is not None
    assert retried.job_id == "row-0"
    manager.acknowledge_success(retried)
    assert manager.is_fully_done() is True


def test_is_fully_done_requires_inflight_empty():
    manager = JobQueueManager([{"x": 1}], max_retry=0, retry_delay_sec=0.001)
    job = manager.request_job("done-check")
    assert job is not None
    assert manager.is_fully_done() is False

    manager.acknowledge_success(job)
    assert manager.is_fully_done() is True

import json
import time
from pathlib import Path

from app.core.models import RepeatConfig, StepData
from app.core.runner import MacroRunner


class DummyMSS:
    def __init__(self, *a, **k):
        self.monitors = [{"left": 0, "top": 0, "width": 20, "height": 20}]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_runner_writes_structured_jsonl_success(monkeypatch, tmp_path):
    import app.core.runner as runner_mod

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    step = StepData(id="s1", name="Comment", type="comment")
    step.source_step_id = "source-s1"
    runner = MacroRunner(
        [step],
        repeat=RepeatConfig(repeat_count=1),
        dry_run=True,
        structured_logging=True,
        structured_log_dir=str(tmp_path),
    )
    runner.run()

    assert runner.structured_log_path
    rows = _read_jsonl(Path(runner.structured_log_path))
    assert rows
    run_ids = {row.get("run_id") for row in rows}
    assert run_ids == {runner.run_id}

    events = [row.get("event") for row in rows]
    assert "run_started" in events
    assert "step_started" in events
    assert "step_succeeded" in events
    assert "run_finished" in events

    success = next(row for row in rows if row.get("event") == "step_succeeded")
    assert success.get("step_uuid") == "source-s1"
    assert isinstance(success.get("duration_ms"), int)
    assert success.get("duration_ms") >= 0

    finished = next(row for row in rows if row.get("event") == "run_finished")
    assert finished.get("success") is True
    assert isinstance(finished.get("duration_ms"), int)


def test_runner_writes_structured_jsonl_failure(monkeypatch, tmp_path):
    import app.core.runner as runner_mod

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    bad = StepData(id="bad", name="Bad", type="unknown_type")
    bad.source_step_id = "bad-source"
    runner = MacroRunner(
        [bad],
        repeat=RepeatConfig(repeat_count=1, stop_on_fail=True),
        dry_run=True,
        structured_logging=True,
        structured_log_dir=str(tmp_path),
    )
    runner.run()

    rows = _read_jsonl(Path(runner.structured_log_path))
    fail = next(row for row in rows if row.get("event") == "step_failed")
    assert fail.get("step_uuid") == "bad-source"
    assert "error" in fail
    assert isinstance(fail.get("duration_ms"), int)
    assert fail.get("duration_ms") >= 0

    finished = next(row for row in rows if row.get("event") == "run_finished")
    assert finished.get("success") is False
    assert finished.get("reason") == "step_failed_stop_on_fail"


def test_runner_pause_resume_logs_events(monkeypatch, tmp_path):
    import app.core.runner as runner_mod

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    steps = [
        StepData(id="w1", name="Wait1", type="wait", wait_ms=500),
        StepData(id="w2", name="Wait2", type="wait", wait_ms=500),
    ]
    runner = MacroRunner(
        steps,
        repeat=RepeatConfig(repeat_count=1),
        dry_run=True,
        structured_logging=True,
        structured_log_dir=str(tmp_path),
    )
    runner.start()
    time.sleep(0.05)
    assert runner.pause() is True
    time.sleep(0.05)
    assert runner.resume_run() is True
    assert runner.wait(3000)

    rows = _read_jsonl(Path(runner.structured_log_path))
    events = [row.get("event") for row in rows]
    assert "run_paused" in events
    assert "run_resumed" in events


def test_runner_kill_logs_events_and_finishes_failed(monkeypatch, tmp_path):
    import app.core.runner as runner_mod

    monkeypatch.setattr(runner_mod.mss, "mss", DummyMSS, raising=False)

    runner = MacroRunner(
        [StepData(id="w1", name="Wait", type="wait", wait_ms=5000)],
        repeat=RepeatConfig(repeat_count=1),
        dry_run=True,
        structured_logging=True,
        structured_log_dir=str(tmp_path),
    )
    runner.start()
    time.sleep(0.05)
    runner.kill(reason="test_kill")
    assert runner.wait(3000)

    rows = _read_jsonl(Path(runner.structured_log_path))
    events = [row.get("event") for row in rows]
    assert "run_killed" in events
    finished = next(row for row in rows if row.get("event") == "run_finished")
    assert finished.get("success") is False
    assert finished.get("reason") == "killed"

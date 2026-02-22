import json
from pathlib import Path

from app.core.run_history import list_run_summaries, load_run_events, summarize_run_events


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_run_events_skips_broken_lines(tmp_path):
    path = tmp_path / "run_events_broken.jsonl"
    path.write_text('{"a":1}\nnot-json\n{"b":2}\n', encoding="utf-8")
    rows = load_run_events(path)
    assert rows == [{"a": 1}, {"b": 2}]


def test_summarize_run_events_success_with_slowest_step(tmp_path):
    path = tmp_path / "run_events_1.jsonl"
    rows = [
        {
            "timestamp": "2026-02-22T05:25:01.000Z",
            "run_id": "run_a",
            "event": "run_started",
            "level": "INFO",
        },
        {
            "timestamp": "2026-02-22T05:25:02.000Z",
            "run_id": "run_a",
            "event": "step_started",
            "step_uuid": "s1",
            "step_name": "login",
        },
        {
            "timestamp": "2026-02-22T05:25:03.000Z",
            "run_id": "run_a",
            "event": "step_succeeded",
            "step_uuid": "s1",
            "step_name": "login",
            "duration_ms": 1000,
        },
        {
            "timestamp": "2026-02-22T05:25:04.000Z",
            "run_id": "run_a",
            "event": "step_started",
            "step_uuid": "s2",
            "step_name": "scan",
        },
        {
            "timestamp": "2026-02-22T05:25:05.000Z",
            "run_id": "run_a",
            "event": "step_succeeded",
            "step_uuid": "s2",
            "step_name": "scan",
            "duration_ms": 2200,
        },
        {
            "timestamp": "2026-02-22T05:25:06.000Z",
            "run_id": "run_a",
            "event": "run_finished",
            "success": True,
            "duration_ms": 5000,
        },
    ]
    _write_jsonl(path, rows)

    summary = summarize_run_events(load_run_events(path), file_path=path)
    assert summary is not None
    assert summary.run_id == "run_a"
    assert summary.status == "success"
    assert summary.duration_ms == 5000
    assert summary.total_steps == 2
    assert summary.failed_steps == 0
    assert summary.slowest_step_name == "scan"
    assert summary.slowest_duration_ms == 2200


def test_summarize_run_events_failed_when_finish_event_false(tmp_path):
    path = tmp_path / "run_events_2.jsonl"
    rows = [
        {"timestamp": "2026-02-22T05:25:01.000Z", "run_id": "run_b", "event": "run_started"},
        {"timestamp": "2026-02-22T05:25:02.000Z", "run_id": "run_b", "event": "step_started"},
        {
            "timestamp": "2026-02-22T05:25:03.000Z",
            "run_id": "run_b",
            "event": "step_failed",
            "step_name": "ocr",
            "duration_ms": 3000,
            "error": "timeout",
        },
        {
            "timestamp": "2026-02-22T05:25:04.000Z",
            "run_id": "run_b",
            "event": "run_finished",
            "success": False,
            "duration_ms": 4000,
        },
    ]
    _write_jsonl(path, rows)

    summary = summarize_run_events(load_run_events(path), file_path=path)
    assert summary is not None
    assert summary.status == "failed"
    assert summary.failed_steps == 1
    assert summary.slowest_step_name == "ocr"
    assert summary.slowest_duration_ms == 3000


def test_list_run_summaries_returns_newest_first(tmp_path):
    path_old = tmp_path / "run_events_old.jsonl"
    path_new = tmp_path / "run_events_new.jsonl"
    _write_jsonl(
        path_old,
        [
            {"timestamp": "2026-02-22T01:00:00.000Z", "run_id": "old", "event": "run_started"},
            {"timestamp": "2026-02-22T01:01:00.000Z", "run_id": "old", "event": "run_finished", "success": True},
        ],
    )
    _write_jsonl(
        path_new,
        [
            {"timestamp": "2026-02-22T02:00:00.000Z", "run_id": "new", "event": "run_started"},
            {"timestamp": "2026-02-22T02:01:00.000Z", "run_id": "new", "event": "run_finished", "success": True},
        ],
    )

    rows = list_run_summaries(tmp_path)
    assert len(rows) == 2
    assert rows[0].run_id == "new"
    assert rows[1].run_id == "old"

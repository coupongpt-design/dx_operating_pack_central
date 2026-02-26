from __future__ import annotations

from tools.task_start_guard import _count_cleanup_artifact_deletes
from tools.task_start_guard import run_guard


def test_count_cleanup_artifact_deletes() -> None:
    text = "D\tlogs/a.jsonl\nD\tapp/__pycache__/x.pyc\nM\tapp/main.py\n"
    assert _count_cleanup_artifact_deletes(text) == 2


def test_run_guard_blocks_when_staged_entries_exist(monkeypatch) -> None:
    import tools.task_start_guard as guard
    ctx = run_guard.__globals__

    monkeypatch.setitem(ctx, "_git", lambda *args: "M\tapp/main.py\n")
    assert run_guard() == 1


def test_run_guard_passes_when_index_clean(monkeypatch) -> None:
    import tools.task_start_guard as guard
    ctx = run_guard.__globals__

    monkeypatch.setitem(ctx, "_git", lambda *args: "")
    assert run_guard() == 0

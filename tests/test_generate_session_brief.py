from __future__ import annotations

import time
from pathlib import Path

import tools.generate_session_brief as brief


def test_build_brief_contains_required_sections(tmp_path, monkeypatch) -> None:
    ctx = brief.build_brief.__globals__
    snap = tmp_path / "CONTEXT_SNAPSHOT.md"
    snap.write_text("# snapshot\n", encoding="utf-8")
    monkeypatch.setitem(ctx, "SNAPSHOT_FILES", (snap,))

    now = time.time()
    monkeypatch.setitem(
        ctx,
        "_load_gate",
        lambda: {
            "timestamp": now,
            "targeted_pass": True,
            "full_suite_required": False,
            "full_suite_pass": True,
        },
    )

    def _fake_git(*args: str) -> str:
        if args == ("branch", "--show-current"):
            return "feature/test\n"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc123\n"
        if args[0] == "log":
            return "abc123 feat: sample\n"
        if args[:4] == ("show", "--name-only", "--pretty=format:", "--no-renames"):
            return "tools/task_finish.py\n"
        return ""

    monkeypatch.setitem(ctx, "_safe_git", _fake_git)
    text = brief.build_brief(max_commits=1)
    assert "# SESSION BRIEF" in text
    assert "## Fast Catch-Up Order" in text
    assert "## Gate Status" in text
    assert "## Snapshot Freshness" in text
    assert "`tools/task_finish.py`" in text


def test_snapshot_summary_marks_missing_file(tmp_path, monkeypatch) -> None:
    ctx = brief._snapshot_summary.__globals__
    missing = tmp_path / "MISSING.md"
    monkeypatch.setitem(ctx, "SNAPSHOT_FILES", (missing,))
    rows = brief._snapshot_summary(time.time())
    assert rows == [f"- {missing.name}: missing"]

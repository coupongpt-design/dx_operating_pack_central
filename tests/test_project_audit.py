from __future__ import annotations

import json
import time
from pathlib import Path

from tools import project_audit


def test_run_audit_writes_report_when_assets_exist(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    gate_path = tmp_path / ".git" / "post_task_gate.json"
    gate_path.write_text(json.dumps({"timestamp": time.time()}), encoding="utf-8")

    for name in ("now_spec.md", "PROJECT_STATUS.md", "DEV_LOG.md", "DOC_INDEX.md", "ASSET_MAP.md"):
        (tmp_path / name).write_text("ok", encoding="utf-8")
    (tmp_path / "app/core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "app/core/runner.py").write_text("# ok", encoding="utf-8")

    monkeypatch.setattr(project_audit, "ASSET_GROUPS", {"Product": ["app/core/runner.py"]})
    monkeypatch.setattr(
        project_audit,
        "DOC_SYNC_FILES",
        ("now_spec.md", "PROJECT_STATUS.md", "DEV_LOG.md", "DOC_INDEX.md", "ASSET_MAP.md"),
    )
    monkeypatch.setattr(project_audit, "GATE_FILES", (Path(".git/post_task_gate.json"),))

    report_path = tmp_path / "project_audit_latest.md"
    rc = project_audit.run_audit(report_path)
    assert rc == 0
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "Asset Integrity" in text
    assert "Gate Freshness" in text


def test_run_audit_returns_nonzero_when_assets_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    gate_path = tmp_path / ".git" / "post_task_gate.json"
    gate_path.write_text(json.dumps({"timestamp": time.time()}), encoding="utf-8")

    for name in ("now_spec.md", "PROJECT_STATUS.md", "DEV_LOG.md", "DOC_INDEX.md", "ASSET_MAP.md"):
        (tmp_path / name).write_text("ok", encoding="utf-8")

    monkeypatch.setattr(project_audit, "ASSET_GROUPS", {"Product": ["app/core/missing.py"]})
    monkeypatch.setattr(
        project_audit,
        "DOC_SYNC_FILES",
        ("now_spec.md", "PROJECT_STATUS.md", "DEV_LOG.md", "DOC_INDEX.md", "ASSET_MAP.md"),
    )
    monkeypatch.setattr(project_audit, "GATE_FILES", (Path(".git/post_task_gate.json"),))

    report_path = tmp_path / "project_audit_latest.md"
    rc = project_audit.run_audit(report_path)
    assert rc == 1

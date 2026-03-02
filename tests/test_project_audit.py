from __future__ import annotations

import json
import os
import time
from pathlib import Path

from tools import project_audit


def test_default_doc_sync_paths_use_docs_directory() -> None:
    assert "docs/DOC_INDEX.md" in project_audit.DOC_SYNC_FILES
    assert "docs/ASSET_MAP.md" in project_audit.DOC_SYNC_FILES


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
    assert "Verification Health" in text
    assert "Asset Integrity Matrix" in text
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


def test_run_audit_returns_nonzero_when_gate_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    gate_path = tmp_path / ".git" / "post_task_gate.json"
    gate_path.write_text(json.dumps({"timestamp": time.time() - 10}), encoding="utf-8")

    for name in ("now_spec.md", "PROJECT_STATUS.md", "DEV_LOG.md", "DOC_INDEX.md", "ASSET_MAP.md"):
        (tmp_path / name).write_text("ok", encoding="utf-8")
    (tmp_path / "app/core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "app/core/runner.py").write_text("# ok", encoding="utf-8")

    monkeypatch.setattr(project_audit, "ASSET_GROUPS", {"Product": ["app/core/runner.py"]})
    monkeypatch.setattr(project_audit, "GATE_FILES", (Path(".git/post_task_gate.json"),))
    monkeypatch.setattr(project_audit, "GATE_TTL_SEC", 1)

    report_path = tmp_path / "project_audit_latest.md"
    rc = project_audit.run_audit(report_path)
    assert rc == 1


def test_run_audit_returns_nonzero_when_docs_out_of_sync(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    gate_path = tmp_path / ".git" / "post_task_gate.json"
    gate_path.write_text(json.dumps({"timestamp": time.time()}), encoding="utf-8")

    now = time.time()
    for name in ("now_spec.md", "PROJECT_STATUS.md", "DEV_LOG.md", "DOC_INDEX.md", "ASSET_MAP.md"):
        (tmp_path / name).write_text("ok", encoding="utf-8")
    os.utime(tmp_path / "now_spec.md", (now - (49 * 3600), now - (49 * 3600)))
    os.utime(tmp_path / "PROJECT_STATUS.md", (now, now))
    os.utime(tmp_path / "DEV_LOG.md", (now, now))
    os.utime(tmp_path / "DOC_INDEX.md", (now, now))
    os.utime(tmp_path / "ASSET_MAP.md", (now, now))

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
    assert rc == 1

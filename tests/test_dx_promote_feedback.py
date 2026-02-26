from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path("dx_operating_pack/tools/promote_dx_feedback.py").resolve()
    spec = importlib.util.spec_from_file_location("dx_promote_feedback", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_load_bundles_reads_manifest(tmp_path) -> None:
    mod = _load_module()
    inbox = tmp_path / "feedback" / "inbox" / "projectA" / "bundle1"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "feedback_manifest.json").write_text('{"changed_files_count":2}', encoding="utf-8")
    bundles = mod._load_bundles(tmp_path / "feedback" / "inbox")
    assert len(bundles) == 1
    assert bundles[0].project == "projectA"


def test_promote_apply_copies_reusable_and_moves_bundle(tmp_path) -> None:
    mod = _load_module()
    repo_root = tmp_path
    bundle = repo_root / "feedback" / "inbox" / "proj" / "bundleX"
    (bundle / "reusable_changes" / "reusable/core").mkdir(parents=True, exist_ok=True)
    (bundle / "reusable_changes" / "reusable/core/tool.py").write_text("x=1", encoding="utf-8")
    (bundle / "LESSONS_LEARNED.md").write_text("lesson", encoding="utf-8")
    (bundle / "feedback_manifest.json").write_text(
        json.dumps({"changed_files_count": 1, "reusable_changes_count": 1}, ensure_ascii=False),
        encoding="utf-8",
    )

    bundles = mod._load_bundles(repo_root / "feedback" / "inbox")
    copied = mod._copy_reusable_changes(bundles[0], repo_root)
    assert copied == ["reusable/core/tool.py"]
    assert (repo_root / "reusable/core/tool.py").exists()

    assert mod._append_lessons_snapshot(bundles[0], repo_root) is True
    assert (repo_root / "docs/LESSONS_LEARNED_DRAFT.md").exists()

    moved = mod._move_processed(bundles[0], repo_root / "feedback" / "processed")
    assert moved.exists()
    assert not bundle.exists()

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path("dx_operating_pack/tools/push_dx_feedback.py").resolve()
    spec = importlib.util.spec_from_file_location("dx_push_feedback", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_detect_reusable_changes() -> None:
    mod = _load_module()
    files = [
        "reusable/core/a.py",
        "app/main.py",
        "dx_operating_pack/reusable/ui/x.py",
        "docs/README.md",
    ]
    assert mod._detect_reusable_changes(files) == [
        "dx_operating_pack/reusable/ui/x.py",
        "reusable/core/a.py",
    ]


def test_build_feedback_bundle_writes_manifest_and_assets(tmp_path, monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.chdir(tmp_path)

    reusable_file = tmp_path / "reusable" / "core" / "logic.py"
    reusable_file.parent.mkdir(parents=True, exist_ok=True)
    reusable_file.write_text("print('ok')", encoding="utf-8")

    insight = tmp_path / "feedback" / "LATEST_INSIGHT.yaml"
    insight.parent.mkdir(parents=True, exist_ok=True)
    insight.write_text("schema_version: 1\n", encoding="utf-8")

    lessons = tmp_path / "docs" / "LESSONS_LEARNED.md"
    lessons.parent.mkdir(parents=True, exist_ok=True)
    lessons.write_text("# lessons\n", encoding="utf-8")

    outbox = tmp_path / "feedback" / "outbox"
    bundle = mod.build_feedback_bundle(
        project_name="macro-editor",
        base="HEAD~1",
        head="HEAD",
        changed_files=["reusable/core/logic.py", "app/main.py"],
        insight_path=insight,
        lessons_path=lessons,
        outbox_root=outbox,
    )

    assert (bundle / "feedback_manifest.json").exists()
    assert (bundle / "LATEST_INSIGHT.yaml").exists()
    assert (bundle / "LESSONS_LEARNED.md").exists()
    assert (bundle / "reusable_changes" / "reusable/core/logic.py").exists()

    manifest = json.loads((bundle / "feedback_manifest.json").read_text(encoding="utf-8"))
    assert manifest["project_name"] == "macro-editor"
    assert manifest["reusable_changes_count"] == 1

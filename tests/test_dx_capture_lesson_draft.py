from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _load_module():
    path = Path("dx_operating_pack/tools/capture_lesson_draft.py").resolve()
    spec = importlib.util.spec_from_file_location("dx_capture_lesson_draft", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_default_paths_prefer_dx_pack_docs() -> None:
    mod = _load_module()
    assert str(mod.DEFAULT_DRAFT_PATHS[0]).replace("\\", "/") == "dx_operating_pack/docs/LESSONS_LEARNED_DRAFT.md"
    assert str(mod.DEFAULT_LESSONS_PATHS[0]).replace("\\", "/") == "dx_operating_pack/docs/LESSONS_LEARNED.md"


def test_extract_added_lines_filters_noise() -> None:
    mod = _load_module()
    diff = "\n".join(
        [
            "@@ -1,0 +1,3 @@",
            "+## Heading",
            "+- lesson item",
            "+plain note",
            "+++ b/docs/LESSONS_LEARNED.md",
        ]
    )
    assert mod._extract_added_lines(diff) == ["- lesson item", "plain note"]


def test_build_insight_payload_and_yaml_render() -> None:
    mod = _load_module()
    payload = mod.build_insight_payload(
        title="Gate Harvest",
        base="HEAD~1",
        head="HEAD",
        from_staged=True,
        files=["reusable/core/template_processor.py", "docs/LESSONS_LEARNED.md"],
        added_lessons=["템플릿 치환 우선"],
        reusable_changes=["reusable/core/template_processor.py"],
    )
    text = mod.render_yaml(payload)
    assert "schema_version: 1" in text
    assert "mode: \"staged\"" in text
    assert "changed_files_count: 2" in text


def test_extract_ai_session_context_reads_latest_json_markdown_logs(tmp_path: Path) -> None:
    mod = _load_module()
    session = tmp_path / "s001"
    session.mkdir()

    planner = session / "planner_plan.md"
    planner.write_text("Decision: keep planner sequence\n", encoding="utf-8")

    old_json = session / "old_log.json"
    old_json.write_text("{\"warning\": \"old warning\"}", encoding="utf-8")
    new_json = session / "latest_log.json"
    new_json.write_text(
        "{\"Decision\": \"use guarded path\", \"nested\": {\"Reason\": \"safer\"}}",
        encoding="utf-8",
    )

    old_md = session / "old_notes.md"
    old_md.write_text("Warning: stale\n", encoding="utf-8")
    new_md = session / "latest_notes.md"
    new_md.write_text("Warning: from latest markdown\n", encoding="utf-8")

    now = os.path.getmtime(new_json)
    os.utime(old_json, (now - 60, now - 60))
    os.utime(old_md, (now - 60, now - 60))
    os.utime(new_md, (now + 60, now + 60))

    ctx = mod._extract_ai_session_context(session)
    assert "use guarded path" in ctx["decisions"]
    assert "safer" in ctx["reasons"]
    assert "from latest markdown" in ctx["warnings"]
    assert "latest_log.json" in ctx["sources"]
    assert "latest_notes.md" in ctx["sources"]

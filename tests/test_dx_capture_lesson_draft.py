from __future__ import annotations

import importlib.util
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

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


HINTS = [
    ("template_processor", "치환/데이터 바인딩 로직 검증 필요"),
    ("input_lock", "동시 입력 경합 테스트 필요"),
    ("session_adapter", "stop_event 기반 중단 경로 검증 필요"),
    ("data_orchestration", "retry/inflight 무결성 테스트 필요"),
    ("runner", "실행 경로 회귀 위험: full pytest 권장"),
    ("styles.py", "UI 가시성/레이아웃 회귀 확인 필요"),
]

DEFAULT_DRAFT_PATHS = (
    Path("docs/LESSONS_LEARNED_DRAFT.md"),
    Path("docs/dx_pack/LESSONS_LEARNED_DRAFT.md"),
)
DEFAULT_LESSONS_PATHS = (
    Path("docs/LESSONS_LEARNED.md"),
    Path("docs/dx_pack/LESSONS_LEARNED.md"),
)
DEFAULT_INSIGHT_PATHS = (
    Path("feedback/LATEST_INSIGHT.yaml"),
    Path("dx_operating_pack/feedback/LATEST_INSIGHT.yaml"),
)


def _changed_files(base: str, head: str, *, from_staged: bool = False) -> list[str]:
    cmd = ["git", "diff", "--cached", "--name-only"] if from_staged else ["git", "diff", "--name-only", f"{base}..{head}"]
    out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _extract_added_lines(diff_text: str) -> list[str]:
    added: list[str] = []
    for raw in diff_text.splitlines():
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        line = raw[1:].strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        added.append(line)
    return added


def _added_lessons(base: str, head: str, lessons_path: Path, *, from_staged: bool = False) -> list[str]:
    if not lessons_path.exists():
        return []
    cmd = (
        ["git", "diff", "--cached", "--unified=0", "--", str(lessons_path)]
        if from_staged
        else ["git", "diff", "--unified=0", f"{base}..{head}", "--", str(lessons_path)]
    )
    out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
    return _extract_added_lines(out)


def _resolve_first_existing(candidates: tuple[Path, ...], fallback: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for candidate in candidates:
        if candidate.parent.exists():
            return candidate
    return fallback


def _detect_reusable_changes(files: list[str]) -> list[str]:
    out: list[str] = []
    for file in files:
        norm = file.replace("\\", "/")
        if norm.startswith("reusable/") or "/reusable/" in norm:
            out.append(norm)
    return sorted(dict.fromkeys(out))


def build_draft(files: list[str], title: str, *, added_lessons: list[str], reusable_changes: list[str]) -> str:
    lines: list[str] = []
    lines.append(f"## {title}")
    lines.append(f"- generated_at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- changed_files: {len(files)}")
    for f in files:
        lines.append(f"  - `{f}`")

    lines.append("")
    lines.append("### Suggested Lessons")
    matched = False
    for key, note in HINTS:
        if any(key in f for f in files):
            lines.append(f"- {note}")
            matched = True
    if not matched:
        lines.append("- 변경 범위 기반으로 핵심 회귀 포인트를 수동 추가하세요.")
    if reusable_changes:
        lines.append("- reusable 변경 감지: 공통 모듈 승격 검토 필요")
    if added_lessons:
        lines.append("")
        lines.append("### New Lessons (from diff)")
        for item in added_lessons[:10]:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("### Human Review Notes")
    lines.append("- [ ] 실제 실패 원인 요약")
    lines.append("- [ ] 재발 방지 룰/테스트 추가 여부")
    lines.append("")
    return "\n".join(lines)


def build_insight_payload(
    *,
    title: str,
    base: str,
    head: str,
    from_staged: bool,
    files: list[str],
    added_lessons: list[str],
    reusable_changes: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "title": title,
        "source": {
            "mode": "staged" if from_staged else "range",
            "base": base,
            "head": head,
        },
        "stats": {
            "changed_files_count": len(files),
            "reusable_changes_count": len(reusable_changes),
            "added_lessons_count": len(added_lessons),
        },
        "changed_files": files,
        "reusable_changes": reusable_changes,
        "added_lessons": added_lessons,
    }


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{text}\""


def render_yaml(data: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(data, dict):
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(render_yaml(value, indent + 2))
            else:
                lines.append(f"{pad}{key}: {_yaml_scalar(value)}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(render_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}- {_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_yaml_scalar(data)}"


def _write_text(path: Path, content: str, *, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and path.exists() else "w"
    with path.open(mode, encoding="utf-8") as fp:
        if mode == "a":
            fp.write("\n")
        fp.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lessons-learned draft from git diff.")
    parser.add_argument("--base", default="HEAD~1", help="Base commit/ref")
    parser.add_argument("--head", default="HEAD", help="Head commit/ref")
    parser.add_argument(
        "--from-staged",
        action="store_true",
        help="Use staged diff (`git diff --cached`) instead of base..head range.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output markdown path",
    )
    parser.add_argument(
        "--lessons",
        default="",
        help="Lessons source markdown path (for added-lines harvesting).",
    )
    parser.add_argument(
        "--insight-out",
        default="",
        help="YAML insight output path. Default resolves to feedback/LATEST_INSIGHT.yaml.",
    )
    parser.add_argument(
        "--title",
        default="Auto Draft",
        help="Section title",
    )
    parser.add_argument(
        "--skip-draft",
        action="store_true",
        help="Do not append markdown draft.",
    )
    parser.add_argument(
        "--skip-insight",
        action="store_true",
        help="Do not write LATEST_INSIGHT.yaml.",
    )
    args = parser.parse_args()

    files = _changed_files(base=args.base, head=args.head, from_staged=args.from_staged)
    lessons_path = Path(args.lessons) if args.lessons else _resolve_first_existing(
        DEFAULT_LESSONS_PATHS,
        DEFAULT_LESSONS_PATHS[0],
    )
    added_lessons = _added_lessons(
        base=args.base,
        head=args.head,
        lessons_path=lessons_path,
        from_staged=args.from_staged,
    )
    reusable_changes = _detect_reusable_changes(files)

    if not args.skip_draft:
        draft = build_draft(
            files=files,
            title=args.title,
            added_lessons=added_lessons,
            reusable_changes=reusable_changes,
        )
        draft_out = Path(args.out) if args.out else _resolve_first_existing(
            DEFAULT_DRAFT_PATHS,
            DEFAULT_DRAFT_PATHS[0],
        )
        _write_text(draft_out, draft, append=True)
        print(f"[ok] lesson draft written: {draft_out}")

    if not args.skip_insight:
        insight = build_insight_payload(
            title=args.title,
            base=args.base,
            head=args.head,
            from_staged=args.from_staged,
            files=files,
            added_lessons=added_lessons,
            reusable_changes=reusable_changes,
        )
        insight_out = Path(args.insight_out) if args.insight_out else _resolve_first_existing(
            DEFAULT_INSIGHT_PATHS,
            DEFAULT_INSIGHT_PATHS[0],
        )
        _write_text(insight_out, render_yaml(insight), append=False)
        print(f"[ok] insight written: {insight_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


from __future__ import annotations

import argparse
import json
import re
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
    Path("dx_operating_pack/docs/LESSONS_LEARNED_DRAFT.md"),
    Path("docs/LESSONS_LEARNED_DRAFT.md"),
    Path("docs/dx_pack/LESSONS_LEARNED_DRAFT.md"),
)
DEFAULT_LESSONS_PATHS = (
    Path("dx_operating_pack/docs/LESSONS_LEARNED.md"),
    Path("docs/LESSONS_LEARNED.md"),
    Path("docs/dx_pack/LESSONS_LEARNED.md"),
)
DEFAULT_INSIGHT_PATHS = (
    Path("feedback/LATEST_INSIGHT.yaml"),
    Path("dx_operating_pack/feedback/LATEST_INSIGHT.yaml"),
)
AI_SESSION_ROOTS = (
    Path("logs/ai_sessions"),
    Path("dx_operating_pack/logs/ai_sessions"),
)
AI_SESSION_TEXT_EXTS = {".md", ".markdown"}
AI_SESSION_JSON_EXTS = {".json"}
AI_SESSION_SKIP_NAMES = {"planner_plan.md", "guardian_report.json", "executor_diff.json"}


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


def _extract_signal_lines(text: str, *, tag: str) -> list[str]:
    out: list[str] = []
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?(?:{re.escape(tag)}|{re.escape(tag.lower())}|{re.escape(tag.upper())})\s*[:\-]\s*(.+)$")
    for raw in (text or "").splitlines():
        m = pattern.search(raw.strip())
        if not m:
            continue
        val = m.group(1).strip()
        if val:
            out.append(val)
    return out


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _latest_session_log_file(session_dir: Path, *, exts: set[str]) -> Path | None:
    newest: tuple[float, Path] | None = None
    for child in session_dir.iterdir():
        if not child.is_file():
            continue
        if child.name.lower() in AI_SESSION_SKIP_NAMES:
            continue
        if child.suffix.lower() not in exts:
            continue
        ts = child.stat().st_mtime
        if newest is None or ts > newest[0]:
            newest = (ts, child)
    return newest[1] if newest else None


def _extract_json_signals(path: Path) -> tuple[list[str], list[str], list[str]]:
    decisions: list[str] = []
    reasons: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(_read_text(path))
    except Exception:
        return decisions, reasons, warnings

    def walk(node: Any, parent_key: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_l = str(key).strip().lower()
                if key_l.startswith("decision") and isinstance(value, (str, int, float)):
                    decisions.append(str(value).strip())
                elif key_l.startswith("reason") and isinstance(value, (str, int, float)):
                    reasons.append(str(value).strip())
                elif key_l.startswith("warning") and isinstance(value, (str, int, float)):
                    warnings.append(str(value).strip())
                walk(value, parent_key=key_l)
            return
        if isinstance(node, list):
            for value in node:
                walk(value, parent_key=parent_key)
            return
        if isinstance(node, str):
            text = node.strip()
            if not text:
                return
            decisions.extend(_extract_signal_lines(text, tag="Decision"))
            reasons.extend(_extract_signal_lines(text, tag="Reason"))
            warnings.extend(_extract_signal_lines(text, tag="Warning"))

    walk(payload)
    return decisions, reasons, warnings


def _latest_ai_session_dir() -> Path | None:
    newest: tuple[float, Path] | None = None
    for root in AI_SESSION_ROOTS:
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            ts = child.stat().st_mtime
            if newest is None or ts > newest[0]:
                newest = (ts, child)
    return newest[1] if newest else None


def _extract_ai_session_context(session_dir: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {"session_dir": "", "decisions": [], "reasons": [], "warnings": [], "sources": []}
    if session_dir is None or not session_dir.exists():
        return result

    decisions: list[str] = []
    reasons: list[str] = []
    warnings: list[str] = []
    sources: list[str] = []

    planner = session_dir / "planner_plan.md"
    if planner.exists():
        text = _read_text(planner)
        decisions.extend(_extract_signal_lines(text, tag="Decision"))
        reasons.extend(_extract_signal_lines(text, tag="Reason"))
        warnings.extend(_extract_signal_lines(text, tag="Warning"))
        sources.append(planner.name)

    guardian = session_dir / "guardian_report.json"
    if guardian.exists():
        try:
            payload = json.loads(_read_text(guardian))
            response = str(payload.get("guardian_response", "")).strip()
            decisions.extend(_extract_signal_lines(response, tag="Decision"))
            reasons.extend(_extract_signal_lines(response, tag="Reason"))
            warnings.extend(_extract_signal_lines(response, tag="Warning"))
            if payload.get("hard_gate_triggered", False):
                warnings.append("guardian hard gate triggered")
            sources.append(guardian.name)
        except Exception:
            warnings.append("guardian report parse failed")

    latest_json = _latest_session_log_file(session_dir, exts=AI_SESSION_JSON_EXTS)
    if latest_json:
        d, r, w = _extract_json_signals(latest_json)
        decisions.extend(d)
        reasons.extend(r)
        warnings.extend(w)
        sources.append(latest_json.name)

    latest_md = _latest_session_log_file(session_dir, exts=AI_SESSION_TEXT_EXTS)
    if latest_md:
        text = _read_text(latest_md)
        decisions.extend(_extract_signal_lines(text, tag="Decision"))
        reasons.extend(_extract_signal_lines(text, tag="Reason"))
        warnings.extend(_extract_signal_lines(text, tag="Warning"))
        sources.append(latest_md.name)

    def _uniq(rows: list[str]) -> list[str]:
        return list(dict.fromkeys([row.strip() for row in rows if row.strip()]))

    result["session_dir"] = str(session_dir).replace("\\", "/")
    result["decisions"] = _uniq(decisions)
    result["reasons"] = _uniq(reasons)
    result["warnings"] = _uniq(warnings)
    result["sources"] = _uniq(sources)
    return result


def build_draft(
    files: list[str],
    title: str,
    *,
    added_lessons: list[str],
    reusable_changes: list[str],
    ai_session_context: dict[str, Any] | None = None,
) -> str:
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
    if ai_session_context:
        decisions = list(ai_session_context.get("decisions", []))
        reasons = list(ai_session_context.get("reasons", []))
        warnings = list(ai_session_context.get("warnings", []))
        if decisions or reasons or warnings:
            lines.append("")
            lines.append("### AI Session Signals")
            for item in decisions[:5]:
                lines.append(f"- Decision: {item}")
            for item in reasons[:5]:
                lines.append(f"- Reason: {item}")
            for item in warnings[:5]:
                lines.append(f"- Warning: {item}")
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
    ai_session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ai_ctx = ai_session_context or {"session_dir": "", "decisions": [], "reasons": [], "warnings": []}
    decisions = list(ai_ctx.get("decisions", []))
    reasons = list(ai_ctx.get("reasons", []))
    warnings = list(ai_ctx.get("warnings", []))
    sources = list(ai_ctx.get("sources", []))
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
            "ai_decisions_count": len(decisions),
            "ai_reasons_count": len(reasons),
            "ai_warnings_count": len(warnings),
            "ai_sources_count": len(sources),
        },
        "changed_files": files,
        "reusable_changes": reusable_changes,
        "added_lessons": added_lessons,
        "ai_session_context": {
            "session_dir": str(ai_ctx.get("session_dir", "")),
            "decisions": decisions,
            "reasons": reasons,
            "warnings": warnings,
            "sources": sources,
        },
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
    parser.add_argument(
        "--ai-session-dir",
        default="",
        help="Optional explicit ai session dir. Defaults to latest under logs/ai_sessions.",
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
    ai_session_dir = Path(args.ai_session_dir) if args.ai_session_dir else _latest_ai_session_dir()
    ai_session_context = _extract_ai_session_context(ai_session_dir)

    if not args.skip_draft:
        draft = build_draft(
            files=files,
            title=args.title,
            added_lessons=added_lessons,
            reusable_changes=reusable_changes,
            ai_session_context=ai_session_context,
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
            ai_session_context=ai_session_context,
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


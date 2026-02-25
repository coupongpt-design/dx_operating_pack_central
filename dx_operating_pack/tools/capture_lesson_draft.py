from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path


HINTS = [
    ("template_processor", "치환/데이터 바인딩 로직 검증 필요"),
    ("input_lock", "동시 입력 경합 테스트 필요"),
    ("session_adapter", "stop_event 기반 중단 경로 검증 필요"),
    ("data_orchestration", "retry/inflight 무결성 테스트 필요"),
    ("runner", "실행 경로 회귀 위험: full pytest 권장"),
    ("styles.py", "UI 가시성/레이아웃 회귀 확인 필요"),
]


def _changed_files(base: str, head: str) -> list[str]:
    cmd = ["git", "diff", "--name-only", f"{base}..{head}"]
    out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
    return [line.strip() for line in out.splitlines() if line.strip()]


def build_draft(files: list[str], title: str) -> str:
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
    lines.append("")
    lines.append("### Human Review Notes")
    lines.append("- [ ] 실제 실패 원인 요약")
    lines.append("- [ ] 재발 방지 룰/테스트 추가 여부")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lessons-learned draft from git diff.")
    parser.add_argument("--base", default="HEAD~1", help="Base commit/ref")
    parser.add_argument("--head", default="HEAD", help="Head commit/ref")
    parser.add_argument(
        "--out",
        default="docs/LESSONS_LEARNED_DRAFT.md",
        help="Output markdown path",
    )
    parser.add_argument(
        "--title",
        default="Auto Draft",
        help="Section title",
    )
    args = parser.parse_args()

    files = _changed_files(base=args.base, head=args.head)
    draft = build_draft(files=files, title=args.title)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if out.exists() else "w"
    with out.open(mode, encoding="utf-8") as fp:
        if mode == "a":
            fp.write("\n")
        fp.write(draft)
    print(f"[ok] lesson draft written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


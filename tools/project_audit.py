from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_REPORT_PATH = Path("project_audit_latest.md")
GATE_FILES = (Path(".git") / "post_task_gate.json", Path("post_task_gate.json"))
GATE_TTL_SEC = 30 * 60
DOC_SYNC_FILES = (
    "now_spec.md",
    "PROJECT_STATUS.md",
    "DEV_LOG.md",
    "DOC_INDEX.md",
    "ASSET_MAP.md",
)
TEST_GLOB_PATTERNS = ("tests/test_*.py", "test_*.py")


ASSET_GROUPS: dict[str, list[str]] = {
    "Product": [
        "app/core/runner.py",
        "app/core/exceptions.py",
        "app/main.py",
        "app/ui/styles.py",
    ],
    "Rule Guard": [
        "AGENTS.md",
        ".cursorrules",
        "tools/git_hook_guards.py",
        "tests/test_rule_docs_sync.py",
        "tests/test_rule_guard_steps_mutation.py",
        ".githooks/pre-commit",
        ".githooks/commit-msg",
    ],
    "DX Tools": [
        "tools/task_start_guard.py",
        "tools/task_finish.py",
        "tools/test_selector.py",
        "tools/preflight_env.py",
        "tools/post_task_gate.py",
        "tools/project_audit.py",
    ],
    "Verification": [
        "tests",
        "pytest.ini",
        "test_core_logic.py",
    ],
    "Resources": [
        "images",
        "logs",
        "app/core/scenario_wizard_templates.json",
        "app/core/scenario_wizard_user_templates.json",
        "app/utils/runtime_paths.py",
    ],
    "Infrastructure": [
        "ASSET_MAP.md",
        "now_spec.md",
        "PROJECT_STATUS.md",
        "DEV_LOG.md",
        "DOC_INDEX.md",
        "USER_GUIDE.md",
        ".github/workflows/ci.yml",
    ],
}


@dataclass(frozen=True)
class AssetCheck:
    group: str
    path: str
    exists: bool


def _resolve_gate_file() -> Path | None:
    for gate in GATE_FILES:
        if gate.exists():
            return gate
    return None


def _load_gate_payload(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _iter_asset_checks() -> Iterable[AssetCheck]:
    for group, paths in ASSET_GROUPS.items():
        for rel in paths:
            yield AssetCheck(group=group, path=rel, exists=Path(rel).exists())


def _format_docs_mtime_table() -> tuple[str, list[str], bool]:
    rows: list[str] = []
    missing: list[str] = []
    mtimes: list[float] = []
    for rel in DOC_SYNC_FILES:
        path = Path(rel)
        if not path.exists():
            rows.append(f"| `{rel}` | ❌ missing | - |")
            missing.append(rel)
            continue
        mtime = path.stat().st_mtime
        mtimes.append(mtime)
        human = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        rows.append(f"| `{rel}` | ✅ exists | {human} |")
    out_of_sync = False
    if len(mtimes) >= 2 and (max(mtimes) - min(mtimes)) > 3600:
        out_of_sync = True
    return ("\n".join(rows), missing, out_of_sync)


def _format_gate_status() -> tuple[str, bool]:
    gate_path = _resolve_gate_file()
    if gate_path is None:
        return (
            "- Gate file: ❌ missing (`.git/post_task_gate.json` or `post_task_gate.json`)\n"
            "- TTL check: ⚠ skipped",
            False,
        )

    payload = _load_gate_payload(gate_path)
    ts_raw = payload.get("timestamp")
    if not isinstance(ts_raw, (int, float)):
        return (
            f"- Gate file: ⚠ unreadable timestamp (`{gate_path}`)\n"
            "- TTL check: ⚠ skipped",
            False,
        )
    age = max(0.0, float(time.time()) - float(ts_raw))
    stale = age > GATE_TTL_SEC
    stamp = datetime.fromtimestamp(float(ts_raw)).strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ fresh" if not stale else "❌ stale"
    return (
        f"- Gate file: ✅ `{gate_path}`\n"
        f"- Last gate: `{stamp}`\n"
        f"- TTL check (30m): {status} (age={int(age)}s)",
        not stale,
    )


def _count_test_files() -> int:
    files: set[Path] = set()
    for pattern in TEST_GLOB_PATTERNS:
        files.update(Path(".").glob(pattern))
    return len(files)


def _resource_snapshot() -> list[str]:
    images_dir = Path("images")
    logs_dir = Path("logs")
    image_count = 0
    if images_dir.exists():
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"):
            image_count += len(list(images_dir.glob(pattern)))
    log_jsonl_count = len(list(logs_dir.glob("*.jsonl"))) if logs_dir.exists() else 0
    return [
        f"- images 파일 수(대표 확장자): {image_count}",
        f"- logs/*.jsonl 파일 수: {log_jsonl_count}",
    ]


def run_audit(report_path: Path) -> int:
    checks = list(_iter_asset_checks())
    missing_assets = [c for c in checks if not c.exists]
    gate_block, gate_fresh = _format_gate_status()
    docs_table, missing_docs, docs_out_of_sync = _format_docs_mtime_table()
    test_file_count = _count_test_files()
    gate_exists = _resolve_gate_file() is not None
    resource_lines = _resource_snapshot()

    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# 🔍 Project Governance Audit Report ({now})")
    lines.append("")
    lines.append("## 1) Verification Health")
    lines.append(f"- 총 테스트 파일 수: {test_file_count}개")
    lines.append(f"- Gate 상태: {'PASS' if gate_exists else 'MISSING'}")
    lines.append("")
    lines.append("## 2) Asset Integrity Matrix")
    lines.append("| Group | Path | Status |")
    lines.append("| :--- | :--- | :--- |")
    for check in checks:
        status = "✅" if check.exists else "❌"
        lines.append(f"| {check.group} | `{check.path}` | {status} |")
    lines.append("")
    lines.append("## 3) Gate Freshness")
    lines.append(gate_block)
    lines.append("")
    lines.append("## 4) Resource Snapshot")
    lines.extend(resource_lines)
    lines.append("")
    lines.append("## 5) Docs Sync Health")
    lines.append("| Path | Exists | Last Modified |")
    lines.append("| :--- | :--- | :--- |")
    lines.append(docs_table)
    lines.append("")
    lines.append("## 6) Maintenance Guide")
    lines.append("- [ ] `task_finish.py`를 통한 문서 동기화 여부 확인")
    lines.append("- [ ] 30분 초과 stale gate 재실행 여부 점검")
    lines.append("- [ ] 누락 자산 발생 시 ASSET_MAP와 실제 경로 동시 갱신")
    lines.append("")
    lines.append("## 7) Maintenance Checklist")
    lines.append(f"- [{'x' if gate_fresh else ' '}] Gate TTL(30m) fresh")
    lines.append(f"- [{' ' if docs_out_of_sync else 'x'}] Doc mtimes reasonably aligned (<=1h gap)")
    lines.append(f"- [{' ' if missing_assets else 'x'}] Required assets present")
    lines.append("")
    if missing_assets:
        lines.append("## Missing Assets")
        for item in missing_assets:
            lines.append(f"- `{item.path}`")
        lines.append("")
    if missing_docs:
        lines.append("## Missing Docs")
        for item in missing_docs:
            lines.append(f"- `{item}`")
        lines.append("")

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[audit] report written: {report_path}")
    if missing_assets:
        print(f"[audit] missing assets: {len(missing_assets)}")
    if docs_out_of_sync:
        print("[audit] warning: docs modified-time gap exceeds 1 hour")
    if not gate_fresh:
        print("[audit] warning: post-task gate is stale or unavailable")
    return 1 if missing_assets else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project governance asset audit")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="output report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = Path(os.path.expanduser(os.path.expandvars(str(args.report)))).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    return run_audit(report_path)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


class BundleInfo:
    def __init__(self, project: str, path: Path, manifest: dict):
        self.project = project
        self.path = path
        self.manifest = manifest


def _load_bundles(inbox_root: Path) -> list[BundleInfo]:
    bundles: list[BundleInfo] = []
    if not inbox_root.exists():
        return bundles
    for project_dir in sorted(p for p in inbox_root.iterdir() if p.is_dir()):
        for bundle_dir in sorted(p for p in project_dir.iterdir() if p.is_dir()):
            manifest_path = bundle_dir / "feedback_manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
            bundles.append(BundleInfo(project=project_dir.name, path=bundle_dir, manifest=manifest))
    return bundles


def _copy_reusable_changes(bundle: BundleInfo, repo_root: Path) -> list[str]:
    copied: list[str] = []
    reusable_dir = bundle.path / "reusable_changes"
    if not reusable_dir.exists():
        return copied
    for src in reusable_dir.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(reusable_dir)
        dst = repo_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(rel).replace("\\", "/"))
    return copied


def _append_lessons_snapshot(bundle: BundleInfo, repo_root: Path) -> bool:
    lessons_snapshot = bundle.path / "LESSONS_LEARNED.md"
    if not lessons_snapshot.exists():
        return False
    target = repo_root / "docs" / "LESSONS_LEARNED_DRAFT.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = lessons_snapshot.read_text(encoding="utf-8", errors="ignore").strip()
    section = (
        f"\n## Imported Feedback - {bundle.project}/{bundle.path.name}\n"
        f"- imported_at: {datetime.now().isoformat(timespec='seconds')}\n\n"
        f"{content}\n"
    )
    with target.open("a", encoding="utf-8") as fp:
        fp.write(section)
    return True


def _move_processed(bundle: BundleInfo, processed_root: Path) -> Path:
    dst = processed_root / bundle.project / bundle.path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(bundle.path), str(dst))
    return dst


def _write_report(path: Path, bundles: list[BundleInfo], actions: list[str]) -> None:
    lines: list[str] = []
    lines.append(f"# Feedback Promotion Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    lines.append("")
    lines.append(f"- bundles_found: {len(bundles)}")
    lines.append("")
    lines.append("## Bundles")
    for bundle in bundles:
        changed = bundle.manifest.get("changed_files_count", 0)
        reusable = bundle.manifest.get("reusable_changes_count", 0)
        lines.append(f"- `{bundle.project}/{bundle.path.name}` (changed={changed}, reusable={reusable})")
    lines.append("")
    lines.append("## Actions")
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- no apply actions (dry-run)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote feedback bundles from inbox into DX assets.")
    parser.add_argument("--repo-root", default=".", help="Central DX repo root.")
    parser.add_argument("--inbox-root", default="feedback/inbox")
    parser.add_argument("--processed-root", default="feedback/processed")
    parser.add_argument("--report", default="feedback/promotion_report_latest.md")
    parser.add_argument("--apply", action="store_true", help="Apply promotion actions and move bundles to processed.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    inbox_root = repo_root / args.inbox_root
    processed_root = repo_root / args.processed_root
    report_path = repo_root / args.report

    bundles = _load_bundles(inbox_root)
    actions: list[str] = []
    if args.apply:
        for bundle in bundles:
            copied = _copy_reusable_changes(bundle, repo_root)
            if copied:
                actions.append(f"{bundle.project}/{bundle.path.name}: reusable promoted ({len(copied)} files)")
            lessons = _append_lessons_snapshot(bundle, repo_root)
            if lessons:
                actions.append(f"{bundle.project}/{bundle.path.name}: lessons draft appended")
            moved = _move_processed(bundle, processed_root)
            actions.append(f"{bundle.project}/{bundle.path.name}: moved to {moved.relative_to(repo_root)}")

    _write_report(report_path, bundles, actions)
    print(f"[ok] promotion report written: {report_path}")
    if args.apply:
        print(f"[ok] apply completed: {len(actions)} actions")
    else:
        print("[info] dry-run mode (use --apply to promote and move bundles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

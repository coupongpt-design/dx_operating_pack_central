from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


INSIGHT_CANDIDATES = (
    Path("feedback/LATEST_INSIGHT.yaml"),
    Path("dx_operating_pack/feedback/LATEST_INSIGHT.yaml"),
)
LESSONS_CANDIDATES = (
    Path("docs/LESSONS_LEARNED.md"),
    Path("docs/dx_pack/LESSONS_LEARNED.md"),
    Path("dx_operating_pack/docs/LESSONS_LEARNED.md"),
)
OUTBOX_CANDIDATES = (
    Path("feedback/outbox"),
    Path("dx_operating_pack/feedback/outbox"),
)


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, ((completed.stdout or "") + (completed.stderr or "")).strip()


def _changed_files(base: str, head: str) -> list[str]:
    rc, out = _run(["git", "diff", "--name-only", f"{base}..{head}"])
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _detect_reusable_changes(files: list[str]) -> list[str]:
    reusable: list[str] = []
    for file in files:
        norm = file.replace("\\", "/")
        if norm.startswith("reusable/") or "/reusable/" in norm:
            reusable.append(norm)
    return sorted(dict.fromkeys(reusable))


def _resolve_existing(candidates: tuple[Path, ...]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_outbox(candidates: tuple[Path, ...]) -> Path:
    for candidate in candidates:
        if candidate.parent.exists() or candidate.exists():
            return candidate
    return candidates[0]


def _safe_name(raw: str) -> str:
    keep = []
    for ch in raw:
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "project"


def build_feedback_bundle(
    *,
    project_name: str,
    base: str,
    head: str,
    changed_files: list[str],
    insight_path: Path | None,
    lessons_path: Path | None,
    outbox_root: Path,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_head = head[:8].replace("/", "_")
    bundle = outbox_root / f"{stamp}_{short_head}"
    bundle.mkdir(parents=True, exist_ok=True)

    reusable_changes = _detect_reusable_changes(changed_files)
    metadata = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_name": project_name,
        "base": base,
        "head": head,
        "changed_files_count": len(changed_files),
        "reusable_changes_count": len(reusable_changes),
        "changed_files": changed_files,
        "reusable_changes": reusable_changes,
    }
    (bundle / "feedback_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if insight_path and insight_path.exists():
        shutil.copy2(insight_path, bundle / "LATEST_INSIGHT.yaml")
    if lessons_path and lessons_path.exists():
        shutil.copy2(lessons_path, bundle / "LESSONS_LEARNED.md")

    for rel in reusable_changes:
        src = Path(rel)
        if not src.exists() or not src.is_file():
            continue
        dst = bundle / "reusable_changes" / rel.replace("\\", "/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return bundle


def _acquire_remote(remote_url: str, cache_dir: Path) -> Path | None:
    cache_dir = cache_dir.resolve()
    if (cache_dir / ".git").exists():
        _run(["git", "-C", str(cache_dir), "remote", "set-url", "origin", remote_url])
        rc, out = _run(["git", "-C", str(cache_dir), "pull", "--ff-only"])
        if rc != 0:
            print(f"[fail] remote pull failed: {out}")
            return None
        return cache_dir

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    rc, out = _run(["git", "clone", remote_url, str(cache_dir)])
    if rc != 0:
        print(f"[fail] remote clone failed: {out}")
        return None
    return cache_dir


def _publish_bundle(
    *,
    remote_repo: Path,
    bundle: Path,
    inbox_subdir: str,
    project_name: str,
    push: bool,
) -> int:
    project_name_safe = _safe_name(project_name)
    dst = remote_repo / inbox_subdir / project_name_safe / bundle.name
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle, dst)

    rc, out = _run(["git", "-C", str(remote_repo), "add", str(dst.relative_to(remote_repo))])
    if rc != 0:
        print(f"[fail] git add failed: {out}")
        return 1

    rc, out = _run(["git", "-C", str(remote_repo), "status", "--porcelain"])
    if rc != 0:
        print(f"[fail] git status failed: {out}")
        return 1
    if not out.strip():
        print("[ok] no remote changes to commit")
        return 0

    subject = f"feedback({project_name_safe}): ingest {bundle.name}"
    rc, out = _run(["git", "-C", str(remote_repo), "commit", "-m", subject])
    if rc != 0:
        print(f"[fail] git commit failed: {out}")
        return 1
    print(f"[ok] remote commit created: {subject}")

    if not push:
        print("[info] push skipped (use --push to publish to origin)")
        return 0

    rc, out = _run(["git", "-C", str(remote_repo), "push", "origin"])
    if rc != 0:
        print(f"[fail] git push failed: {out}")
        return 1
    print("[ok] remote push completed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Package and publish DX feedback bundle.")
    parser.add_argument("--base", default="HEAD~1")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--project-name", default="", help="Logical project name for inbox grouping.")
    parser.add_argument("--remote-url", default="", help="Central DX repo URL/path. If omitted, local bundle only.")
    parser.add_argument("--cache-dir", default=".dx_cache/dx_feedback_remote")
    parser.add_argument("--inbox-subdir", default="inbox")
    parser.add_argument("--push", action="store_true", help="Push commit to origin after publishing bundle.")
    parser.add_argument("--insight", default="", help="Insight YAML path override.")
    parser.add_argument("--lessons", default="", help="Lessons markdown path override.")
    parser.add_argument("--outbox-root", default="", help="Outbox root override.")
    args = parser.parse_args()

    project_name = args.project_name.strip() or Path.cwd().name
    changed_files = _changed_files(args.base, args.head)

    insight_path = Path(args.insight) if args.insight else _resolve_existing(INSIGHT_CANDIDATES)
    lessons_path = Path(args.lessons) if args.lessons else _resolve_existing(LESSONS_CANDIDATES)
    outbox_root = Path(args.outbox_root) if args.outbox_root else _resolve_outbox(OUTBOX_CANDIDATES)
    outbox_root.mkdir(parents=True, exist_ok=True)

    bundle = build_feedback_bundle(
        project_name=project_name,
        base=args.base,
        head=args.head,
        changed_files=changed_files,
        insight_path=insight_path,
        lessons_path=lessons_path,
        outbox_root=outbox_root,
    )
    print(f"[ok] feedback bundle created: {bundle}")

    if not args.remote_url.strip():
        print("[info] remote-url not provided; local outbox export only")
        return 0

    remote_repo = _acquire_remote(args.remote_url.strip(), Path(args.cache_dir))
    if not remote_repo:
        return 1
    return _publish_bundle(
        remote_repo=remote_repo,
        bundle=bundle,
        inbox_subdir=args.inbox_subdir.strip("/"),
        project_name=project_name,
        push=args.push,
    )


if __name__ == "__main__":
    raise SystemExit(main())

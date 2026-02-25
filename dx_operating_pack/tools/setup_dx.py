from __future__ import annotations

import argparse
import shutil
from pathlib import Path


# (source_rel, target_rel) mapping inside/new project root.
INSTALL_MAP: list[tuple[str, str]] = [
    ("rules/AGENTS.md", "AGENTS.md"),
    ("rules/.cursorrules", ".cursorrules"),
    ("hooks", ".githooks"),
    ("tools", "tools"),
    ("ci", ".github/workflows"),
    ("tests", "tests"),
    ("docs", "docs/dx_pack"),
    ("docs_for_ai", "docs_for_ai"),
    ("prompt_recipes", "PROMPT_RECIPES"),
    (".cursor/prompts", ".cursor/prompts"),
    ("COMPLIANCE_GUIDE.md", "COMPLIANCE_GUIDE.md"),
]


def _safe_remove(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _copy_or_link(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        if src.is_dir():
            dst.symlink_to(src, target_is_directory=True)
        else:
            dst.symlink_to(src)
        return

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def install(pack_root: Path, target_root: Path, mode: str, overwrite: bool) -> list[str]:
    installed: list[str] = []
    for src_rel, dst_rel in INSTALL_MAP:
        src = pack_root / src_rel
        dst = target_root / dst_rel
        if not src.exists():
            continue

        if dst.exists() or dst.is_symlink():
            if not overwrite:
                installed.append(f"[skip] {dst_rel} (exists)")
                continue
            _safe_remove(dst)

        _copy_or_link(src=src, dst=dst, mode=mode)
        installed.append(f"[ok] {src_rel} -> {dst_rel}")
    return installed


def main() -> int:
    parser = argparse.ArgumentParser(description="Install DX operating pack into another project.")
    parser.add_argument(
        "--pack-root",
        default="dx_operating_pack",
        help="Path to dx_operating_pack root.",
    )
    parser.add_argument(
        "--target-root",
        default=".",
        help="Path to destination project root.",
    )
    parser.add_argument(
        "--mode",
        choices=("copy", "symlink"),
        default="copy",
        help="Install mode: copy files or create symlinks.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing target files/directories.",
    )
    args = parser.parse_args()

    pack_root = Path(args.pack_root).resolve()
    target_root = Path(args.target_root).resolve()
    if not pack_root.exists():
        print(f"[fail] pack root not found: {pack_root}")
        return 1

    logs = install(pack_root=pack_root, target_root=target_root, mode=args.mode, overwrite=args.overwrite)
    print(f"[done] mode={args.mode}, overwrite={args.overwrite}, target={target_root}")
    for line in logs:
        print(line)
    print("[next] run: python tools/install_git_hooks.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


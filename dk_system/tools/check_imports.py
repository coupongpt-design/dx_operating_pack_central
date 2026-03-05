#!/usr/bin/env python
"""
Import 검토 스크립트.

프로젝트 레이아웃을 감지해 import 대상 모듈 목록을 자동 선택한다.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_LAYOUT_MODULES = [
    "app.main",
    "app.core.models",
    "app.core.runner",
    "app.core.recorder",
    "app.ui.dialogs",
    "app.ui.widgets",
    "app.ui.selectors",
    "app.ui.hotkeys",
    "app.utils.common",
    "app.utils.matcher",
    "app.io.csv_loader",
]

ROOT_LAYOUT_MODULES = [
    "macro.config",
    "macro.utils",
    "macro.data_handler",
    "macro.data_analyzer",
    "macro.job_tracker",
    "macro.notifier",
    "macro.pdf_generator",
    "macro.browser_manager",
    "macro.browser_pool",
    "macro.dashboard",
    "google_messages",
    "macro.version",
]


def _detect_modules(project_root: Path) -> list[str]:
    if (project_root / "app").is_dir():
        return APP_LAYOUT_MODULES
    return ROOT_LAYOUT_MODULES


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

    modules_to_check = _detect_modules(project_root)
    errors: list[tuple[str, str]] = []

    for module_name in modules_to_check:
        try:
            print(f"Checking {module_name}...", end=" ")
            importlib.import_module(module_name)
            print("OK")
        except Exception as exc:
            print(f"ERROR: {exc}")
            errors.append((module_name, str(exc)))

    if errors:
        print("\n=== Import Errors Found ===")
        for module, error in errors:
            print(f"{module}: {error}")
        return 1

    print("\n=== All imports OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from tools import check_imports


def test_detect_modules_returns_root_layout_without_app_dir(tmp_path) -> None:
    assert check_imports._detect_modules(tmp_path) == check_imports.ROOT_LAYOUT_MODULES


def test_detect_modules_returns_app_layout_with_app_dir(tmp_path) -> None:
    (tmp_path / "app").mkdir()
    assert check_imports._detect_modules(tmp_path) == check_imports.APP_LAYOUT_MODULES

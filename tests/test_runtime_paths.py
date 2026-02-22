import os
from pathlib import Path


def test_get_resource_path_points_to_repo_resource():
    from app.utils.runtime_paths import get_resource_path

    path = get_resource_path("app/core/scenario_wizard_templates.json")
    assert Path(path).exists()


def test_get_writable_app_dir_env_override(tmp_path, monkeypatch):
    from app.utils.runtime_paths import get_writable_app_dir

    target = tmp_path / "custom_appdata"
    monkeypatch.setenv("IMAGEMACRO_DATA_DIR", str(target))
    got = get_writable_app_dir()
    assert got == target
    assert got.exists()

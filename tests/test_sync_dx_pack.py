from argparse import Namespace
from pathlib import Path


def test_acquire_remote_existing_cache_syncs_requested_branch(monkeypatch, tmp_path):
    import dx_operating_pack.tools.sync_dx_pack as sync_mod

    cache_dir = tmp_path / "cache"
    (cache_dir / ".git").mkdir(parents=True)
    calls = []

    def fake_run(cmd, cwd=None):
        calls.append((cmd, cwd))
        return 0

    monkeypatch.setattr(sync_mod, "_run", fake_run)

    result = sync_mod._acquire_remote(
        "git@github.com:coupongpt-design/dx_operating_pack_central.git",
        cache_dir,
        remote_branch="feature/ui-modernization-v1",
    )

    assert result == cache_dir
    assert calls[0][0] == ["git", "-C", str(cache_dir), "remote", "set-url", "origin", "git@github.com:coupongpt-design/dx_operating_pack_central.git"]
    assert calls[1][0] == ["git", "-C", str(cache_dir), "fetch", "origin", "feature/ui-modernization-v1"]
    assert calls[2][0] == ["git", "-C", str(cache_dir), "checkout", "feature/ui-modernization-v1"]
    assert calls[3][0] == [
        "git",
        "-C",
        str(cache_dir),
        "pull",
        "--ff-only",
        "origin",
        "feature/ui-modernization-v1",
    ]


def test_acquire_remote_new_clone_uses_single_branch(monkeypatch, tmp_path):
    import dx_operating_pack.tools.sync_dx_pack as sync_mod

    cache_dir = tmp_path / "cache"
    calls = []

    def fake_run(cmd, cwd=None):
        calls.append((cmd, cwd))
        return 0

    monkeypatch.setattr(sync_mod, "_run", fake_run)

    result = sync_mod._acquire_remote(
        "git@github.com:coupongpt-design/dx_operating_pack_central.git",
        cache_dir,
        remote_branch="feature/ui-modernization-v1",
    )

    assert result == cache_dir
    assert calls == [
        (
            [
                "git",
                "clone",
                "--branch",
                "feature/ui-modernization-v1",
                "--single-branch",
                "git@github.com:coupongpt-design/dx_operating_pack_central.git",
                str(cache_dir),
            ],
            None,
        )
    ]


def test_resolve_pack_repo_syncs_local_shared_repo_branch(monkeypatch, tmp_path):
    import dx_operating_pack.tools.sync_dx_pack as sync_mod

    pack_repo = tmp_path / "pack"
    pack_repo.mkdir()
    calls = []

    def fake_run(cmd, cwd=None):
        calls.append((cmd, cwd))
        return 0

    monkeypatch.setattr(sync_mod, "_run", fake_run)

    args = Namespace(
        remote_url="",
        remote_branch="feature/ui-modernization-v1",
        cache_dir=".dx_cache/dx_operating_pack_remote",
        pack_repo=str(pack_repo),
    )

    result = sync_mod._resolve_pack_repo(args=args, project_root=tmp_path)

    assert result == pack_repo
    assert calls == [
        (["git", "-C", str(pack_repo), "fetch", "origin", "feature/ui-modernization-v1"], None),
        (["git", "-C", str(pack_repo), "checkout", "feature/ui-modernization-v1"], None),
        (
            ["git", "-C", str(pack_repo), "pull", "--ff-only", "origin", "feature/ui-modernization-v1"],
            None,
        ),
    ]

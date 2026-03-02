from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "transplant_full_system.py"


def _write(path: Path, content: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prepare_min_source(source_root: Path) -> None:
    (source_root / "dx_operating_pack").mkdir(parents=True, exist_ok=True)
    (source_root / "dx_operating_pack" / "hooks").mkdir(parents=True, exist_ok=True)
    (source_root / "dx_operating_pack" / "rules").mkdir(parents=True, exist_ok=True)
    (source_root / "dx_operating_pack" / "templates").mkdir(parents=True, exist_ok=True)
    (source_root / "dx_operating_pack" / "tests").mkdir(parents=True, exist_ok=True)
    (source_root / "tools").mkdir(parents=True, exist_ok=True)
    (source_root / "docs_for_ai").mkdir(parents=True, exist_ok=True)
    _write(source_root / "AGENTS.md", "agents\n")
    _write(source_root / "pytest.ini", "[pytest]\n")
    _write(source_root / "requirements-dev.txt", "pytest\n")
    _write(source_root / "run_health_check.py", "print('ok')\n")
    _write(source_root / "tools" / "check_tool_integrity.py", "print('integrity')\n")
    _write(source_root / "dx_operating_pack" / "README.md", "pack\n")
    _write(source_root / "dx_operating_pack" / "hooks" / "pre-commit", "#!/bin/sh\n")
    _write(source_root / "dx_operating_pack" / "hooks" / "commit-msg", "#!/bin/sh\n")
    _write(
        source_root / "dx_operating_pack" / "hooks" / "pre-push",
        (
            "#!/bin/sh\n"
            "python -m pytest -q "
            "tests/test_rule_docs_sync.py "
            "tests/test_rule_guard_steps_mutation.py "
            "tests/test_git_hook_guards.py "
            "tests/test_test_selector.py "
            "tests/test_task_finish.py "
            "tests/test_post_task_gate.py "
            "tests/test_ci_governance_guard.py\n"
        ),
    )
    _write(source_root / "dx_operating_pack" / "rules" / ".cursorrules", "canonical-rules\n")
    _write(source_root / "dx_operating_pack" / "templates" / "DEV_LOG.template.md", "# devlog\n")
    _write(
        source_root / "dx_operating_pack" / "templates" / "PROJECT_STATUS.template.md",
        "# project-status\n",
    )
    _write(source_root / "dx_operating_pack" / "templates" / "now_spec.template.md", "# now-spec\n")
    for name in (
        "test_rule_docs_sync.py",
        "test_rule_guard_steps_mutation.py",
        "test_git_hook_guards.py",
        "test_test_selector.py",
        "test_task_finish.py",
        "test_post_task_gate.py",
        "test_ci_governance_guard.py",
    ):
        _write(
            source_root / "dx_operating_pack" / "tests" / name,
            "def test_stub():\n    assert True\n",
        )


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_dry_run_does_not_modify_target(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    _prepare_min_source(source_root)

    completed = _run(
        "--source-root",
        str(source_root),
        "--target-root",
        str(target_root),
        "--dry-run",
        "--skip-verify",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "[done] dry-run finished" in completed.stdout
    assert not (target_root / "dx_operating_pack").exists()


def test_overwrite_creates_backup_and_replaces_files(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    _prepare_min_source(source_root)
    _write(source_root / "AGENTS.md", "new-agents\n")

    _write(target_root / "AGENTS.md", "old-agents\n")
    _write(target_root / "pytest.ini", "old\n")

    completed = _run(
        "--source-root",
        str(source_root),
        "--target-root",
        str(target_root),
        "--overwrite",
        "--skip-verify",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (target_root / "AGENTS.md").read_text(encoding="utf-8") == "new-agents\n"

    backup_parent = target_root / ".dx_cache" / "transplant_backup"
    backups = [p for p in backup_parent.iterdir() if p.is_dir()]
    assert backups, "backup directory not created"
    backup_agents = backups[0] / "AGENTS.md"
    assert backup_agents.exists()
    assert backup_agents.read_text(encoding="utf-8") == "old-agents\n"


def test_transplant_bootstraps_state_docs_and_governance_bridges(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    _prepare_min_source(source_root)

    _write(target_root / ".cursorrules", "legacy-rule\n")
    _write(target_root / "rule.md", "legacy-rule-md\n")
    _write(target_root / "tests" / "test_rule_docs_sync.py", "def test_old():\n    assert True\n")

    completed = _run(
        "--source-root",
        str(source_root),
        "--target-root",
        str(target_root),
        "--overwrite",
        "--skip-verify",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (target_root / "PROJECT_STATUS.md").exists()
    assert (target_root / "now_spec.md").exists()
    assert (target_root / "DEV_LOG.md").exists()
    assert (target_root / ".cursorrules").read_text(encoding="utf-8") == "canonical-rules\n"
    assert not (target_root / "rule.md").exists()

    bridge = (target_root / "tests" / "test_rule_docs_sync.py").read_text(encoding="utf-8")
    assert "dx_operating_pack.tests.test_rule_docs_sync" in bridge
    assert (target_root / "rules" / "AGENTS.md").read_text(encoding="utf-8") == "agents\n"

    archived = list((target_root / "archive" / "legacy_rules").rglob("*.md"))
    assert archived, "legacy rule files must be archived"

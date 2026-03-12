import json
import json
from argparse import Namespace
from pathlib import Path
import subprocess

import pytest

from app.core.multi_role_ai import (
    GeminiCliRoleBackend,
    MultiRoleAIOrchestrator,
    OrchestrationResult,
    RoleDefinition,
    RoleTurn,
    SelectiveRoleBackend,
    load_roles_from_json,
    render_result_markdown,
)


class RecordingBackend:
    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, role, prompt, *, max_output_chars):
        self.prompts.append(prompt)
        return f"{role.role_id} response"


def test_multi_role_ai_compact_default_chain():
    orchestrator = MultiRoleAIOrchestrator()
    result = orchestrator.run(task="매크로 저장 오류 수정", mode="compact")

    assert result.mode == "compact"
    assert result.role_ids == ["planner", "implementer", "reviewer"]
    assert [turn.role_id for turn in result.turns] == result.role_ids
    assert all(turn.response for turn in result.turns)


def test_multi_role_ai_auto_switches_to_precision():
    orchestrator = MultiRoleAIOrchestrator()
    result = orchestrator.run(task="대규모 아키텍처 리팩터 및 회귀 테스트 계획", mode="auto")

    assert result.mode == "precision"
    assert len(result.turns) == 5
    assert result.role_ids == ["planner", "implementer", "reviewer", "tester", "documenter"]


def test_multi_role_ai_auto_switches_to_precision_on_changed_files_threshold():
    orchestrator = MultiRoleAIOrchestrator()
    result = orchestrator.run(
        task="작업",
        mode="auto",
        changed_files=["a.py", "b.py", "c.py", "d.py", "e.py"],
    )
    assert result.mode == "precision"


def test_multi_role_ai_auto_switches_to_precision_on_risk_files():
    orchestrator = MultiRoleAIOrchestrator()
    result = orchestrator.run(
        task="작업",
        mode="auto",
        changed_files=["app/core/runner.py"],
    )
    assert result.mode == "precision"


def test_multi_role_ai_raises_for_unknown_role():
    orchestrator = MultiRoleAIOrchestrator()
    with pytest.raises(ValueError):
        orchestrator.run(task="task", role_ids=["planner", "unknown"])


def test_multi_role_ai_prompt_contains_context_truncation_marker():
    backend = RecordingBackend()
    orchestrator = MultiRoleAIOrchestrator(backend=backend, max_context_chars=80)
    orchestrator.run(task="작업", context=("x" * 600), mode="compact")

    assert backend.prompts
    assert "[context truncated; tail only]" in backend.prompts[0]


def test_load_roles_from_json_and_run(tmp_path):
    path = tmp_path / "roles.json"
    payload = {
        "schema_version": 1,
        "roles": [
            {
                "role_id": "planner",
                "title": "Planner",
                "objective": "plan",
                "guidance": "return bullets",
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    roles = load_roles_from_json(path)
    orchestrator = MultiRoleAIOrchestrator(roles=roles)
    result = orchestrator.run(task="단일 역할 실행", role_ids=["planner"])

    assert len(roles) == 1
    assert result.role_ids == ["planner"]
    assert result.turns[0].role_id == "planner"


def test_custom_roles_run_without_explicit_role_ids(tmp_path):
    path = tmp_path / "roles_custom.json"
    payload = {
        "schema_version": 1,
        "roles": [
            {
                "role_id": "architect",
                "title": "Architect",
                "objective": "design",
                "guidance": "show architecture decisions",
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    roles = load_roles_from_json(path)
    orchestrator = MultiRoleAIOrchestrator(roles=roles)
    result = orchestrator.run(task="커스텀 실행", mode="auto")
    assert result.role_ids == ["architect"]


def test_render_result_markdown_includes_roles():
    result = OrchestrationResult(
        task="테스트",
        context="",
        mode="compact",
        role_ids=["planner"],
        turns=[RoleTurn(role_id="planner", title="Planner", prompt="p", response="done")],
        summary="ok",
    )
    text = render_result_markdown(result)
    assert "Multi-Role AI Result" in text
    assert "Planner (planner)" in text
    assert "done" in text


def test_load_roles_from_json_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "roles_bad.json"
    payload = {
        "schema_version": 1,
        "roles": [
            {
                "role_id": "planner",
                "title": "Planner",
                "objective": "a",
                "guidance": "b",
            },
            {
                "role_id": "planner",
                "title": "Planner2",
                "objective": "c",
                "guidance": "d",
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError):
        load_roles_from_json(path)


def test_multi_role_ai_accepts_custom_role_definition():
    roles = [
        RoleDefinition(
            role_id="architect",
            title="Architect",
            objective="design",
            guidance="produce architecture notes",
        )
    ]
    orchestrator = MultiRoleAIOrchestrator(roles=roles)
    result = orchestrator.run(task="설계", role_ids=["architect"])
    assert result.role_ids == ["architect"]
    assert result.turns[0].title == "Architect"


def test_multi_role_ai_rejects_empty_roles():
    with pytest.raises(ValueError):
        MultiRoleAIOrchestrator(roles=[])


def test_run_multi_role_ai_hard_gate_blocks_on_guardian_fail(monkeypatch, tmp_path):
    import tools.run_multi_role_ai as cli
    ctx = cli.main.__globals__

    class FakeOrchestrator:
        def __init__(self, backend=None, roles=None):
            self.backend = backend
            self.roles = roles

        def select_mode(self, task, context="", changed_files=None):
            return "precision"

        def run(self, **kwargs):
            return OrchestrationResult(
                task="t",
                context="",
                mode="precision",
                role_ids=["planner", "implementer", "reviewer"],
                turns=[
                    RoleTurn(role_id="planner", title="Planner", prompt="p", response="plan"),
                    RoleTurn(role_id="implementer", title="Implementer", prompt="p", response="impl"),
                    RoleTurn(role_id="reviewer", title="Reviewer", prompt="p", response='{"is_approved": false}'),
                ],
                summary="s",
            )

    rollback_called = {}

    def fake_rollback(_baseline):
        rollback_called["called"] = True
        return {"attempted": True, "targets": ["x.py"], "rolled_back": ["x.py"], "failed": []}

    monkeypatch.setitem(ctx, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setitem(ctx, "MultiRoleAIOrchestrator", FakeOrchestrator)
    monkeypatch.setitem(ctx, "parse_args", lambda: Namespace(
        task="task",
        context="ctx",
        mode="auto",
        roles="",
        roles_file="",
        format="json",
        changed_file=[],
        backend="heuristic",
        gemini_command="gemini",
        gemini_model="",
        gemini_extra_arg=[],
        gemini_timeout_sec=180,
    ))
    monkeypatch.setitem(ctx, "_collect_git_state", lambda: {"tracked": set(), "untracked": set()})
    monkeypatch.setitem(ctx, "_safe_git_diff", lambda: "")
    monkeypatch.setitem(ctx, "_auto_rollback_changes", fake_rollback)

    rc = cli.main()
    assert rc == 1
    assert rollback_called.get("called") is True

    base = tmp_path / "logs" / "ai_sessions"
    dirs = sorted(base.glob("*"))
    assert dirs
    artifact_dir = dirs[-1]
    assert (artifact_dir / "planner_plan.md").exists()
    assert (artifact_dir / "executor_diff.json").exists()
    assert (artifact_dir / "guardian_report.json").exists()


def test_gemini_cli_backend_returns_stdout(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert Path(cmd[0]).name.lower() in {"gemini", "gemini.cmd", "gemini.exe", "gemini.bat"}
        assert cmd[1] == "-p"
        return subprocess.CompletedProcess(cmd, 0, stdout="planner answer", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = GeminiCliRoleBackend()
    text = backend.generate(
        RoleDefinition("planner", "Planner", "plan", "guidance"),
        "TASK:\nhello",
        max_output_chars=400,
    )
    assert text == "planner answer"


def test_gemini_cli_backend_raises_when_missing():
    backend = GeminiCliRoleBackend(command="missing-gemini")
    with pytest.raises(RuntimeError):
        backend.generate(
            RoleDefinition("planner", "Planner", "plan", "guidance"),
            "TASK:\nhello",
            max_output_chars=400,
        )


def test_selective_role_backend_routes_selected_roles():
    calls = []

    class RecordingBackend:
        def __init__(self, name):
            self.name = name

        def generate(self, role, prompt, *, max_output_chars):
            calls.append((self.name, role.role_id, max_output_chars))
            return f"{self.name}:{role.role_id}"

    default_backend = RecordingBackend("heuristic")
    gemini_backend = RecordingBackend("gemini")
    backend = SelectiveRoleBackend(
        default_backend=default_backend,
        routed_backends={"planner": gemini_backend},
        fallback_backend=default_backend,
    )

    planner_text = backend.generate(
        RoleDefinition("planner", "Planner", "plan", "guidance"),
        "TASK:\nhello",
        max_output_chars=300,
    )
    implementer_text = backend.generate(
        RoleDefinition("implementer", "Implementer", "do", "guidance"),
        "TASK:\nhello",
        max_output_chars=300,
    )

    assert planner_text == "gemini:planner"
    assert implementer_text == "heuristic:implementer"
    assert calls == [
        ("gemini", "planner", 300),
        ("heuristic", "implementer", 300),
    ]


def test_selective_role_backend_falls_back_on_runtime_error():
    calls = []

    class FailingBackend:
        def generate(self, role, prompt, *, max_output_chars):
            calls.append(("gemini", role.role_id))
            raise RuntimeError("gemini unavailable")

    class RecordingBackend:
        def generate(self, role, prompt, *, max_output_chars):
            calls.append(("heuristic", role.role_id))
            return f"fallback:{role.role_id}"

    default_backend = RecordingBackend()
    backend = SelectiveRoleBackend(
        default_backend=default_backend,
        routed_backends={"planner": FailingBackend()},
        fallback_backend=default_backend,
    )

    planner_text = backend.generate(
        RoleDefinition("planner", "Planner", "plan", "guidance"),
        "TASK:\nhello",
        max_output_chars=300,
    )

    assert planner_text == "fallback:planner"
    assert calls == [("gemini", "planner"), ("heuristic", "planner")]


def test_run_multi_role_ai_builds_gemini_backend(monkeypatch, tmp_path):
    import tools.run_multi_role_ai as cli
    ctx = cli.main.__globals__

    captured = {}

    class FakeGeminiBackend:
        def __init__(self, **kwargs):
            captured["backend_kwargs"] = kwargs

    class FakeOrchestrator:
        def __init__(self, backend=None, roles=None):
            captured["backend_type"] = type(backend).__name__
            self.backend = backend
            self.roles = roles

        def run(self, **kwargs):
            return OrchestrationResult(
                task="t",
                context="",
                mode="compact",
                role_ids=["planner"],
                turns=[RoleTurn(role_id="planner", title="Planner", prompt="p", response="plan")],
                summary="s",
            )

    monkeypatch.setitem(ctx, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setitem(ctx, "GeminiCliRoleBackend", FakeGeminiBackend)
    monkeypatch.setitem(ctx, "MultiRoleAIOrchestrator", FakeOrchestrator)
    monkeypatch.setitem(ctx, "parse_args", lambda: Namespace(
        task="task",
        context="ctx",
        mode="compact",
        roles="",
        roles_file="",
        format="json",
        changed_file=[],
        backend="gemini-cli",
        gemini_command="gemini",
        gemini_model="gemini-2.5-pro",
        gemini_extra_arg=["--yolo"],
        gemini_timeout_sec=90,
    ))
    monkeypatch.setitem(ctx, "_collect_git_state", lambda: {"tracked": set(), "untracked": set()})
    monkeypatch.setitem(ctx, "_safe_git_diff", lambda: "")

    rc = cli.main()
    assert rc == 0
    assert captured["backend_type"] == "FakeGeminiBackend"
    assert captured["backend_kwargs"] == {
        "command": "gemini",
        "model": "gemini-2.5-pro",
        "extra_args": ["--yolo"],
        "timeout_sec": 90,
    }


def test_run_multi_role_ai_builds_semi_auto_backend_for_precision(monkeypatch, tmp_path):
    import tools.run_multi_role_ai as cli

    ctx = cli.main.__globals__
    captured = {}

    class FakeGeminiBackend:
        def __init__(self, **kwargs):
            captured["gemini_kwargs"] = kwargs

    class FakeHeuristicBackend:
        pass

    class FakeSelectiveBackend:
        def __init__(self, **kwargs):
            captured["selective_kwargs"] = kwargs

    class FakeOrchestrator:
        def __init__(self, backend=None, roles=None):
            captured.setdefault("backend_types", []).append(type(backend).__name__)
            self.backend = backend
            self.roles = roles

        def select_mode(self, task, context="", changed_files=None):
            captured["select_mode_changed_files"] = list(changed_files or [])
            return "precision"

        def run(self, **kwargs):
            captured["run_kwargs"] = kwargs
            return OrchestrationResult(
                task="t",
                context="",
                mode="precision",
                role_ids=["planner", "implementer", "reviewer"],
                turns=[RoleTurn(role_id="planner", title="Planner", prompt="p", response="plan")],
                summary="s",
            )

    monkeypatch.setitem(ctx, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setitem(ctx, "GeminiCliRoleBackend", FakeGeminiBackend)
    monkeypatch.setitem(ctx, "HeuristicRoleBackend", FakeHeuristicBackend)
    monkeypatch.setitem(ctx, "SelectiveRoleBackend", FakeSelectiveBackend)
    monkeypatch.setitem(ctx, "MultiRoleAIOrchestrator", FakeOrchestrator)
    monkeypatch.setitem(
        ctx,
        "parse_args",
        lambda: Namespace(
            task="task",
            context="ctx",
            mode="auto",
            roles="implementer",
            roles_file="",
            format="json",
            changed_file=["a.py", "b.py", "c.py", "d.py", "e.py"],
            backend="semi-auto",
            gemini_command="gemini",
            gemini_model="gemini-2.5-pro",
            gemini_extra_arg=["--yolo"],
            gemini_timeout_sec=90,
        ),
    )
    monkeypatch.setitem(ctx, "_collect_git_state", lambda: {"tracked": set(), "untracked": set()})
    monkeypatch.setitem(ctx, "_safe_git_diff", lambda: "")

    rc = cli.main()

    assert rc == 0
    assert captured["backend_types"][-1] == "FakeSelectiveBackend"
    assert captured["run_kwargs"]["role_ids"] == ["planner", "implementer", "reviewer"]
    assert captured["gemini_kwargs"] == {
        "command": "gemini",
        "model": "gemini-2.5-pro",
        "extra_args": ["--yolo"],
        "timeout_sec": 90,
    }
    assert sorted(captured["selective_kwargs"]["routed_backends"]) == [
        "guardian",
        "planner",
        "reviewer",
        "tester",
    ]


def test_run_multi_role_ai_semi_auto_stays_heuristic_in_compact_mode(monkeypatch, tmp_path):
    import tools.run_multi_role_ai as cli

    ctx = cli.main.__globals__
    captured = {}

    class FakeHeuristicBackend:
        pass

    class FakeOrchestrator:
        def __init__(self, backend=None, roles=None):
            captured.setdefault("backend_types", []).append(type(backend).__name__)
            self.backend = backend
            self.roles = roles

        def select_mode(self, task, context="", changed_files=None):
            return "compact"

        def run(self, **kwargs):
            captured["run_kwargs"] = kwargs
            return OrchestrationResult(
                task="t",
                context="",
                mode="compact",
                role_ids=["implementer"],
                turns=[RoleTurn(role_id="implementer", title="Implementer", prompt="p", response="impl")],
                summary="s",
            )

    monkeypatch.setitem(ctx, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setitem(ctx, "HeuristicRoleBackend", FakeHeuristicBackend)
    monkeypatch.setitem(ctx, "MultiRoleAIOrchestrator", FakeOrchestrator)
    monkeypatch.setitem(
        ctx,
        "parse_args",
        lambda: Namespace(
            task="task",
            context="ctx",
            mode="auto",
            roles="implementer",
            roles_file="",
            format="json",
            changed_file=["app/ui/main.py"],
            backend="semi-auto",
            gemini_command="gemini",
            gemini_model="",
            gemini_extra_arg=[],
            gemini_timeout_sec=90,
        ),
    )
    monkeypatch.setitem(ctx, "_collect_git_state", lambda: {"tracked": set(), "untracked": set()})
    monkeypatch.setitem(ctx, "_safe_git_diff", lambda: "")

    rc = cli.main()

    assert rc == 0
    assert captured["backend_types"][-1] == "FakeHeuristicBackend"
    assert captured["run_kwargs"]["role_ids"] == ["implementer"]


def test_run_multi_role_ai_root_points_to_project_root():
    import tools.run_multi_role_ai as cli

    root = cli.main.__globals__["PROJECT_ROOT"]
    assert (Path(root) / "app" / "core" / "multi_role_ai.py").exists()
    assert (Path(root) / "dx_operating_pack" / "reusable" / "core" / "multi_role_ai.py").exists()


def test_run_multi_role_ai_git_calls_use_utf8(monkeypatch):
    import tools.run_multi_role_ai as cli

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(cli.main.__globals__["subprocess"], "run", fake_run)
    cli.main.__globals__["_run_git"](["status", "--porcelain"])

    assert captured["cmd"][:2] == ["git", "status"]
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"

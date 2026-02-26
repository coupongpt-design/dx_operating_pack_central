import json
from argparse import Namespace

import pytest

from app.core.multi_role_ai import (
    MultiRoleAIOrchestrator,
    OrchestrationResult,
    RoleDefinition,
    RoleTurn,
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
        def __init__(self, roles=None):
            self.roles = roles

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

    monkeypatch.setitem(ctx, "ROOT", str(tmp_path))
    monkeypatch.setitem(ctx, "MultiRoleAIOrchestrator", FakeOrchestrator)
    monkeypatch.setitem(ctx, "parse_args", lambda: Namespace(
        task="task",
        context="ctx",
        mode="auto",
        roles="",
        roles_file="",
        format="json",
        changed_file=[],
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

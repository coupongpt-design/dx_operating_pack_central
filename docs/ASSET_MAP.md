# ImageMacro Editor Project Master Asset Map

이 문서는 프로젝트 운영 자산을 큰 축으로 나누어 추적하는 기준 지도다.
1차 문서 정리 기준에서는 특히 "어떤 문서가 canonical 인가"와 "어떤 문서가 산출물/보관본인가"를 분리해 본다.

## 0) Document Classes
- Canonical
  - `PROJECT_STATUS.md`
  - `AGENTS.md`
  - `docs_for_ai/CONTEXT_SNAPSHOT.md`
  - `now_spec.md`
  - `DEV_LOG.md`
- Conditional
  - `dx_operating_pack/docs_for_ai/CONTEXT_UI.md`
  - `dx_operating_pack/docs_for_ai/CONTEXT_CORE.md`
  - `docs/dev/REAL_WORLD_QA.md`
  - `docs/dev/USER_JOURNEYS.md`
  - `docs/DOC_INDEX.md`
  - `docs/USER_GUIDE.md`
- Generated
  - `docs/reports/project_audit_latest.md`
  - `dx_operating_pack/docs/LESSONS_LEARNED_DRAFT.md`
  - `dx_operating_pack/feedback/LATEST_INSIGHT.yaml`
- Archived
  - `archive/**`
  - `backups/**`
  - `.dx_cache/**`

## 1) Product (Engine + UI)
- Engine
  - `app/core/runner.py`
  - `app/core/exceptions.py`
  - `app/core/models.py`
  - `app/core/recorder.py`
- Interface
  - `app/main.py`
  - `app/ui/dialogs.py`
  - `app/ui/styles.py`
  - `app/ui/overlay.py`
  - `app/ui/selectors.py`

## 2) Rule Guard (Governance)
- Canonical Rules
  - `AGENTS.md`
  - `.cursorrules`
- Rule Guard Tests
  - `tests/test_rule_docs_sync.py`
  - `tests/test_rule_guard_steps_mutation.py`
  - `tests/test_git_hook_guards.py`
- Gate Evidence
  - `.git/post_task_gate.json`

## 3) DX Tools
- Workflow
  - `tools/task_start_guard.py`
  - `tools/task_finish.py`
  - `tools/test_selector.py`
  - `tools/preflight_env.py`
  - `tools/post_task_gate.py`
  - `tools/project_audit.py`
  - `tools/check_tool_integrity.py`
- DX Pack Governance / Sync
  - `dx_operating_pack/tools/setup_dx.py`
  - `dx_operating_pack/tools/sync_dx_pack.py`
  - `dx_operating_pack/tools/post_task_gate.py`

## 4) Real-World QA and Multi-Agent
- Real-World QA
  - `docs/dev/REAL_WORLD_QA.md`
  - `docs/dev/USER_JOURNEYS.md`
  - `docs/dev/BUG_LOOP_PROTOCOL.md`
- Multi-Agent Orchestration
  - `docs/dev/MULTI_AGENT_PROTOCOL.md`
  - `app/core/multi_role_ai.py`
  - `tools/run_multi_role_ai.py`

## 5) Verification Assets
- Test Suites
  - `tests/**`
  - `pytest.ini`
- Runtime Checks
  - `run_health_check.py`
  - `auto_inspect.py`
- Audit Reports
  - `docs/reports/project_audit_latest.md`

## 6) Resources
- Resource Stores
  - `images/`
  - `logs/`
- Template/Runtime Mapping
  - `app/core/scenario_wizard_templates.json`
  - `app/core/scenario_wizard_user_templates.json`
  - `app/utils/runtime_paths.py`

## 7) Documentation Surfaces
- Session Bootstrap
  - `PROJECT_STATUS.md`
  - `AGENTS.md`
  - `docs_for_ai/CONTEXT_SNAPSHOT.md`
- Behavior / Status / History
  - `now_spec.md`
  - `DEV_LOG.md`
  - `PROJECT_STATUS.md`
- User-Facing Docs
  - `README.md`
  - `docs/USER_GUIDE.md`
  - `docs/NEWBIE_GUIDE.md`
  - `요청에 따른 동작 정리.txt`
- Index / Inventory
  - `docs/DOC_INDEX.md`
  - `docs/ASSET_MAP.md`
- DX Pack Docs
  - `dx_operating_pack/README.md`
  - `dx_operating_pack/AGENT_ONBOARDING.md`
  - `dx_operating_pack/docs/**`
  - `dx_operating_pack/docs_for_ai/**`

## 8) Active Operating Loop
1. Start: read `PROJECT_STATUS.md`
2. Bootstrap: read `docs_for_ai/CONTEXT_SNAPSHOT.md`
3. Scope expansion: load `CONTEXT_UI`, `CONTEXT_CORE`, QA docs, or docs/rules docs as needed
4. Implement and validate
5. Gate: `python tools/task_finish.py --subject "..."`
6. Audit when needed: `python tools/project_audit.py`

## 9) Cleanup Guidance
- 1차 문서 정리에서는 canonical 경로를 바꾸지 않는다.
- generated / archived 문서는 검색에 보여도 기본 읽기 세트에 포함하지 않는다.
- `%BDIR%` 같은 잔재 경로는 정체 확인 전까지 active asset으로 보지 않는다.

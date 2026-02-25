# Manifest (v2 Reinforced)

## 1) Rules
- `rules/AGENTS.md`
- `rules/.cursorrules`
- `rules/MULTI_AGENT_PROTOCOL.md`
- `rules/CONSULT_TOKEN_TEMPLATE.md`

## 2) Git Hooks
- `hooks/commit-msg`
- `hooks/pre-commit`
- `hooks/pre-push`

## 3) Tools (Core Governance)
- `tools/install_git_hooks.py`
- `tools/git_hook_guards.py`
- `tools/post_task_gate.py`
- `tools/task_finish.py`
- `tools/task_start_guard.py`
- `tools/test_selector.py`
- `tools/preflight_env.py`
- `tools/cleanup_repo_artifacts.py`
- `tools/ci_governance_guard.py`

## 4) Tools (AI/Context/Security)
- `tools/generate_context_snapshot.py`
- `tools/context_compressor.py`
- `tools/dependency_graph_gen.py`
- `tools/token_usage_analyzer.py`
- `tools/check_ai_security.py`
- `tools/secret_leak_detector.py`
- `tools/export_external_profiles.py`
- `tools/generate_scenario_wizard_templates.py`
- `tools/setup_dx.py`
- `tools/sync_dx_pack.py`
- `tools/capture_lesson_draft.py`

## 5) CI
- `ci/ci.yml`
- `ci/build-exe.yml`

## 6) Tests (Governance + Reusable Core)
- `tests/test_rule_docs_sync.py`
- `tests/test_rule_guard_steps_mutation.py`
- `tests/test_git_hook_guards.py`
- `tests/test_post_task_gate.py`
- `tests/test_task_finish.py`
- `tests/test_task_start_guard.py`
- `tests/test_test_selector.py`
- `tests/test_preflight_env.py`
- `tests/test_ci_governance_guard.py`
- `tests/test_integration_core_logic_patch_guard.py`
- `tests/test_multi_role_ai.py`
- `tests/test_data_orchestration_v2.py`
- `tests/test_session_adapter_v2.py`
- `tests/test_excel_io.py`
- `tests/test_template_processor.py`
- `tests/test_input_lock_runner.py`
- `tests/test_logic_path_simulator.py`
- `tests/test_smart_recorder_core.py`
- `tests/test_smart_recorder_transformer.py`
- `tests/test_coordinate_overlay_mapping.py`

## 7) Multi-Agent Runtime
- `multi_agent/multi_role_ai.py`
- `multi_agent/multi_role_ai_roles.example.json`
- `tools/run_multi_role_ai.py`

## 8) Reusable Modules
- `reusable/core/data_orchestration.py`
- `reusable/core/session_adapter.py`
- `reusable/core/excel_io.py`
- `reusable/core/template_processor.py`
- `reusable/core/input_lock.py`
- `reusable/core/logic_path_simulator.py`
- `reusable/core/recorder.py`
- `reusable/core/smart_recorder.py`
- `reusable/core/evaluator.py`
- `reusable/core/commands.py`
- `reusable/core/models.py`
- `reusable/ui/overlay.py`
- `reusable/ui/styles.py`
- `reusable/ui/widgets.py`

## 9) Docs / Context
- `docs/adr/ADR_TEMPLATE.md`
- `docs/adr/ADR-0001-governance-first.md`
- `docs/KNOWLEDGE_BASE.md`
- `docs/LESSONS_LEARNED.md`
- `docs/COMPLIANCE_CHECKLIST.md`
- `docs/TOKEN_BURN_RATE.md`
- `COMPLIANCE_GUIDE.md`

## 10) AI-Ready Docs / Prompts
- `docs_for_ai/README.md`
- `docs_for_ai/SYSTEM_PSEUDOCODE.md`
- `docs_for_ai/INTERFACES.md`
- `docs_for_ai/SCOPE_GUIDE.md`
- `docs_for_ai/CONTEXT_SNAPSHOT.md` (generated)
- `docs_for_ai/DEPENDENCY_GRAPH.md` (generated)
- `docs_for_ai/TOKEN_USAGE_REPORT.md` (generated)
- `prompt_recipes/README.md`
- `prompt_recipes/REFRACTOR_RECIPE.md`
- `prompt_recipes/TDD_RECIPE.md`
- `prompt_recipes/BUGFIX_RECIPE.md`
- `.cursor/prompts/planner.prompt.md`
- `.cursor/prompts/executor.prompt.md`
- `.cursor/prompts/guardian.prompt.md`
- `MANIFEST_AI.yaml`

## 11) Templates / Ops Docs
- `templates/.gitignore`
- `templates/pytest.ini`
- `templates/requirements-dev.txt`
- `templates/PROJECT_STATUS.template.md`
- `templates/DEV_LOG.template.md`
- `templates/now_spec.template.md`
- `templates/UI_RELEAYOUT_PLAN.reference.md`
- `templates/folder_rules/core.cursorrules.template`
- `templates/folder_rules/ui.cursorrules.template`

## 12) Optional Extras
- `optional/extensions.json`
- `optional/codex_shell.bat`
- `optional/SMOKE_TEST_CHECKLIST.md`
- `optional/build_exe.ps1`
- `optional/run_health_check.py`
- `optional/external/continue_config.local.yaml`
- `optional/external/continue_config.example.yaml`
- `optional/external/README.md`
- `PACK_COVERAGE.md`

## Excluded on Purpose
- `backups/**`
- `logs/**`
- `build/**`, `dist/**`
- `__pycache__/**`, `*.pyc`
- 프로젝트 전용 비즈니스 로직 전체

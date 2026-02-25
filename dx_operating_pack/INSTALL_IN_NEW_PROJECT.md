# Install In New Project

아래 순서를 그대로 실행하면 운영 시스템이 활성화됩니다.

## 0) 대용량 변경/커밋 주의 (권장)
- 리포 가드가 `staged changed lines <= 1400`를 강제합니다.
- 대형 파일은 최초 이식 시에도 기능 단위로 쪼개서 원자 커밋하세요.
- 예: Bone(rules/hooks/ci) -> Brain(manifest/docs) -> Tools -> Assets -> Tests.

## 1) 복사
대상 프로젝트 루트 기준으로 다음 구조를 복사:
- `AGENTS.md` (rules/AGENTS.md)
- `.cursorrules` (rules/.cursorrules)
- `.githooks/*` (hooks/*)
- `tools/*`
- `tests/test_rule_*.py`, `tests/test_git_hook_guards.py`, `tests/test_post_task_gate.py`, `tests/test_task_finish.py`, `tests/test_task_start_guard.py`, `tests/test_test_selector.py`, `tests/test_preflight_env.py`, `tests/test_ci_governance_guard.py`
- `.github/workflows/ci.yml` (필요 시 merge)
- `docs/*`, `docs_for_ai/*`, `prompt_recipes/*`, `.cursor/prompts/*` (AI 최적화 사용 시)

## 1-1) 원클릭 설치(권장)
```bat
python dx_operating_pack\tools\setup_dx.py --pack-root dx_operating_pack --target-root . --mode copy --overwrite
```

## 2) 훅 설치
```bat
python tools/install_git_hooks.py
```

## 3) 기본 의존성
```bat
python -m pip install -r requirements-dev.txt
```

## 4) 검증
```bat
python tools/task_start_guard.py
python -m pytest -q tests/test_rule_docs_sync.py tests/test_rule_guard_steps_mutation.py tests/test_git_hook_guards.py tests/test_post_task_gate.py tests/test_task_finish.py tests/test_test_selector.py tests/test_preflight_env.py tests/test_ci_governance_guard.py
```

## 5) AI 컨텍스트/보안 초기화(권장)
```bat
python tools/generate_context_snapshot.py
python tools/generate_context_snapshot.py --scope core --out docs_for_ai/CONTEXT_CORE.md
python tools/generate_context_snapshot.py --scope ui --out docs_for_ai/CONTEXT_UI.md
python tools/dependency_graph_gen.py
python tools/token_usage_analyzer.py --out docs_for_ai/TOKEN_USAGE_REPORT.md
python tools/check_ai_security.py
```

## 6) 표준 워크플로우
```bat
python tools/task_finish.py --subject "rule(dx): bootstrap workflow" --scope rule
git commit -F .git/TASK_COMMIT_TEMPLATE.md
```

## 7) 외부 프로필 백업(선택)
```bat
python tools/export_external_profiles.py
```
- 생성된 `optional/external/*.local.*` 파일은 공유 금지(민감정보 포함 가능).

## 8) 공용 팩 동기화(선택)
```bat
python tools/sync_dx_pack.py --pack-repo <shared_dx_pack_repo_path> --project-root . --mode copy --overwrite
```

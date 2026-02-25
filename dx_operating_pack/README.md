# DX Operating Pack

이 폴더는 다른 프로젝트에 그대로 이식 가능한 "개발 운영 시스템 + 재사용 코어 + AI 컨텍스트 자산" 백업본입니다.

## 목적
- 규칙/가드/게이트/CI를 표준화해 휴먼 에러를 줄임
- 커밋 품질(테스트/스코프/문서/정합성)을 자동 강제
- 멀티 에이전트(Planner/Executor/Guardian) 운영 프로토콜 재사용
- AI 컨텍스트 압축/스냅샷/의존성 그래프/프롬프트 레시피 재사용
- 보안/컴플라이언스 체크리스트 및 시크릿 스캔 도구 제공

## 빠른 적용 순서
1. 대상 프로젝트 루트에 `rules`, `hooks`, `tools`, `ci`, `tests`, `templates`, `docs`, `docs_for_ai`, `prompt_recipes`를 복사
2. `rules/AGENTS.md`, `rules/.cursorrules`를 대상 루트로 배치
3. `hooks/*`를 대상 프로젝트 `.githooks/`에 배치
4. `tools/*`를 대상 프로젝트 `tools/`에 배치
5. `python tools/install_git_hooks.py` 실행
6. `python tools/task_start_guard.py` -> `python tools/task_finish.py --subject "<msg>" --scope rule`로 워크플로우 검증
7. 필요 시 `.github/workflows/ci.yml` 병합
8. `python tools/generate_context_snapshot.py` 실행해 AI 컨텍스트 스냅샷 생성
9. `python tools/check_ai_security.py` 실행해 시크릿 누수 점검

## 부트스트랩(원라인)
- `curl -fsSL <RAW_SETUP_DX_URL> -o setup_dx.py && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`
- `wget -qO setup_dx.py <RAW_SETUP_DX_URL> && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`

## 핵심 명령
- 시작 전 인덱스 점검: `python tools/task_start_guard.py`
- 작업 종료 표준: `python tools/task_finish.py --subject "<msg>" --scope <feature|rule|cleanup|docs|test>`
- 산출물 인덱스 정리: `python tools/cleanup_repo_artifacts.py --apply`
- 새 프로젝트 설치: `python tools/setup_dx.py --pack-root dx_operating_pack --target-root <project> --mode copy --overwrite`
- 원격 온보딩: `python tools/setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root <project> --mode copy --overwrite`
- 공용 팩 동기화: `python tools/sync_dx_pack.py --remote-url <CENTRAL_REPO_URL_OR_PATH> --project-root <project> --mode copy --overwrite`
- 컨텍스트 스냅샷: `python tools/generate_context_snapshot.py`
- 스코프 스냅샷: `python tools/generate_context_snapshot.py --scope core|ui|dx`
- 의존성 그래프: `python tools/dependency_graph_gen.py`
- 토큰 사용 리포트: `python tools/token_usage_analyzer.py --out docs_for_ai/TOKEN_USAGE_REPORT.md`
- 레슨 초안 자동 생성: `python tools/capture_lesson_draft.py --base HEAD~1 --head HEAD --out docs/LESSONS_LEARNED_DRAFT.md --title "Sprint Draft"`
- 시크릿 스캔: `python tools/check_ai_security.py`

## 구성 범위
- 운영 시스템(규칙/가드/게이트/CI/멀티 에이전트)
- 재사용 코어 샘플(`reusable/core`, `reusable/ui`)
- AI 전용 문서/프롬프트/요약 도구
- 온보딩 가이드(`AGENT_ONBOARDING.md`)
- 생성 리포트(`docs_for_ai/CONTEXT_SNAPSHOT.md`, `DEPENDENCY_GRAPH.md`, `TOKEN_USAGE_REPORT.md`)
- AI 지침형 매니페스트(`MANIFEST_AI.yaml`)

## 주의
- `optional/external/continue_config.local.yaml`은 민감정보가 포함될 수 있습니다.
- 공개 공유 시 `*.example.yaml`만 사용하세요.

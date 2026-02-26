# 🗺️ Macro Editor Project Master Asset Map

이 문서는 프로젝트 운영 자산을 6대 영역으로 고정해 추적하는 기준 지도입니다.

## 1) Product (엔진 및 UI)
- Engine
  - `app/core/runner.py` (실행 엔진)
  - `app/core/exceptions.py` (Stage 4 예외 계층)
- Interface
  - `app/main.py` (메인 윈도우/실행 흐름)
  - `app/ui/styles.py` (전역 QSS)
  - UI 핵심 구조: 좌측 3열 그리드, 스냅 접기 사이드 패널, 상단 옵션 3단 그룹화

## 2) Rule Guard (관리 규율)
- Commit Hook
  - Atomic Cleanup: cleanup 산출물 10개 이상 삭제 시 분리 커밋 강제
  - App Code Guard: `app/` 수정 + 테스트 0건 선택 시 게이트 실패
  - Scale Warning: 수정 파일 7개 / 변경 라인 500 초과 시 분할 권고
- Gate Policy
  - Gate TTL: 30분 초과 시 stale 처리
  - Gate evidence: `.git/post_task_gate.json`
- Canonical Rules
  - `AGENTS.md` (정본), `.cursorrules` (미러)

## 3) DX Tools (자동화 도구)
- Workflow
  - `tools/task_start_guard.py` (작업 시작 게이트)
  - `tools/task_finish.py` (테스트/게이트/템플릿, `--auto-push` 자동 상신)
  - `tools/test_selector.py` (targeted 테스트 자동 선택)
  - `tools/preflight_env.py` (환경 선점검)
  - `tools/post_task_gate.py` (게이트 레코드 생성)
  - `tools/project_audit.py` (전수 자산 감사)
  - `tools/check_tool_integrity.py` (루트 tools <-> dx tools 정합성 검사)
- DX Pack Governance/Sync
  - `dx_operating_pack/tools/setup_dx.py` (신규 프로젝트 설치/적용)
  - `dx_operating_pack/tools/sync_dx_pack.py` (중앙 DX 레포 동기화 + 로컬 보호/백업)
  - `dx_operating_pack/tools/post_task_gate.py` (DX Pack 로컬 게이트)
- Knowledge Feedback Loop
  - `dx_operating_pack/tools/capture_lesson_draft.py` (작업 인사이트 추출 + 최신 AI 세션 JSON/Markdown 신호 반영)
  - `dx_operating_pack/tools/push_dx_feedback.py` (Satellite -> Central inbox 상신)
  - `dx_operating_pack/tools/promote_dx_feedback.py` (Central inbox -> reusable/lessons 승격)
- Multi-Agent Orchestration
  - `app/core/multi_role_ai.py` (Planner/Executor/Guardian 실행 오케스트레이션)
  - `tools/run_multi_role_ai.py` (멀티 역할 AI 실행 CLI)
  - `MULTI_AGENT_PROTOCOL.md` (역할 분리 운영 프로토콜)

## 4) Verification (검증 자산)
- Test Suites
  - `tests/` 하위 unit/integration/e2e 테스트 세트
  - 루트 검증 파일: `pytest.ini`, `test_core_logic.py`
- Rule Guard Tests
  - `tests/test_rule_docs_sync.py`
  - `tests/test_rule_guard_steps_mutation.py`

## 5) Resources (실행 자원)
- Resource Stores
  - `images/` (캡처/매칭 이미지)
  - `logs/` (실행 로그 및 JSONL 기록)
- DX Feedback Stores
  - `dx_operating_pack/feedback/LATEST_INSIGHT.yaml` (최신 인사이트 스냅샷)
  - `dx_operating_pack/feedback/inbox/` (중앙 레포 수신함)
  - `dx_operating_pack/feedback/outbox/` (위성 프로젝트 송신함)
- Resource Mapping Logic
  - `app/core/scenario_wizard_templates.json`
  - `app/core/scenario_wizard_user_templates.json`
  - `app/utils/runtime_paths.py`

## 6) Infrastructure (문서 및 CI)
- Docs
  - `now_spec.md`
  - `PROJECT_STATUS.md`
  - `DEV_LOG.md`
  - `DOC_INDEX.md`
  - `USER_GUIDE.md`
  - `dx_operating_pack/AGENT_ONBOARDING.md`
  - `dx_operating_pack/INSTALL_IN_NEW_PROJECT.md`
- CI
  - `.github/workflows/ci.yml`
- Git Hooks
  - `.githooks/pre-commit`
  - `.githooks/commit-msg`

## 표준 운영 루프
1. 시작: `python tools/task_start_guard.py`
2. 구현: 원자 단위 변경
3. 종료: `python tools/task_finish.py --subject \"...\" --scope ...`
4. 감사: `python tools/project_audit.py`
5. 커밋: `git commit -F .git/TASK_COMMIT_TEMPLATE.md`

## 지속 개선 항목 (Continuous Improvement)
아래 항목은 한 번 구현하고 끝나는 자산이 아니라, 운영 중 계속 튜닝/보강해야 하는 핵심 영역입니다.

1. Global Input Lock
   - 멀티 세션 입력 경합, timeout, 대기 정책 지속 점검
2. Pending 세션 자동 복구
   - backoff/재시도/임계치 초과 시 error 승격 정책 보정
3. 데이터 바인딩 Fail-Fast
   - 미치환 플레이스홀더 타이핑 차단 경로 회귀 점검
4. 구조화 로그/실행 이력 분석
   - JSONL 이벤트 품질, 병목 분석, 히스토리 뷰어 가독성 개선
5. `.macro` 로딩 보안
   - 경로 검증(Path Traversal 방지) 및 포맷 확장 시 방어 규칙 점검

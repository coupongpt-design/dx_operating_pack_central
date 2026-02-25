# 🗺️ Macro Editor Project Asset Map

이 문서는 이 프로젝트의 운영 자산(코드/규칙/도구/문서/CI)을 한 눈에 추적하기 위한 기준 지도입니다.

## 1) Product (매크로 엔진)
- Core
  - `app/core/runner.py` (실행 엔진)
  - `app/core/exceptions.py` (Stage 4 예외 계층)
  - `app/core/models.py` (StepData/RepeatConfig)
- UI
  - `app/main.py` (메인 윈도우/실행 흐름)
  - `app/ui/styles.py` (전역 QSS)
  - Stage 3 결과:
    - 좌측 3열 그리드 액션 패널
    - 스냅 접기(side panel collapse) 지원
    - 상단 옵션 3단 그룹화(Targeting/Flags/Excel)

## 2) Rule Guard (관리 규율)
- Atomic Cleanup
  - cleanup 산출물 대량 삭제(10+)는 `chore(cleanup)` 분리 커밋
- App Code Guard
  - `app/` 수정 시 테스트 선택 0건이면 게이트 실패
- Scale Warning
  - 수정 파일 7개 / 변경 라인 500 초과 시 분할 작업 경고
- Gate TTL
  - 게이트 결과 30분 TTL 만료 시 재검증 요구
- Canonical Rules
  - `AGENTS.md` (정본), `.cursorrules` (미러)

## 3) DX Tools (자동화 도구)
- `tools/task_start_guard.py`
  - 작업 시작 전 staged/index 오염 점검
- `tools/task_finish.py`
  - 테스트 선택/게이트 검증/커밋 템플릿 생성
  - 문서 동기화 확인 절차 포함
- `tools/test_selector.py`
  - 변경 파일 기반 targeted test 자동 선택
- `tools/preflight_env.py`
  - git/python/pytest/메모리 사전 점검
- `tools/post_task_gate.py`
  - 게이트 레코드 작성 및 TTL 기준 소스
- `tools/project_audit.py`
  - 자산 무결성/문서/게이트 상태 감사 리포트 생성

## 4) Docs (문서 체계)
- 기준 문서
  - `now_spec.md`
  - `PROJECT_STATUS.md`
  - `DEV_LOG.md`
  - `DOC_INDEX.md`
- 운영 보조 문서
  - `USER_GUIDE.md`
  - `SMOKE_TEST_CHECKLIST.md`
  - `BUTTON_CHECK.md`
  - `CONSULT_TOKEN_TEMPLATE.md`

## 5) CI / Git Governance
- CI
  - `.github/workflows/ci.yml`
- Local Hooks
  - `.githooks/pre-commit`
  - `.githooks/commit-msg`

## 6) 표준 운영 루프 (권장)
1. 시작: `python tools/task_start_guard.py`
2. 구현: 기능/규칙 변경
3. 종료 게이트: `python tools/task_finish.py --subject \"...\" --scope ...`
4. 감사: `python tools/project_audit.py`
5. 커밋: `git commit -F .git/TASK_COMMIT_TEMPLATE.md`


# Interfaces (LLM-Ready)

## Gate Pipeline
- `tools/task_start_guard.py`
  - 입력: git index/worktree 상태
  - 출력: 시작 가능 여부, 차단 사유

- `tools/test_selector.py`
  - 입력: 변경 파일 목록
  - 출력: targeted test command set

- `tools/post_task_gate.py`
  - 입력: 테스트 결과, 리스크 플래그
  - 출력: pass/fail + gate record(json)

- `tools/task_finish.py`
  - 입력: subject/scope
  - 출력: 통합 실행 + commit template

## Multi-Agent
- `tools/run_multi_role_ai.py`
  - Planner/Executor/Guardian 단계 실행
  - Guardian FAIL 시 차단(정책 기반)

## Security
- `tools/check_ai_security.py`
  - 저장소 스캔 후 잠재 비밀정보 탐지

## Catch-Up
- `tools/generate_context_snapshot.py`
  - 도메인(scope)별 스냅샷 문서 생성

- `tools/generate_session_brief.py`
  - 최신 커밋/게이트/스냅샷 신선도를 1페이지로 요약


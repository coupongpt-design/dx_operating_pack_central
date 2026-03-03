# ADR-0001: Governance-First Workflow

- Status: accepted
- Date: 2026-02-25
- Decision Owner: Project Maintainer

## Context
- AI/사람 혼합 개발에서 규칙 누락과 커밋 품질 편차가 자주 발생.
- 대형 변경에서 회귀가 늦게 발견되면 복구 비용이 커짐.

## Decision
- 운영 정본은 `AGENTS.md`로 두고, 미러는 `.cursorrules`로 유지.
- 작업 시작(`task_start_guard`) + 종료(`task_finish`) 가드로 절차를 강제.
- Git hook + CI rule guard를 기본 활성화한다.

## Consequences
- 장점: 테스트/문서/규칙 정합성 일관 유지.
- 단점: 소규모 변경에서도 절차 비용이 발생.
- 대응: `Compact/Precision` 모드로 실행 깊이를 자동 조절.

## Validation
- `tests/test_rule_docs_sync.py`
- `tests/test_rule_guard_steps_mutation.py`
- `tests/test_post_task_gate.py`
- `tests/test_task_finish.py`


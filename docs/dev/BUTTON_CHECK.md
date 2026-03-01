# 버튼/메뉴 연결 점검 기준 (최신)

**최종 업데이트**: 2026-03-02 (UI 탭 통합 반영)

이 문서는 과거의 라인 번호 수동 점검표를 대체합니다.  
현재 프로젝트는 **테스트 기반**으로 버튼/메뉴 연결 회귀를 관리합니다.

## 1. 검증 원칙
- 고정 라인 번호/수동 캡처 기반 문서는 유지하지 않음.
- 연결 상태는 UI 통합 테스트 + 스모크 실행으로 검증.
- 회귀가 발견되면 테스트 케이스를 먼저 추가한 뒤 수정.

## 2. 핵심 자동 검증
- `python -m pytest -q tests/test_ui_integration.py`
  - Run/Stop/Record, 설정 시그널 연결, 실행 상태 전환 검증
- `python -m pytest -q tests/test_action_dialog_flows.py tests/test_action_dialog_visibility.py`
  - 액션 다이얼로그 저장/취소/노출 경로 검증
- `python -m pytest -q tests/test_window_selector_dialog.py tests/test_window_integration.py`
  - 타겟 선택기/타겟 반영 경로 검증
- `python run_smoke_suite.py --quick`
  - 런타임 핵심 + 이미지 매칭 핵심 스모크 게이트

## 3. 수동 확인(최소)
- `SMOKE_TEST_CHECKLIST.md`의 `A0 타겟 셀렉터`, `A 캡처->매칭`, `B 매칭->클릭` 수행

## 4. 현재 기준
- 전체 회귀 기준: `python -m pytest -q` — `tests/` 하위 전체 통과 확인
- 스모크 기준: `python run_smoke_suite.py` => `PASS`, `SYSTEM HEALTHY`
- **핵심 guard 테스트**: `test_rule_docs_sync`, `test_rule_guard_steps_mutation`, `test_task_start_guard` 반드시 green 유지

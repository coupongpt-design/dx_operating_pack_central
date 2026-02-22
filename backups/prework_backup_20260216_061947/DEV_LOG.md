# 개발 로그

## [2025-11-25] 세션 1
- **목표**: Undo/Redo & 서브스크립트 구현, 테스트/헬스 체크 통합.
- **변경사항**:
  - `app/core/commands.py` 추가(커맨드 패턴, UndoStack) 및 언두/리두 인프라 구성.
  - MacroRunner에 서브스크립트 지원(콜 스택, 공유 변수 컨텍스트).
  - 디버그 오버레이, 휴먼라이크 마우스, 테스트/헬스 체크 스크립트 추가.
  - `.cursorrules`, `docs/PROJECT_STATUS.md` 등 프로젝트 상태 문서화.
- **이슈/버그**: MainWindow CRUD의 완전한 `_push_command` 전환은 남아있음.
- **다음 단계**: `_push_command`로 CRUD 마무리, 드래그/드롭 MoveStepCommand 적용 등.

## [2025-11-27] 세션 2
- **목표**: MainWindow에서 커맨드 패턴 Undo/Redo 완전 연결, 문서 갱신.
- **변경사항**:
  - `_push_command`, `_do_undo`, `_do_redo` 헬퍼 추가; CRUD/이동/복제 모두 UndoStack 경유.
  - `_update_undo_buttons` 적용 및 선택 복원 처리.
  - `.cursorrules`, 프로젝트 상태 문서 최신화.
- **이슈/버그**: 드래그-드롭 재정렬은 아직 Undo 기록 미지원.
- **다음 단계**: 드래그-드롭 MoveStepCommand 기록, UI/스케줄러/액션 확장 검토.

## [2025-11-27] 세션 3
- **목표**: Undo/Redo 통합 완료 및 서브스크립트(중첩 매크로) 구현.
- **변경사항**:
  - MainWindow CRUD 전체 커맨드 패턴 전환, Ctrl+Z/Ctrl+Y Undo/Redo 완전 동작.
  - `ActionType.RUN_MACRO` 추가, MacroRunner에 호출 스택/재귀 가드(깊이 5) + 변수 공유.
  - `NotImageDialog`에 서브 스크립트 경로 선택 UI 추가.
  - `tests/test_subscript_system.py`로 부모-자식 호출 시 컨텍스트 공유 검증.
- **이슈/버그**: 드래그-드롭 재정렬 Undo 기록 미지원 지속.
- **다음 단계**: 드래그-드롭 Undo 지원, 모듈형 매크로 관리 UI/UX 개선.

## [2025-11-28] 세션 4
- **목표**: 안정성 정리 및 UI 리팩터 시도 중단 기록.
- **확정 성공**:
  - Undo/Redo 시스템: 커맨드 패턴으로 MainWindow CRUD 전환, Add/Del/Edit/Move 모두 되돌리기 가능.
  - 서브스크립트: `ActionType.RUN_MACRO` + 호출 스택/재귀 가드(깊이 5) + 변수 컨텍스트 공유.
  - 파일 호환성: `.json`/`.macro` 모두 저장/불러오기/선택 지원.
- **UI 메모**: NotImageDialog UI 리팩터링은 안정성 우려로 롤백(현 UI 유지).
- **다음 단계**: 드래그-드롭 Undo 기록, 낮은 우선순위 UI/UX 개선.

## [2025-11-28] 세션 5 — 안정성 점검
- **목표**: QA 집중 점검, Python 개발 모드 유지 결정.
- **변경사항**:
  - `run_health_check.py`, `auto_inspect.py`로 통합 테스트 실행 체계 확립.
  - 모킹 기반 시뮬레이션/스트레스/행동/분기/입출력 호환성 테스트 추가, 50/50 테스트 통과.
  - Undo/Redo 및 서브스크립트 안정 빌드 검증, `.json`/`.macro` 호환 유지.
- **이슈/버그**: 패키징(.exe) 보류; 드래그-드롭 Undo 기록 미지원 지속.
- **다음 단계**: 기능 추가 전 `run_health_check.py` 실행 습관화, UI/UX 개선(낮은 우선순위).

## [2025-11-28] 세션 6 — Recorder 오버홀
- **목표**: 고부하 녹화 안정화 및 성능 개선.
- **변경사항**:
  - 이벤트 폭주 방지: 큐 최대 5000, 가득 찰 때 드롭 및 1초 단위 경고.
  - 최적화: 이동 최소 거리 필터(기본 3px 미만 무시)로 데이터 폭주 감소.
  - 안정성: `stop()` 스레드 종료 로직 보강(리스너 join 타임아웃 경고).
  - QA: `tests/test_recorder_logic.py`로 모킹 기반 검증.
- **상태**: 긴 세션에서도 사용 가능한 프로덕션 수준 녹화기로 안정화.

## [2025-11-28] 세션 7 — Recorder 최적화 완료
- **목표**: 녹화 품질 향상(지터 감소)과 재생 매끄러움 확보.
- **변경사항**:
  - 하이브리드 필터: 거리<3px & 20ms 미만 움직임 스킵, 느린 정밀 이동은 기록.
  - 드래그 경로 자동 리샘플링(약 20포인트 균등 분포)으로 재생 품질 개선.
  - 메트릭 UI 연동: `stop()` 반환값을 UI 로그/상태바에 표시.
  - 추가 테스트: `tests/test_recorder_advanced.py`로 지터/정밀/드래그 리샘플 검증.
- **상태**: Recorder 최적화 완료, 재생 품질·안정성 확보.
- **메모**: NotImageDialog UI 리팩터링은 안정성 우려로 롤백 상태 유지.

## [2025-11-29] 세션 8 — Window Manager & 메타데이터
- **목표**: 대상 창 제어와 매크로 메타데이터 저장/로드 완성.
- **변경사항**:
  - `WindowManager` 추가: `find_window`/`activate_window`/1px 흔들기(`force_refresh`)로 렌더링 글리치 복구.
  - `MacroRunner` 실행 전 자동 포커스/활성화, 창 미발견 시 경고만 남기고 계속.
  - 매크로 포맷을 JSON dict(meta/repeat/steps)로 확장, 리스트/`.macro` 역호환 유지.
  - UI 통합: 대상 창 제목 입력, Find/Fix 버튼, Window Selector(AHK 필터 로직) 추가.
- **이슈/버그**: pywin32/psutil 미설치 시 기능 제한(경고 후 무시).
- **다음 단계**: Window selector 사용성 검증, 메타데이터 확장 검토.

## [2025-11-29] 세션 9 — UX 폴리시 (Jump If 자동완성)
- **목표**: 조건 분기 UI 사용성 개선.
- **변경사항**:
  - Jump If 변수 입력을 `QComboBox`(editable)로 교체, OCR_STORE 스텝에서 변수명을 스캔해 자동완성 제공.
  - 시스템 변수(`loop_index`, `loop_count`) 기본 제안 추가로 오타/누락 방지.
- **상태**: UX 개선 완료, 추가 조건 빌더 확장은 추후 검토.

## [2025-11-29] 세션 10 — E2E 통합 검증 성공
- **목표**: 전체 라이프사이클(E2E) 회귀 검증.
- **변경사항**:
  - E2E 테스트로 편집 → Undo/Redo → 저장 → 불러오기 → 실행 흐름을 검증.
  - StepData 객체 리팩터링을 완료하고 역호환성 확인(딕셔너리 로드 시 자동 변환).
  - 대상 창 메타데이터가 JSON에 올바르게 저장/복원됨을 확인.
- **상태**: 종합 E2E 통과, 회귀 없음.

## [2025-11-30] 세션 11 — 이미지 스텝 안정화
- **목표**: 이미지 스텝 반복 클릭 UX/안정성 개선.
- **변경사항**:
  - ImageStepDialog에 `Loop until hidden` 옵션 추가, Runner가 템플릿이 사라질 때까지 재탐색·재클릭 후 종료하도록 구현.
  - SpinBox 초기값을 안전 변환하도록 보강(N/A → 기본값)하여 편집 시 `None` 변환 오류 방지.
  - StepData에 `loop_until_hide` 필드 추가(직렬화 호환).
- **상태**: 옵션 기본값 False, 기존 동작 보존.

## [2025-11-30] 세션 12 — 다음 세션 준비
- **목표**: 다음 대화 연속성을 위한 기록 정리.
- **변경사항**:
  - 문서에 이미지 스텝 `loop_until_hide` 관련 상태를 반영.
  - UI/Runner 동작 영향 최소화 원칙을 재확인.
- **이슈/메모**:
  - 버튼 배경 변화 대응(자동 마스크/피처 매칭)은 보류.
  - CMD 환경에서 `python -c` 원라이너가 종종 실패 → `type`/`apply_patch` 중심으로 작업 권장.

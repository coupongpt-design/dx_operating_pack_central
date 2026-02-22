# 개발 로그

## [2025-11-25] 세션 1
- **목표**: Undo/Redo & 서브스크립트 구현, 테스트/헬스 체크 통합.
- **변경사항**:
  - `app/core/commands.py` 추가(커맨드 패턴, UndoStack) 및 언두/리두 인프라 구성.
  - MacroRunner에 서브스크립트 지원(콜 스택, 공유 변수 컨텍스트).
  - 디버그 오버레이, 휴먼라이크 마우스, 테스트/헬스 체크 스크립트 추가.
  - `.cursorrules`, `PROJECT_STATUS.md` 등 프로젝트 상태 문서화.
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

## [2026-02-16] 세션 13 — Scheduler 실패정책 UX/상태표시 강화
- **목표**: 스케줄러 실패 정책이 UI에서 명확히 보이고, 재시도 동작이 의도대로 추적되도록 보강.
- **변경사항**:
  - `MacroScheduler`에 실행/재시도/실패중단 상태 `statusChanged` 발행을 보강해 상태 라벨 가시성 개선.
  - 재시도 시도 번호 계산을 보정해 로그/상태의 시도 표기가 실제 동작과 일치하도록 수정.
  - `MainWindow`에서 `scheduler.statusChanged`를 스케줄러 라벨에 연결(`_on_scheduler_status_changed`).
  - 실패 정책이 `retry_then_continue`일 때만 Retry Count/Delay 입력이 활성화되도록 UI 제어 추가.
  - 스케줄러 코어/통합 테스트 보강(`tests/test_scheduler_core.py`, `tests/test_main_trigger_scheduler_integration.py`).
- **검증 결과**:
  - `python -m pytest -q` → `244 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 14 — 드래그 재정렬 Undo 경로 검증 강화
- **목표**: 스텝 드래그-드롭 재정렬의 실제 Undo/Redo 경로를 통합 테스트로 고정.
- **변경사항**:
  - `tests/test_main_trigger_scheduler_integration.py`에 재정렬 후 `sync_order` 반영, Undo/Redo 복원 검증 테스트 추가.
  - 동일 경로에서 no-op 재정렬 시 Undo 스택이 증가하지 않는 방어 테스트 추가.
  - 문서의 오래된 "드래그-드롭 Undo 미지원" 상태 문구를 최신 코드 상태로 정정.
- **검증 결과**:
  - `python -m pytest -q tests\\test_main_trigger_scheduler_integration.py` → `15 passed`
  - `python -m pytest -q` → `246 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 15 — Action Dialog 취소/중복 UI 보완
- **목표**: 액션 다이얼로그에서 사용자 의도와 다른 저장 동작을 제거하고 UI 중복을 정리.
- **변경사항**:
  - `MainWindow.add_not_image_step`에서 `QDialog.Accepted`가 아닐 때 스텝 추가를 차단.
  - `MainWindow.edit_step_at`의 `NotImageDialog` 경로에서 `QDialog.Accepted`가 아닐 때 편집 반영을 차단.
  - `NotImageDialog` 내부에 중복 생성되던 Run Macro 그룹 1개를 제거.
  - 회귀 테스트 추가:
    - `Cancel` 시 add 미반영
    - `Cancel` 시 edit 미반영
- **검증 결과**:
  - `python -m pytest -q tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py tests\\test_main_trigger_scheduler_integration.py` → `86 passed`
  - `python -m pytest -q` → `248 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 16 — 배경 변화 대응(확장급) 매칭 보강
- **목표**: 버튼/배경 색상 변동 환경에서 이미지 인식 실패를 줄이기 위한 고급 매칭 보강 옵션 추가.
- **변경사항**:
  - `StepData`에 `hq_color_bg_robust` 옵션 추가(기본 `False`, 기존 동작 100% 유지).
  - `Matcher._quality_passes` 보강:
    - `match_quality=high` + `match_color=True` + `hq_color_bg_robust=True`인 경우,
    - `gray/clahe/edge` fallback 패스를 색상매칭 비활성 오버라이드로 추가 실행.
  - `ImageStepDialog` 매칭 탭에 `High Quality Color Robust Fallback` 체크박스 추가.
  - 다이얼로그의 `Test Match`/`accept()` 경로에서 새 옵션 저장/반영 연결.
  - 회귀 테스트 보강(`tests/test_matcher_quality.py`):
    - 색상 모드 기본값에서는 gray 강제 패스가 여전히 스킵되는지 검증.
    - 옵션 활성화 시 fallback 패스가 실제 선택되는지 검증.
    - fallback 패스가 color gate에 막히지 않는지 검증.
- **검증 결과**:
  - `python -m pytest -q tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `6 passed`
  - `python -m pytest -q` → `250 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 17 — PNG 알파 마스크 매칭 지원
- **목표**: 투명 PNG 템플릿에서 배경을 제외한 전경 매칭으로 인식 내성을 강화.
- **변경사항**:
  - `common`에 `decode_png_with_mask()` 추가:
    - PNG를 `IMREAD_UNCHANGED`로 디코드.
    - 알파 채널이 존재하고 완전 불투명이 아니면 0/255 마스크 생성.
  - `StepData` 확장:
    - `alpha_mask_enable` 옵션 추가(기본 `True`).
    - 런타임 캐시 `_tpl_mask` 추가, 직렬화 제외 처리.
    - `ensure_tpl()`에서 템플릿 BGR + 알파 마스크 동시 로드.
  - `Matcher` 확장:
    - 템플릿 마스크의 pass/scale/rotation 캐시 경로 추가.
    - 마스크 존재 시 `matchTemplate`를 mask-aware 경로(`TM_CCORR_NORMED`)로 수행하고 실패 시 안전 폴백.
    - color gate가 마스크 픽셀만 평균 차이를 계산하도록 보강.
    - `find_best_optimized` / `find_all` 모두 마스크를 매칭·게이트에 반영.
  - `ImageStepDialog` 보강:
    - `Use PNG Alpha Mask` 옵션 추가 및 저장/테스트 경로 반영.
    - 이미지 로드 시 알파 마스크를 함께 캐시.
  - `MainWindow` 보강:
    - 이미지 캡처 스텝 생성 시 `_tpl_mask` 초기화.
    - 트리거 저장 시 `_tpl_mask` 임시 필드 제거.
  - 테스트 보강:
    - `tests/test_matcher_quality.py`: mask-aware 매칭 메서드/마스크 기반 color gate 검증 추가.
    - `tests/test_stepdata_serialization.py`: 알파 PNG 로드 시 `_tpl_mask` 생성 검증 추가.
- **검증 결과**:
  - `python -m pytest -q tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `9 passed`
  - `python -m pytest -q tests\\test_ui_integration.py tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q` → `253 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 18 — 알파 없는 템플릿 자동 전경 마스크
- **목표**: 알파 채널이 없는 PNG에서도 배경 영향을 줄이기 위한 자동 전경 마스크 경로 제공.
- **변경사항**:
  - `StepData`에 `auto_fg_mask_enable` 옵션 추가(기본 `False`, 기존 동작 보존).
  - `ImageStepDialog` 매칭 탭에 `Auto Foreground Mask (No Alpha)` 체크박스 추가 및 저장/테스트 경로 연동.
  - `Matcher` 보강:
    - `alpha_mask_enable` 또는 `auto_fg_mask_enable` 중 하나라도 켜져 있으면 마스크 경로 활성.
    - 알파 마스크가 없고 자동 전경 옵션이 켜진 경우:
      - 테두리 배경색 기반 거리 마스크 생성
      - 실패 시 edge 기반 폴백 마스크 생성
      - 결과를 캐시에 저장해 반복 비용 최소화
    - 생성된 마스크를 기존 pass/scale/rotation 매칭 경로에 그대로 전달.
  - 테스트 보강(`tests/test_matcher_quality.py`):
    - 자동 전경 마스크 생성(중심 전경/배경 분리) 검증.
    - 자동 전경 마스크가 실제 매칭 호출에 전달되는지 검증.
- **검증 결과**:
  - `python -m pytest -q tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `11 passed`
  - `python -m pytest -q tests\\test_ui_integration.py tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q` → `255 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 19 — 자동 전경 마스크 임계값 튜닝 옵션화
- **목표**: 템플릿별 자동 전경 마스크 민감도를 사용자 설정으로 조절 가능하게 보강.
- **변경사항**:
  - `StepData` 확장:
    - `auto_fg_mask_bg_percentile` (기본 70.0)
    - `auto_fg_mask_dynamic_scale` (기본 0.6)
    - `auto_fg_mask_min_distance` (기본 12.0)
  - `Matcher._build_auto_fg_mask`가 위 3개 파라미터를 읽어 임계값을 계산하도록 개선.
  - `ImageStepDialog` 매칭 탭에 튜닝 입력 추가:
    - `Auto FG BG Percentile`
    - `Auto FG Dynamic Scale`
    - `Auto FG Min Distance`
  - Test Match/저장(`accept`) 경로에서 신규 값 반영.
  - 테스트 보강(`tests/test_matcher_quality.py`):
    - `min_distance` 조절에 따른 마스크 생성/실패 경로 검증.
    - `dynamic_scale` 조절에 따른 마스크 생성/실패 경로 검증.
- **검증 결과**:
  - `python -m pytest -q tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `13 passed`
  - `python -m pytest -q tests\\test_ui_integration.py tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q` → `257 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 20 — 자동 전경 마스크 프리셋(안정/정확/공격)
- **목표**: 자동 전경 마스크 튜닝값을 스텝별 프리셋으로 빠르게 적용 가능하도록 UX 개선.
- **변경사항**:
  - `ImageStepDialog`에 `Auto FG Preset` 콤보 추가:
    - `Custom`
    - `Stable` (`80.0`, `0.9`, `18.0`)
    - `Accurate` (`70.0`, `0.6`, `12.0`)
    - `Aggressive` (`60.0`, `0.35`, `6.0`)
  - 프리셋 선택 시 자동으로 값 적용 + `Auto Foreground Mask` 활성화.
  - 튜닝 스핀박스를 수동 변경하면 현재 값이 프리셋과 다를 때 `Custom`으로 자동 전환.
  - 신규 테스트 파일 추가(`tests/test_image_dialog_presets.py`):
    - Stable 프리셋 적용 검증
    - 수동 조정 시 Custom 전환 검증
    - 프리셋 적용 후 `accept()` 저장값 검증
- **검증 결과**:
  - `python -m pytest -q tests\\test_image_dialog_presets.py tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `16 passed`
  - `python -m pytest -q tests\\test_ui_integration.py tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q` → `260 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 21 — 프리셋 설명/자동추천 UX
- **목표**: Auto FG 프리셋 선택 의사결정을 돕고, 템플릿 기반 추천으로 초기 설정 시간을 단축.
- **변경사항**:
  - `ImageStepDialog`에 `Suggest` 버튼 추가:
    - 현재 템플릿의 밝기 표준편차 + 엣지 밀도로 `stable/accurate/aggressive` 추천.
    - 템플릿이 없으면 안내 문구 표시.
  - 프리셋 설명 힌트 라벨 추가:
    - 각 프리셋의 권장 상황을 즉시 표시.
  - 프리셋 콤보 툴팁 추가(요약 설명).
  - `tests/test_image_dialog_presets.py` 보강:
    - 힌트 텍스트 갱신 검증
    - Suggest 버튼으로 stable 추천 적용 검증
    - 고엣지 템플릿에서 aggressive 추천 검증
- **검증 결과**:
  - `python -m pytest -q tests\\test_image_dialog_presets.py tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `19 passed`
  - `python -m pytest -q tests\\test_ui_integration.py tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q` → `263 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-16] 세션 22 — Suggest 신뢰도/근거 지표 표시
- **목표**: Auto FG 추천 결과를 수치로 보여 사용자 신뢰도를 높이고 튜닝 판단을 쉽게 만들기.
- **변경사항**:
  - `Suggest` 실행 시 추천 결과 표시를 확장:
    - 추천 프리셋
    - confidence(%)
    - 근거 지표(`std`, `edge density`)
  - 추천/수동 변경 흐름에서 정보 라벨 정리:
    - 프리셋/수동 튜닝 시 이전 추천 정보 초기화
    - 템플릿이 없을 때 안내 메시지 표시
  - 추천 로직 메서드 분리:
    - `preset + confidence + metrics` 반환 메서드 추가
    - 기존 단순 key 반환 메서드는 호환 유지
  - 테스트 보강(`tests/test_image_dialog_presets.py`):
    - Suggest 결과 문자열에 confidence 포함 검증
    - 템플릿 없음 안내 검증
    - 상세 추천 메서드의 confidence 범위/지표 값 검증
- **검증 결과**:
  - `python -m pytest -q tests\\test_image_dialog_presets.py tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `21 passed`
  - `python -m pytest -q tests\\test_ui_integration.py tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q` → `265 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-18] 세션 23 — Suggest 임계값 사용자 설정화
- **목표**: Auto FG Suggest 추천 기준(std/edge low/high)을 스텝별 사용자 설정으로 노출해 템플릿별 추천 편차를 직접 조정 가능하게 보강.
- **변경사항**:
  - `StepData` 확장:
    - `auto_fg_suggest_std_low` (기본 18.0)
    - `auto_fg_suggest_std_high` (기본 42.0)
    - `auto_fg_suggest_edge_low` (기본 0.07)
    - `auto_fg_suggest_edge_high` (기본 0.20)
  - `ImageStepDialog` 매칭 탭에 Suggest 임계값 입력 UI 4종 추가:
    - `Suggest Std Low/High`
    - `Suggest Edge Low/High`
  - 추천 로직 개선:
    - 분류(`stable/accurate/aggressive`)가 고정 임계값 대신 UI 임계값을 사용.
    - confidence 계산도 사용자 임계값을 반영하도록 보정.
    - low/high 역전 입력 시 내부 정규화(자동 swap) 적용.
  - `Test Match` 임시 스텝과 `accept()` 저장 경로에 신규 4개 필드를 연동.
  - 테스트 보강(`tests/test_image_dialog_presets.py`):
    - `accept()` 저장 시 신규 임계값 직렬화 검증.
    - Suggest 임계값 변경이 추천 결과를 실제로 바꾸는지 검증.
- **검증 결과**:
  - `python -m pytest -q tests\\test_image_dialog_presets.py tests\\test_matcher_quality.py tests\\test_stepdata_serialization.py` → `22 passed`
  - `python -m pytest -q tests\\test_ui_integration.py tests\\test_action_dialog_flows.py tests\\test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q` → `266 passed, 1 skipped`
  - `python run_health_check.py` → `SYSTEM HEALTHY`

## [2026-02-18] 세션 24 — 실사용 스모크 테스트 체계 정비
- **목표**: 자동 테스트 통과 후에도 실환경 동작을 빠르게 검증할 수 있도록 실행형 스모크 게이트 + 수동 체크리스트를 표준화.
- **변경사항**:
  - `run_smoke_suite.py` 추가:
    - `--quick`: 런타임 핵심 + 이미지 매칭 핵심 테스트 묶음 실행
    - 기본(full): 위 테스트 + `run_health_check.py` 실행
    - 결과 로그를 `logs/smoke_suite_<mode>_<timestamp>.log`에 저장
    - 실패 시 즉시 중단 + non-zero 종료코드 반환
  - `SMOKE_TEST_CHECKLIST.md` 추가:
    - 실사용 기준 수동 점검 절차(캡처->매칭->클릭->분기->반복->트리거/스케줄러)
    - Pass/Fail 기준 및 결과 기록 템플릿 제공
  - `USER_GUIDE.md`에 스모크 테스트 권장 절차 섹션 추가.
  - 로그 파일명 충돌 방지:
    - 파일명에 `mode` + microseconds를 포함해 동시 실행 시에도 충돌 없도록 보완.
- **검증 결과**:
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)
  - `python run_smoke_suite.py` → `PASS` (`25 passed`, `22 passed`, `266 passed, 1 skipped`, `SYSTEM HEALTHY`)

## [2026-02-19] 세션 25 — 회귀 점검 및 윈도우 셀렉터 복구
- **목표**: 최근 개선/수정 과정에서 "되던 게 안 되는" 회귀를 집중 점검하고 즉시 복구.
- **변경사항**:
  - 윈도우 셀렉터 목록 회귀 대응:
    - `WindowManager.get_window_list()`에서 pywin32 미가용 시 `ctypes` 기반 EnumWindows 폴백 추가.
    - 빈 목록일 때 안내 문구를 리스트에 표시해 무반응처럼 보이는 UX 제거.
  - 목록 표시 개선:
    - 프로세스명을 얻지 못한 창은 `[] title` 대신 `title`만 표시.
  - 멀티 매니저 타겟 선택 회귀 보정:
    - `ManagerTab._on_pick_target()`가 `selected_title()` 호출하던 경로를 `selected_title` 속성 읽기로 수정.
  - 회귀 방지 테스트 추가:
    - `tests/test_window_selector_dialog.py` 신설(표시/빈목록/선택/매니저탭 연동).
    - 시작 타겟 기본값/Runner 기본 타겟 관련 테스트는 기존 추가분 유지.
- **검증 결과**:
  - `python -m pytest -q tests\\test_window_selector_dialog.py tests\\test_window_integration.py tests\\test_ui_integration.py` → `31 passed`
  - `python -m pytest -q` → `272 passed, 1 skipped`
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)
  - `python run_smoke_suite.py` → `PASS` (`25 passed`, `22 passed`, `272 passed, 1 skipped`, `SYSTEM HEALTHY`)

## [2026-02-19] 세션 26 — 문서 전체 동기화
- **목표**: 스펙/상태/가이드 문서 간 불일치를 제거하고 최신 코드 동작 기준으로 단일화.
- **변경사항**:
  - `now_spec.md`:
    - Python 버전 표기를 `3.13` 기준으로 정정.
    - `ManagerTab`/`SessionManager`, Window Selector 표시 규칙, 시작 타겟 빈값 정책, `ctypes` 폴백 동작 반영.
    - QA 기준 테스트 항목에 윈도우 셀렉터/타겟 회귀 테스트 반영.
  - `PROJECT_STATUS.md`:
    - 시작 타겟 정책(앱 시작 시 빈 값, macro 로드 시 반영) 추가.
    - 최신 검증 기준(`272 passed, 1 skipped`, smoke quick/full PASS) 추가.
  - `USER_GUIDE.md`:
    - 타겟 창 고정 섹션에 시작 기본값/권한 일치/셀렉터 표시 규칙 보강.
  - `SMOKE_TEST_CHECKLIST.md`:
    - `A0. 타겟 셀렉터` 항목 추가.
  - `BUTTON_CHECK.md`:
    - 과거 라인번호 수동 점검 문서를 폐기하고 테스트 기반 점검 기준 문서로 전면 교체.
  - 루트 문서 기준 통일:
    - 중복/구버전 `docs/` 문서와 빈 `docs` 디렉터리 제거 상태 유지.
- **검증 결과**:
  - `python -m pytest -q tests\\test_window_selector_dialog.py tests\\test_window_integration.py tests\\test_e2e_runtime_orchestration.py tests\\test_scheduler_core.py tests\\test_trigger_engine_core.py` → `35 passed`
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)

## [2026-02-19] 세션 27 — 문서 전부 동기화(레거시 표기 정리)
- **목표**: 루트 markdown 문서 전체에서 최신 기준 문서와 레거시 문서를 명확히 구분.
- **변경사항**:
  - 레거시 문서 3종에 아카이브 배너 추가:
    - `기능검토_이미지동작추가.md`
    - `검토요약_이미지동작추가.md`
    - `개선완료_이미지동작추가.md`
  - 각 레거시 문서 상단에 최신 참조 문서(`now_spec.md`, `PROJECT_STATUS.md`, `USER_GUIDE.md`, `SMOKE_TEST_CHECKLIST.md`, `BUTTON_CHECK.md`) 안내를 명시.
- **검증 결과**:
  - `python -m pytest -q` → `272 passed, 1 skipped`
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)
  - `python run_smoke_suite.py` → `PASS` (`25 passed`, `22 passed`, `272 passed, 1 skipped`, `SYSTEM HEALTHY`)

## [2026-02-19] 세션 28 — 문서 구조 정리(루트 간소화)
- **목표**: 최신 기준 문서만 루트에 남기고 레거시 문서를 아카이브로 분리.
- **변경사항**:
  - 레거시 3종 이동:
    - `기능검토_이미지동작추가.md`
    - `검토요약_이미지동작추가.md`
    - `개선완료_이미지동작추가.md`
  - 이동 경로: `archive/docs_legacy_20251124/`
  - 신규 인덱스 문서 추가: `DOC_INDEX.md` (최신 기준 문서/아카이브 정책 명시)
- **결과**:
  - 루트 markdown은 최신 운영 문서만 남도록 정리됨.
  - 백업 폴더(`backups/`)는 미변경 유지.

## [2026-02-19] 세션 29 — 일반동작(Add Action) 전수검사
- **목표**: `일반동작+` 경로의 추가/편집 저장 흐름이 의도대로 동작하는지 전수 점검.
- **변경사항**:
  - 관련 테스트 묶음 실행:
    - `tests/test_action_dialog_flows.py`
    - `tests/test_action_dialog_visibility.py`
    - `tests/test_main_trigger_scheduler_integration.py`
    - `tests/test_runner_logic.py`
    - `tests/test_simulation.py`
    - `tests/test_macro_io_compat.py`
  - 누락된 성공/예외 경로 테스트 보강(`tests/test_main_trigger_scheduler_integration.py`):
    - `add_not_image_step` 승인 시 스텝 추가 + Undo/Redo 검증
    - `add_not_image_step`에서 `get_step_data` 예외 시 무변경 검증
    - `edit_step_at` 승인 시 편집 반영 + Undo/Redo 검증
    - `edit_step_at`에서 `get_step_data` 예외 시 무변경 검증
- **검증 결과**:
  - `python -m pytest -q tests/test_main_trigger_scheduler_integration.py tests/test_action_dialog_flows.py tests/test_action_dialog_visibility.py` → `90 passed`
  - `python -m pytest -q tests/test_action_dialog_flows.py tests/test_action_dialog_visibility.py tests/test_main_trigger_scheduler_integration.py tests/test_runner_logic.py tests/test_simulation.py tests/test_macro_io_compat.py` → `100 passed`
  - `python -m pytest -q` → `276 passed, 1 skipped`
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)

## [2026-02-19] 세션 30 — `action (legacy)` 기본값 정리
- **목표**: `일반동작+` 생성 시 `action (legacy)`가 표시되는 혼선을 제거.
- **변경사항**:
  - `MainWindow.add_not_image_step` 기본 타입을 `action` -> `keyboard`로 변경.
  - `NotImageDialog._select_step_type`에 legacy alias 추가:
    - `action` 입력 시 `keyboard`로 자동 매핑.
  - 회귀 테스트 추가:
    - `tests/test_main_trigger_scheduler_integration.py`
      - `test_add_not_image_step_uses_supported_default_type`
    - `tests/test_action_dialog_flows.py`
      - `test_action_dialog_maps_legacy_action_to_keyboard`
- **검증 결과**:
  - `python -m pytest -q tests/test_action_dialog_flows.py tests/test_main_trigger_scheduler_integration.py` → `45 passed`
  - `python -m pytest -q` → `278 passed, 1 skipped`
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)

## [2026-02-19] 세션 31 — Add Action 타입 문서화 강화
- **목표**: Action Type 전체를 사용자 관점에서 쉽게 찾고 이해할 수 있도록 문서 가독성 개선.
- **변경사항**:
  - `USER_GUIDE.md`의 `Add Action 타입 설명` 섹션을 전면 개편:
    - 전체 타입(`keyboard/text/key/key_down/key_up/key_hold/mouse/click_point/drag/scroll/screen_check/pixel_check/screenshot_roi/ocr_check_text/ocr_store/ocr_jump_if/file_action/load_data_file/jump_if/run_macro/comment/start_loop/end_loop`) 기능 설명 추가
    - 통합 타입 vs 직접 타입 구분, 용도 기준 안내 추가
    - 레거시 타입(`loop`, `action`) 동작/권장사항 명시
  - `now_spec.md`의 데이터 모델 섹션에 Action Type 기능 매핑 요약 추가(개발/운영 문서 기준 통일).

## [2026-02-19] 세션 32 — 유저가이드 고급 활용 예시 추가
- **목표**: 개별 기능 설명을 넘어, 실제 자동화 설계에 바로 쓸 수 있는 고급 조합 패턴 제공.
- **변경사항**:
  - `USER_GUIDE.md`에 `고급 사용자 활용 예시 (실전 조합)` 섹션 추가.
  - 포함 시나리오:
    - 다중 계정 일일 루틴 자동 순환
    - CSV 기반 대량 반복 입력
    - OCR 기반 상태판단 + 행동 분기
    - 트리거 인터럽트(긴급 대응)
    - 팝업/오류 자동 복구 루프
    - 증적 수집형 자동화
    - 사람 같은 입력 패턴 안정화
    - 모듈형 매크로 아키텍처
  - 마지막에 실전 설계 팁(검증 순서/분기 패턴/복원력/스모크 점검) 추가.

## [2026-02-19] 세션 33 — Multi-Manager 부분구현 명시 + 통합 테스트 보강
- **목표**: `Multi-Manager`를 완성 기능처럼 오해하지 않도록 문서를 정정하고, UI 경로 검증을 보강.
- **변경사항**:
  - 문서 정정:
    - `USER_GUIDE.md`
      - 왼쪽 탭 설명에서 `Multi-Manager`를 부분구현으로 명시
      - 고급 예시의 Multi-Manager 조합에 주의 문구 추가
      - `Multi-Manager 현재 상태` 섹션 신설(가능 범위/제한/권장 운영)
    - `now_spec.md`
      - `SessionManager`/`Multi-Manager` 설명을 부분구현 기준으로 정정
      - 테스트 기준에 `tests/test_manager_tab_integration.py` 추가
    - `PROJECT_STATUS.md`
      - 코어 모듈에 `SessionManager` 추가
      - 알려진 이슈에 Multi-Manager runner 자동연결 미구현 명시
  - 테스트 보강:
    - `tests/test_manager_tab_integration.py` 추가
      - 세션 추가 시 테이블/매니저 반영
      - `Start All` + runner 없음 => `pending`
      - `Start All` + runner 있음 => `running`/`Stop All` => `stopped`
- **검증 결과**:
  - `python -m pytest -q tests/test_manager_tab_integration.py tests/test_session_manager.py` → `5 passed`
  - `python -m pytest -q` → `281 passed, 1 skipped`
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)

## [2026-02-19] 세션 34 — 작업 규칙 재발 방지 프로토콜 추가
- **목표**: "기능 존재"와 "실사용 완성"을 혼동하는 회귀를 방지.
- **변경사항**:
  - `.cursorrules`에 `Feature Maturity Verification Protocol` 추가:
    - UI 기능을 `Stable/Partial/Experimental`로 강제 분류
    - 완성 선언 전 3단계 검증(`Core Test`, `UI Integration Test`, `Runtime Check`) 강제
    - 기능 상태 변경 시 문서 동기화 대상(`USER_GUIDE.md`, `PROJECT_STATUS.md`, `now_spec.md`) 명시
    - 최종 보고 체크리스트(분류/테스트/제한사항/문서 경로) 명시
    - DEV_LOG 재발 방지 템플릿 권장안 추가
- **재발 방지**:
  - 기능 성숙도 분류 + 3단계 검증을 완료하지 않으면 `Stable`로 보고하지 않음.
- **누락 원인**:
  - 코어 테스트 존재를 완성 근거로 과신하고, UI 통합 경로의 runner 연결 상태를 분리 검증하지 않음.
- **다음 점검 포인트**:
  - UI에 노출된 기능은 반드시 `UI Integration Test`를 근거로 상태를 판정한다.

## [2026-02-19] 세션 35 — 규칙 문서 경로/버전 표기 정리
- **목표**: `.cursorrules`의 오래된 경로 표기(`docs/...`)와 버전 표기를 현재 프로젝트 기준으로 정리.
- **변경사항**:
  - 시작 지시 문서 경로:
    - `@docs/PROJECT_STATUS.md` -> `PROJECT_STATUS.md`
  - Tech Stack 버전:
    - `Python 3.14` -> `Python 3.13`
  - Documentation Sync Protocol 경로:
    - `docs/DEV_LOG.md` -> `DEV_LOG.md`
    - `docs/PROJECT_STATUS.md` -> `PROJECT_STATUS.md`

## [2026-02-19] 세션 36 — Add Action `wait/compare_images` UI + Multi-Manager 자동 runner 보강
- **목표**: 엔진 지원 대비 UI 미노출 타입(`wait`, `compare_images`)을 Add Action에 연결하고, Multi-Manager의 runner 자동 연결을 완성.
- **변경사항**:
  - `NotImageDialog`:
    - Action Type 목록에 `wait`, `compare_images` 추가.
    - `Wait` 그룹 추가(`wait_ms` 편집/저장).
    - `Compare Images` 그룹 추가:
      - `image_a_path`, `image_b_path` 브라우즈
      - `compare_mode`(`mse/ssim/hash`), `compare_threshold`
      - ROI(`compare_roi_x/y/w/h`)
      - `on_match_goto_id`, `branch_on_fail_goto_id`
    - `_refresh_visibility`/`result_step` 경로에 신규 타입 반영.
  - `ManagerTab`:
    - `Start All` 직전에 세션별 runner 자동 생성/연결(`script_path` 기반) 로직 추가.
    - 스크립트 변경 시 기존 runner 정리 후 재생성 경로 보강.
    - 외부 주입용 `set_runner_builder` 제공(테스트/확장성).
  - 테스트 보강:
    - `tests/test_action_dialog_visibility.py`에 `wait`, `compare_images` 가시성/위젯 맵 추가.
    - `tests/test_action_dialog_flows.py`에 저장 검증 추가:
      - `test_action_dialog_wait_saved`
      - `test_action_dialog_compare_images_saved`
    - `tests/test_manager_tab_integration.py`:
      - `test_manager_tab_start_all_builds_runner_when_missing` 추가.
  - 문서 동기화:
    - `USER_GUIDE.md`: Action Type 표/활용 문구/Multi-Manager 상태 최신화.
    - `now_spec.md`, `PROJECT_STATUS.md`: Multi-Manager 설명 및 최신 검증 수치 반영.
- **검증 결과**:
  - `python -m pytest -q tests/test_action_dialog_visibility.py tests/test_action_dialog_flows.py` → `76 passed`
  - `python -m pytest -q tests/test_compare_images_modes.py tests/test_runner_logic.py` → `15 passed`
  - `python -m pytest -q tests/test_manager_tab_integration.py tests/test_session_manager.py` → `6 passed`
  - `python run_health_check.py` → `291 passed, 1 skipped` / `SYSTEM HEALTHY`

## [2026-02-19] 세션 37 — 글로벌 핫키 파서 확장
- **목표**: `SystemHotkeys`가 실사용 조합키를 더 넓게 해석하도록 VK 매핑 범위를 확장.
- **변경사항**:
  - `_parse_combo` 보강:
    - modifier(`ctrl/control`, `shift`, `alt`, `win/meta/super`)를 순서 무관하게 파싱.
    - 비-modifier 키 토큰이 1개가 아니면 invalid 처리.
  - `_get_vk` 매핑 확장:
    - `F1~F24`, NumPad 숫자(`num0`, `numpad9` 등)
    - NumPad 연산(`num_div`, `num_add`, `num_sub`, `num_mul`, `num_dec`)
    - 특수키 alias(`return`, `capslock`, `numlock`, `scrolllock`, `printscreen` 등)
    - OEM 기호 키(`semicolon`, `minus`, `comma`, `slash`, `backslash` 등)
  - 테스트 보강(`tests/test_hotkeys_mapping.py`):
    - 확장 매핑 검증
    - 순서/공백 허용 파싱 검증
    - 다중 키 토큰 invalid 검증
- **검증 결과**:
  - `python -m pytest -q tests/test_hotkeys_mapping.py` → `5 passed`
  - `python -m pytest -q tests/test_ui_integration.py tests/test_config_manager.py` → `25 passed`
  - `python run_health_check.py` → `291 passed, 1 skipped` / `SYSTEM HEALTHY`

## [2026-02-19] 세션 38 — 시나리오 마법사(템플릿 기반) 구현
- **목표**: 기존 매크로 시스템은 유지한 채, 별도 버튼으로 고급 예시 템플릿을 선택/입력/검증 후 스텝 자동 생성하는 마법사 기능 추가.
- **변경사항**:
  - 신규 코어 모듈 추가:
    - `app/core/scenario_wizard.py`
      - 템플릿 카탈로그 로드/스키마 검증
      - 필드 타입별 입력 정규화/검증(오류/경고 분리)
      - 템플릿별 `StepData` 빌더 및 생성 스텝 정합성 검증
      - 미리보기용 스텝 요약 생성
    - `app/core/scenario_wizard_templates.json`
      - schema_version=1
      - 제공 템플릿 6종:
        - 채팅/입력 반복 전송
        - 데이터 파일 기반 서브매크로 실행
        - OCR 값 기반 보호 동작 분기
        - 주기적 증적 스크린샷 수집
        - 서브매크로 재시도 루프
        - 복합 키보드 시퀀스 루프
  - 신규 UI 다이얼로그 추가:
    - `app/ui/scenario_wizard.py`
      - 템플릿 목록 `추천/전체` 필터 + 검색
      - 템플릿 상세(난이도/전제조건/실패 포인트) 표시
      - 필수 입력 동적 폼 생성(문자열/멀티라인/숫자/선택/불리언/파일경로)
      - 생성 미리보기 + 오류/경고 검증
      - 삽입 위치 선택(선택 스텝 다음 / 끝)
  - 메인 윈도우 통합:
    - `app/main.py`
      - 왼쪽 Scenario 버튼 영역에 `시나리오 마법사` 별도 버튼 추가
      - `open_scenario_wizard()` 추가
      - 적용 시 `AddStepsCommand` 경유 삽입(Undo/Redo/기존 CRUD 흐름 유지)
  - 테스트 추가:
    - `tests/test_scenario_wizard_core.py` (코어 빌더/검증)
    - `tests/test_main_scenario_wizard_integration.py` (버튼/삽입 통합 경로)
  - 문서 동기화:
    - `USER_GUIDE.md` (마법사 사용법/템플릿 목록/운영 팁)
    - `now_spec.md` (아키텍처/핵심 기능/템플릿 카탈로그 반영)
    - `PROJECT_STATUS.md` (완료 기능/최신 검증 수치 반영)
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_core.py tests/test_main_scenario_wizard_integration.py` → `8 passed`
  - `python -m pytest -q tests/test_ui_integration.py` → `21 passed`
  - `python -m pytest -q tests/test_main_trigger_scheduler_integration.py` → `22 passed`
  - `python -m pytest -q` → `299 passed, 1 skipped`
  - `python run_smoke_suite.py --quick` → `PASS` (`25 passed`, `22 passed`)

## [2026-02-19] 세션 39 — 시나리오 마법사 템플릿 대규모 확장
- **목표**: 마법사 템플릿을 대폭 확장하고 템플릿 파일 손상 상태를 복구.
- **변경사항**:
  - `app/core/scenario_wizard_templates.json` 복구 및 확장:
    - 총 34개 템플릿으로 재구성(채팅/입력, 키보드/단축키, 마우스, 파일/서브매크로, 스크린샷/OCR/분기).
    - 템플릿 이름을 행동 중심으로 단순화(`[추천]`, 난이도 접미 문구 제거).
    - 빌더 alias(`builder`)를 활용한 변형 템플릿 세트 추가(예: 빠른/느린 채팅, 우클릭/더블클릭, 스크롤 상/하 등).
  - 템플릿 유지보수 자동화:
    - `tools/generate_scenario_wizard_templates.py` 추가.
    - 스키마 호환(`schema_version=1`)을 유지하면서 카탈로그를 재생성하도록 구성.
  - 문서 동기화:
    - `USER_GUIDE.md` 템플릿 목록을 34종 기준으로 갱신.
    - `PROJECT_STATUS.md`, `now_spec.md`에 확장 상태 반영.
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_core.py` → `6 passed`
  - `python -m pytest -q tests/test_main_scenario_wizard_integration.py` → `2 passed`
  - `python -m pytest -q tests/test_ui_integration.py` → `21 passed`
  - `python -m pytest -q` → `299 passed, 1 skipped`

## [2026-02-19] 세션 40 — 리니지류 실전 템플릿 추가
- **목표**: MMORPG(리니지류) 실사용 흐름에 맞는 시나리오 마법사 템플릿을 추가.
- **변경사항**:
  - `tools/generate_scenario_wizard_templates.py`에 리니지류 템플릿 12종 추가:
    - `lineage_click_attack`
    - `lineage_loot_repeat`
    - `lineage_tab_target_repeat`
    - `lineage_npc_dialog_skip`
    - `lineage_basic_attack_hold`
    - `lineage_buff_cycle`
    - `lineage_hp_potion_ocr`
    - `lineage_mp_potion_ocr`
    - `lineage_hp_return_ocr`
    - `lineage_patrol_two_spots`
    - `lineage_combo_submacro_loop`
    - `lineage_hunt_capture`
  - 각 템플릿은 기존 안정 빌더(`click_then_hotkey`, `hotkey_repeat`, `wait_hotkey_repeat`, `ocr_threshold_guard_key`, `ocr_jump_guard_key`, `click_two_points_loop`, `submacro_retry_loop`, `periodic_screenshot_capture`)에 alias 연결.
  - 카탈로그 재생성 후 전체 템플릿 수 `46`으로 확장.
  - 문서 동기화:
    - `USER_GUIDE.md` 템플릿 목록(46종) 및 리니지류 실전 카테고리 반영.
    - `PROJECT_STATUS.md`, `now_spec.md` 템플릿 수치 갱신.
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_core.py` → `6 passed`
  - `python -m pytest -q tests/test_main_scenario_wizard_integration.py` → `2 passed`
  - `python -m pytest -q tests/test_ui_integration.py` → `21 passed`
  - `python -m pytest -q` → `299 passed, 1 skipped`

## [2026-02-21] 세션 41 — 마법사 B안(제한 편집 + 복제) 구현
- **목표**: 마법사 팝업에서 기본 템플릿 원본을 보호하면서 사용자 커스텀 템플릿 저장/수정/삭제를 지원.
- **사전 백업**:
  - `backups/wizard_b_pre_user_template_edit_20260221/`에 관련 파일 백업 후 작업 진행.
- **변경사항**:
  - 코어(`app/core/scenario_wizard.py`):
    - 사용자 카탈로그 경로 추가: `scenario_wizard_user_templates.json`
    - 기본+사용자 템플릿 병합 로딩(`list_templates`) 및 출처 태깅(`template_source`)
    - 사용자 템플릿 생성 API: `create_user_template_from_base(...)`
    - 사용자 템플릿 저장/삭제 API: `upsert_user_template(...)`, `delete_user_template(...)`
    - 사용자 템플릿 ID prefix(`user_`) 정책 및 기본 템플릿 ID 충돌 방지
    - 사용자 템플릿 생성 시 `builder`를 원본 빌더로 고정해 실행 가능성 보장
  - UI(`app/ui/scenario_wizard.py`):
    - 목록 필터에 `사용자` 추가
    - 버튼 추가: `복제 저장`, `사용자 편집`, `사용자 삭제`
    - `UserTemplateEditDialog` 추가(제목/요약/태그 + 필드 기본값 편집)
    - 편집 가능 범위 제한: 구조/빌더 수정 불가 정책 반영
  - 런타임 보강(`app/core/runner.py`):
    - 데이터 치환 토큰 `{data}`(현재 행의 첫 번째 값) 지원 보강
- **테스트 추가**:
  - `tests/test_scenario_wizard_user_templates.py` (코어 CRUD/검증)
  - `tests/test_scenario_wizard_user_template_ui.py` (팝업 복제/편집/삭제 경로)
  - `tests/test_scenario_wizard_catalog_integrity.py` (템플릿 전수 빌드 검증)
  - `tests/test_runner_logic.py`에 `{data}` 치환 회귀 테스트 추가
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_user_templates.py tests/test_scenario_wizard_user_template_ui.py` → `3 passed`
  - `python -m pytest -q tests/test_scenario_wizard_catalog_integrity.py tests/test_scenario_wizard_core.py tests/test_main_scenario_wizard_integration.py` → `9 passed`
  - `python -m pytest -q tests/test_ui_integration.py tests/test_runner_logic.py` → `34 passed`
  - `python -m pytest -vv` → `304 passed, 1 skipped`

## [2026-02-21] 세션 42 — custom_flow 코어(Validator/Atomic) 도입
- **목표**: 마법사 고급 편집 확장을 위한 코어 파이프라인(무결성 검증 + 원자적 저장 + step id remap) 선구현.
- **변경사항**:
  - 신규 모듈 `app/core/scenario_wizard_flow.py` 추가:
    - `atomic_write_json(path, payload)`:
      - 동일 디렉터리에 `.tmp` 생성
      - flush + fsync
      - `os.replace(tmp, real)`로 원자적 저장
    - `materialize_custom_flow_steps(steps_blueprint)`:
      - blueprint(`id`/`step_uuid`) -> `StepData` 변환
      - 실행 시 새 step id 발급 및 참조 필드 리매핑
    - `validate_custom_flow_steps(steps)`:
      - Error: 중복 ID, 고아 참조, 루프 start/end 미페어, self-reference
      - Warning: 미도달 스텝, 뒤로 점프/무한루프 위험
  - `app/core/scenario_wizard.py` 연동:
    - 사용자 카탈로그 저장을 `atomic_write_json`으로 교체
    - `plan_template`에 `mode=custom_flow` 경로 추가
    - custom_flow 계획 시 validator 결과를 errors/warnings에 합산
  - 테스트 추가:
    - `tests/test_scenario_wizard_flow_validator.py`
    - `tests/test_scenario_wizard_custom_flow.py`
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_flow_validator.py tests/test_scenario_wizard_custom_flow.py` → `7 passed`
  - `python -m pytest -q tests/test_scenario_wizard_user_templates.py tests/test_scenario_wizard_user_template_ui.py tests/test_scenario_wizard_core.py tests/test_main_scenario_wizard_integration.py` → `11 passed`
  - `python -m pytest -q tests/test_ui_integration.py tests/test_runner_logic.py tests/test_scenario_wizard_catalog_integrity.py` → `35 passed`
  - `python -m pytest -q` → `311 passed, 1 skipped`

## [2026-02-21] 세션 43 — 삭제 Lazy-Check 코어 + 상세 Validator 리포트
- **목표**: custom_flow 편집기 UI 구현 전, 삭제 참조 보정과 상세 검증 리포트 코어를 선행 고정.
- **변경사항**:
  - `app/core/scenario_wizard_flow.py` 확장:
    - `ValidationIssue` 추가(`level`, `code`, `message`, `step_id`)
    - `validate_custom_flow_steps_detailed(...)` 추가(코드 기반 상세 리포트)
    - `validate_custom_flow_blueprint(...)` 추가(UI 편집 중 blueprint 검증)
    - `find_references_in_blueprint(...)` 추가(삭제 전 참조 카운트/목록)
    - `delete_step_with_lazy_repair(...)` 추가
      - 참조 대상 삭제 시 기본적으로 다음 스텝 ID로 재연결
      - 다음 스텝이 없으면 `None` 처리 + warning 생성
      - loop 참조(`start_loop_id`)는 자동 복구 대신 `None` 처리 + 수동 수정 warning
  - 회귀 없이 기존 `validate_custom_flow_steps(...)` 문자열 인터페이스 유지.
  - 테스트 보강:
    - `tests/test_scenario_wizard_flow_validator.py`
      - 상세 리포트 코드 검증
      - 삭제 Lazy-Check 참조 보정(next/None) 검증
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_flow_validator.py tests/test_scenario_wizard_custom_flow.py` → `10 passed`
  - `python -m pytest -q tests/test_scenario_wizard_user_templates.py tests/test_scenario_wizard_user_template_ui.py tests/test_scenario_wizard_core.py` → `9 passed`
  - `python -m pytest -q tests/test_main_scenario_wizard_integration.py tests/test_ui_integration.py tests/test_runner_logic.py tests/test_scenario_wizard_catalog_integrity.py` → `37 passed`
  - `python -m pytest -q` → `314 passed, 1 skipped`

# 개발 로그

## 운영 지침 (필수)
- 모든 작업 시작 전 첫 명령: `python tools/task_start_guard.py`
- 작업 종료는 `python tools/task_finish.py --subject "..." --scope ...` 경로를 표준으로 사용
- 게이트 통과 후 운영 감사 권장: `python tools/project_audit.py`

## Session 103 - Governance Master Asset Map / Audit 확장
- Date: 2026-02-26
- Summary:
  - `ASSET_MAP.md`를 6대 자산 영역(Product, Rule Guard, DX Tools, Verification, Resources, Infrastructure) 기준으로 재정리.
  - `tools/project_audit.py`를 전수 감사 포맷으로 확장:
    - Verification Health(테스트 파일 수 + Gate 상태)
    - Asset Integrity Matrix(6대 영역)
    - Gate Freshness(TTL 30m)
    - Resource Snapshot(images/logs)
    - Docs Sync Health + Maintenance Guide
  - `tools/task_finish.py`에 문서 3종 mtime drift(5분) 경고 로직 추가.
  - `tools/task_finish.py` 성공 시 감사 안내 문구를 한국어 고정 문구로 통일.
- Validation:
  - `python -m pytest -q tests/test_project_audit.py tests/test_task_finish.py` -> `12 passed in 0.12s`
  - `python -m pytest -q` -> `534 passed, 1 skipped in 41.89s`
  - `python tools/project_audit.py` -> `project_audit_latest.md` 생성 확인

## [2026-02-23] 세션 40
- **목표**: Multi-Agent 운영 체계에 Guardian Hard Gate/롤백/세션 아티팩트 저장을 반영하고 모드 트리거를 AGENTS 규칙과 동기화.
- **변경사항**:
  - `app/core/multi_role_ai.py`
    - `run(..., changed_files=...)`/`select_mode(..., changed_files=...)` 지원 추가.
    - AGENTS 트리거 동기화: 변경 파일 수 5개 이상 또는 `stepdata/serialization/runner/signal` 경로 포함 시 `precision` 강제.
  - `tools/run_multi_role_ai.py`
    - reviewer/guardian 응답에서 `is_approved=false` 또는 `FAIL` 탐지 시 하드게이트(`exit code 1`) 적용.
    - 실패 시 baseline 대비 신규 tracked 변경 파일 자동 rollback 시도(`git checkout -- <file>`).
    - 세션 아티팩트 저장 추가:
      - `logs/ai_sessions/{timestamp}/planner_plan.md`
      - `logs/ai_sessions/{timestamp}/executor_diff.json`
      - `logs/ai_sessions/{timestamp}/guardian_report.json`
  - `MULTI_AGENT_PROTOCOL.md`
    - Guardian 체크리스트에 Monkey Patching 징후 탐지 항목 추가.
  - `tests/test_multi_role_ai.py`
    - `changed_files` 기반 precision 강제 테스트 추가.
    - Guardian FAIL 시 CLI 차단 + rollback 호출 + 아티팩트 생성 테스트 추가.
- **테스트**:
  - Targeted: `python -m pytest -q tests/test_multi_role_ai.py`
  - 결과: `13 passed in 0.06s`
  - Full: `python -m pytest -q`
  - 결과: `418 passed, 1 skipped in 20.21s`

## [2026-02-23] 세션 39
- **목표**: Action Step 편집성 개선(키 녹화), Excel 실행 UX 가시성/로그 개선, 텍스트 입력 편의 옵션 추가.
- **변경사항**:
  - `NotImageDialog` 키 입력 영역에 `[REC]` 버튼 추가.
  - REC 활성 시 `enter/tab/f1/esc` 등 키를 눌러 `Key String` 자동 입력.
  - REC는 `key/key_down/key_up/key_hold` 모드에서만 활성화되도록 제한하여 `text` 입력 모드 간섭 차단.
  - 메인 옵션 바에 `Auto Enter` 체크박스 추가.
  - `MacroRunner`/Excel payload runner에 `auto_enter_after_text` 경로를 연결해 텍스트 입력 뒤 Enter 자동 입력 지원.
  - Excel 오케스트레이션 진행 로그에 워커와 치환 결과를 표시하도록 추가(`job_dispatched` 이벤트 기반).
- **테스트**:
  - Targeted: `python -m pytest -q tests/test_action_dialog_flows.py tests/test_excel_payload_runner_template.py tests/test_excel_toolbar_responsive.py tests/test_runner_logic.py`
  - 결과: `64 passed in 1.37s`
  - Full: `python -m pytest -q`
  - 결과: `415 passed, 1 skipped in 20.32s`

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

## [2026-02-22] 세션 44 — custom_flow 편집 UI(샌드위치/삭제 가로채기/검증 모달) 연동
- **목표**: 마법사 팝업 안에서 템플릿 스텝 흐름을 안전하게 삽입/삭제/검증할 수 있도록 UI를 완성.
- **사전 백업**:
  - `backups/flow_editor_ui_20260222/`에 관련 파일 백업 후 작업 진행.
- **변경사항**:
  - `app/ui/scenario_wizard.py`
    - 신규 `FlowStepEditDialog` 추가:
      - 스텝 타입 선택(`comment`, `wait`, `click_point`, `key`, `keyboard`, `pixel_check`, `ocr_check_text`, `jump_if`, `start_loop`, `end_loop`)
      - 타입별 파라미터 입력
    - 신규 `CustomFlowEditorDialog` 추가:
      - 스텝 사이 `+ 스텝 추가`(샌드위치 삽입)
      - 기본 스텝/사용자 스텝 시각 분리
      - 기본 스텝 읽기 전용(편집/삭제 제한)
      - 삭제 시 `find_references_in_blueprint`로 참조 감지 후 경고 팝업
      - 삭제 승인 시 `delete_step_with_lazy_repair` 적용 + 자동 보정 안내
    - 신규 `FlowValidationDialog` 추가:
      - 저장 전 오류/경고 상세 표시
      - Error 존재 시 저장 차단
      - Warning만 있을 때 확인 후 저장 허용
    - `UserTemplateEditDialog` 확장:
      - `흐름 편집 열기` 버튼 추가
      - 편집 결과를 payload(`use_custom_flow`, `steps_blueprint`, `system_step_ids`)로 반환
    - `ScenarioWizardDialog` 확장:
      - 현재 템플릿 기준 흐름 seed 생성(기본 템플릿은 plan 결과 기반, custom_flow는 blueprint 기반)
      - 사용자 템플릿 저장 전 custom_flow payload 적용(`mode=custom_flow`, `fields=[]`, `steps_blueprint` 저장)
  - `tests/test_scenario_wizard_user_template_ui.py`
    - 기존 monkeypatch 다이얼로그 시그니처를 신규 인자에 맞게 보강
    - `test_scenario_wizard_clone_to_custom_flow` 추가(복제 후 custom_flow 저장 검증)
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_user_template_ui.py tests/test_scenario_wizard_custom_flow.py tests/test_scenario_wizard_flow_validator.py` → `12 passed`
  - `python -m pytest -q tests/test_scenario_wizard_catalog_integrity.py tests/test_scenario_wizard_core.py tests/test_scenario_wizard_custom_flow.py tests/test_scenario_wizard_flow_validator.py tests/test_scenario_wizard_user_template_ui.py tests/test_scenario_wizard_user_templates.py tests/test_main_scenario_wizard_integration.py` → `23 passed`
  - `python -m pytest -q` → `315 passed, 1 skipped`

## [2026-02-22] 세션 45 — 흐름 편집 진입 조건 완화(자동 seed)
- **목표**: "미리보기 생성 전에는 흐름 편집 불가" 제약을 완화해 초반 진입성을 개선.
- **변경사항**:
  - `ScenarioWizardDialog._flow_seed_for_editor(...)` 보강:
    - 기존 입력값으로 plan 실패 시, 필드 타입 기반 자동 seed 값을 생성해 2차 plan 시도.
    - 성공하면 입력값 미완성 상태에서도 흐름 편집기로 진입 가능.
  - 자동 seed 규칙 추가:
    - `str/multiline/path/int/float/bool/choice` 타입별 안전 기본값 생성.
  - 테스트 추가:
    - `test_flow_editor_seed_works_without_manual_required_inputs`
      - `run_macro_once` 템플릿에서 수동 입력 없이도 flow seed가 생성되는지 검증.
- **검증 결과**:
  - `python -m pytest -q tests/test_scenario_wizard_user_template_ui.py tests/test_scenario_wizard_custom_flow.py tests/test_scenario_wizard_flow_validator.py` → `13 passed`
  - `python -m pytest -q` → `316 passed, 1 skipped`

## [2026-02-22] 세션 46 — Runtime Observability(step_uuid) 연동
- **목표**: custom_flow 실행 중 실패 지점을 `step_uuid` 기준으로 추적하고 UI에서 직관적으로 표시.
- **변경사항**:
  - `app/core/scenario_wizard_flow.py`
    - `materialize_custom_flow_steps(...)`에서 런타임 `StepData`에 메타 추가:
      - `source_step_id`
      - `source_step_name`
  - `app/core/runner.py`
    - Runner 시그널 확장:
      - `stepStarted(step_uuid, step_name)`
      - `stepSucceeded(step_uuid)`
      - `stepFailed(step_uuid, step_name, error_message)`
    - 스텝 실행 루프에서 시작/성공/실패 시점마다 시그널 emit.
    - 실패 이벤트는 예외/일반 실패 모두에서 emit되도록 보강.
  - `app/ui/widgets.py`
    - `StepItemWidget` 상태 스타일 확장:
      - active(파란 강조)
      - failed(붉은 강조)
      - active+failed 조합
    - `StepList.set_failed_index(...)` 추가.
  - `app/main.py`
    - 상태 추적 필드 추가:
      - `_last_failed_step_index`, `_last_failed_step_uuid`
    - 상태바 라벨 추가:
      - `Run`(현재 실행 스텝)
      - `Fail`(마지막 실패 스텝/원인)
    - Runner 시그널 연결/해제/재연결(`resume`) 로직 확장.
    - `step_uuid` -> 리스트 row 매핑 후 자동 스크롤/하이라이트 반영.
  - 테스트 보강:
    - `tests/test_runner_logic.py`
      - `test_runner_emits_step_started_and_succeeded_with_source_uuid`
      - `test_runner_emits_step_failed_with_source_uuid_on_failure`
    - `tests/test_ui_integration.py`
      - `test_runner_step_uuid_handlers_update_runtime_debug_ui`
    - `tests/test_scenario_wizard_custom_flow.py`
      - custom_flow 계획 시 `source_step_id` 매핑 검증 추가
- **검증 결과**:
  - `python -m pytest -q tests/test_runner_logic.py tests/test_ui_integration.py tests/test_scenario_wizard_custom_flow.py tests/test_main_trigger_scheduler_integration.py` → `61 passed`
  - `python -m pytest -q` → `319 passed, 1 skipped`

## [2026-02-22] 세션 47 — 자문 전 토큰 최적화 규칙 정비
- **목표**: 다음 외부 자문/협업 턴에서 컨텍스트 토큰 사용량을 줄이기 위한 운영 규칙 및 템플릿 정비.
- **변경사항**:
  - `.cursorrules` 경량화:
    - 중복 섹션 통합, 장문 규칙 축약.
    - `Token Efficiency Protocol` 신설:
      - Delta-first 보고, 최소 파일 읽기, 목표형 테스트 실행, 압축 최종 보고 형식 적용.
  - `CONSULT_TOKEN_TEMPLATE.md` 신규 추가:
    - Quick Ask / Deep Ask 템플릿
    - 토큰 절약 규칙
    - 전달 전 체크리스트
  - `DOC_INDEX.md`에 보조 문서 인덱스 반영.
  - `PROJECT_STATUS.md`, `now_spec.md`에 토큰 최적화 운영 문구 반영.
- **검증 결과**:
  - 문서/규칙 정리 작업(코드 실행 로직 미변경).

## [2026-02-22] 세션 48 — 난이도 기반 동적 모드 전환 규칙(최우선) 추가
- **목표**: 작업 난이도에 따라 `압축 모드`/`정밀 모드`를 자동 전환하도록 강제 상위 규칙 지정.
- **변경사항**:
  - `.cursorrules` 맨 앞에 `Adaptive Mode Enforcement` 섹션 추가.
  - 규칙 우선순위 명시:
    - 충돌 시 본 규칙이 다른 출력/스타일 규칙보다 우선.
  - 전환 기준 추가:
    - 기본 `Compact Mode` 시작
    - 고위험/고복잡 트리거 발생 시 즉시 `Precision Mode`
    - 구현+검증 완료 후 `Compact Mode` 복귀
  - 섹션 번호 재정렬(0~9).
- **검증 결과**:
  - 규칙 문서 업데이트(코드 변경 없음).

## [2026-02-22] 세션 49 — 멀티 역할 AI 오케스트레이터 구현
- **목표**: Claude 스타일의 다중 역할 협업 흐름을 로컬 프로젝트에서 실행 가능한 형태로 도입.
- **변경사항**:
  - 신규 코어 `app/core/multi_role_ai.py` 추가:
    - 역할 모델(`RoleDefinition`), 실행 이력(`RoleTurn`), 결과 모델(`OrchestrationResult`) 정의
    - 오케스트레이터(`MultiRoleAIOrchestrator`) 구현:
      - 역할 체인 순차 실행
      - `compact`/`precision`/`auto` 모드 지원
      - task/context 복잡도 기반 자동 모드 선택
      - 커스텀 역할 ID 지정 실행 및 입력 검증
    - 오프라인 기본 백엔드(`HeuristicRoleBackend`) 추가
    - 커스텀 역할 JSON 로더(`load_roles_from_json`) 및 결과 렌더러(`render_result_markdown`) 추가
  - 실행 스크립트 `tools/run_multi_role_ai.py` 추가:
    - `--task`, `--context`, `--mode`, `--roles`, `--roles-file`, `--format(json/markdown)` 지원
  - 커스텀 역할 포맷 예시 파일 `app/core/multi_role_ai_roles.example.json` 추가
  - 테스트 `tests/test_multi_role_ai.py` 추가:
    - 기본 체인 실행, auto 모드 전환, role 검증 예외, context truncation 마커, roles JSON 로딩, markdown 렌더링 검증
  - 문서 동기화:
    - `USER_GUIDE.md`, `PROJECT_STATUS.md`, `now_spec.md`
- **검증 결과**:
  - `python -m pytest -q tests/test_multi_role_ai.py` → `10 passed`
  - `python -m pytest -q` → `329 passed, 1 skipped`

## [2026-02-22] 세션 50 — 구조화 JSON Lines 런타임 로그 추가
- **목표**: 런타임 사후 분석을 위해 `run_id`, `duration_ms`, 실패 원인을 JSON Lines로 안정 기록.
- **변경사항**:
  - 신규 유틸 `app/utils/structured_jsonl.py` 추가:
    - JSONL 라인 단위 쓰기(각 라인 독립 JSON 객체)
    - 공통 필드 자동 주입: `timestamp(UTC)`, `run_id`, `level`, `event`
  - `app/core/runner.py` 확장:
    - 실행 단위 `run_id` 생성 및 상태 필드(`structured_log_path`) 노출
    - 이벤트 기록:
      - `run_started` / `run_resumed` / `run_finished` / `run_stop_requested`
      - `step_started` / `step_succeeded` / `step_failed`
    - 스텝 시작/종료 시각 추적으로 `duration_ms` 기록
    - 실패 이벤트에 `error` 기록
    - 기존 step 시그널(`stepStarted/stepSucceeded/stepFailed`)은 그대로 유지
  - `app/main.py`:
    - 메인 실행/트리거 실행에서 `MacroRunner(..., structured_logging=True)`로 구조화 로그 활성화
  - 테스트 추가 `tests/test_runner_structured_jsonl.py`:
    - 성공 경로 JSONL 기록 검증
    - 실패 경로 JSONL 기록 검증(`stop_on_fail=True`)
- **검증 결과**:
  - `python -m pytest -q tests/test_runner_structured_jsonl.py tests/test_runner_logic.py tests/test_ui_integration.py` → `39 passed`
  - `python -m pytest -q` → `331 passed, 1 skipped`

## [2026-02-22] 세션 51 — 실행 이력(History Viewer) MVP 추가
- **목표**: JSONL 구조화 로그를 앱 내부에서 즉시 조회/분석할 수 있는 실행 이력 뷰어 제공.
- **변경사항**:
  - 신규 코어 `app/core/run_history.py` 추가:
    - `load_run_events(...)` (손상 라인 스킵 포함)
    - `summarize_run_events(...)` (상태/총시간/실패 수/병목 스텝)
    - `list_run_summaries(...)` (`logs/run_events_*.jsonl` 최신순 목록화)
  - 신규 UI `app/ui/history_viewer.py` 추가:
    - 좌측 실행 목록 테이블(run_id, 상태, 총소요, 스텝 수, 실패 수, 병목)
    - 우측 이벤트 타임라인(`step_name`, `duration_ms`, `error`) 상세 테이블
    - 실패/성공/불완전 상태 색상 하이라이트
  - 메인 메뉴 연동 `app/main.py`:
    - `Help -> Execution History` 액션 추가
    - `_open_execution_history()` 다이얼로그 오픈 경로 추가
  - 테스트 추가/보강:
    - `tests/test_run_history.py` (파서/요약/정렬 검증)
    - `tests/test_ui_integration.py`에 이력 뷰어 오픈 경로 테스트 추가
- **검증 결과**:
  - `python -m pytest -q tests/test_run_history.py tests/test_runner_structured_jsonl.py tests/test_ui_integration.py tests/test_runner_logic.py` → `44 passed`
  - `python -m pytest -q` → `336 passed, 1 skipped`

## [2026-02-22] 세션 52 — Option A(긴급중단 + 일시정지/재개) 구현
- **목표**: 사용자 통제권 보장을 위해 글로벌 안전장치(일시정지/재개, 긴급중단) 추가.
- **변경사항**:
  - `MacroRunner` 제어 확장:
    - `pause()` / `resume_run()` / `kill()` / `is_paused()` 추가
    - `threading.Event` 기반 대기로 pause 상태에서 CPU 스핀 방지
    - `msleep` 및 주요 실행 루프에 pause 대기/kill 즉시 탈출 반영
  - 구조화 로그 확장:
    - `run_paused`, `run_resumed`, `run_killed` 이벤트 기록
    - kill 시 `run_finished(success=False, reason=\"killed\")`로 종료 원인 명시
  - 글로벌 핫키 연동:
    - `F10` = Pause/Resume 토글
    - `F12` = Emergency Kill
    - `SystemHotkeys`(WM_HOTKEY) + 로컬 `QShortcut` 모두 연결
  - 설정/프로필 확장:
    - hotkey config에 `pause`, `kill` 키 추가
    - import/export profile에 `pause`, `kill` 포함
  - 테스트 보강:
    - `tests/test_runner_structured_jsonl.py`:
      - pause/resume 로그 이벤트 검증
      - kill 이벤트 + finished reason 검증
    - `tests/test_ui_integration.py`:
      - 핫키 pause/resume 토글 동작
      - 핫키 kill 호출 및 UI 상태 동기화
    - `tests/test_config_manager.py`:
      - pause/kill 설정 로드/저장 검증
- **검증 결과**:
  - `python -m pytest -q tests/test_config_manager.py` → `4 passed`
  - `python -m pytest -q tests/test_runner_structured_jsonl.py` → `4 passed`
  - `python -m pytest -q tests/test_ui_integration.py` → `25 passed`
  - `python -m pytest -q` → `340 passed, 1 skipped`

## [2026-02-22] 세션 53 — Option A UX 마무리(설정 UI + Paused 시각화)
- **목표**: 안전장치 기능을 사용자가 바로 이해하고 실수 없이 설정할 수 있도록 UX 마감.
- **변경사항**:
  - `HotkeySettingsDialog` 확장:
    - 항목 추가: `Pause/Resume`, `Emergency Kill`
    - 중복 단축키 충돌 검증 추가(붉은 경고 텍스트 표시, 저장 차단)
  - `MainWindow` 핫키 설정 연동:
    - 신규 다이얼로그 반환값(7개 핫키) 반영
    - 저장 직전 2차 충돌 검증(방어적 체크)
  - Paused 상태 시각화:
    - Run 버튼 상태 전환: 기본(파랑 `실행`) ↔ 일시정지(주황 `▶ 재개`)
    - 상태바/런타임 라벨에 `Paused` 명시
    - 일시정지 중 Run 버튼 클릭 시 재개 동작으로 연결
  - 테스트 보강:
    - `tests/test_ui_integration.py`:
      - pause/resume 시 버튼 텍스트/스타일/상태 플래그 검증
      - hotkey dialog 중복 차단/정상 허용 검증
- **검증 결과**:
  - `python -m pytest -q tests/test_ui_integration.py` → `27 passed`
  - `python -m pytest -q tests/test_hotkeys_mapping.py` → `5 passed`
  - `python -m pytest -q tests/test_config_manager.py` → `4 passed`
  - `python -m pytest -q` → `342 passed, 1 skipped`

## [2026-02-22] 세션 54 — Option B(해상도 독립 + 이미지 조건 대기) 구현
- **목표**: 해상도/배율 차이 환경에서 이미지 기준 상대 클릭을 안정화하고, 클릭 없는 이미지 조건 대기를 정식 스텝으로 제공.
- **변경사항**:
  - `StepData` 확장:
    - `anchor_image_path`, `image_path` 필드 추가.
    - `ensure_tpl()`에서 `png_bytes`가 없을 때 경로 기반 이미지 로드 지원.
    - `wait_for_image` 타입 직렬화 지원(`image_click`과 동일한 이미지 에셋 처리).
  - `MacroRunner` 확장:
    - 새 스텝 핸들러 `wait_for_image` 추가.
    - `click_anchor`(`center/top-left/top-right/bottom-left/bottom-right`)를 실제 클릭 좌표 계산에 반영.
    - branch target 클릭에도 `click_anchor`/offset 반영.
    - `hold_until_next` 탐색 대상에 `wait_for_image` 포함.
  - 입출력/편집 경로 연동:
    - `MacroIO`에 `wait_for_image` 이미지 저장/복원 지원 추가.
    - `MainWindow` 편집/미리보기/분기변환 경로에서 `wait_for_image`를 이미지 스텝으로 동일 처리.
    - 시나리오 마법사 custom_flow 편집 스키마에 `image_click`, `wait_for_image` 추가.
  - 문서 동기화:
    - `PROJECT_STATUS.md`, `now_spec.md`, `USER_GUIDE.md` 업데이트.
- **테스트 보강**:
  - `tests/test_runner_logic.py`
    - `image_click` 앵커 좌표 계산 검증.
    - `wait_for_image` 성공(무클릭)/타임아웃 검증.
  - `tests/test_stepdata_serialization.py`
    - `anchor_image_path` 기반 템플릿 로드 검증.
- **검증 결과**:
  - `python -m pytest -q tests/test_runner_logic.py` → `18 passed`
  - `python -m pytest -q tests/test_stepdata_serialization.py tests/test_scenario_wizard_flow_validator.py tests/test_scenario_wizard_user_template_ui.py` → `15 passed`
  - `python -m pytest -q tests/test_macro_io_compat.py` → `1 passed`
  - `python -m pytest -q` → `347 passed, 1 skipped`

## [2026-02-22] 세션 55 — Option C(.macro 패키지 생태계) 구현
- **목표**: `.macro`를 공유 가능한 표준 패키지로 정리하고(Export/Import), 구포맷 호환성과 안전한 경로 로드를 보장.
- **변경사항**:
  - `app/io/macro_io.py`
    - 저장 포맷을 `template.json + assets/*.png` 구조로 표준화.
    - 구포맷(`scenario.json + images/*.png`) 로드는 그대로 지원.
    - `load_macro_payload()` 추가로 `.macro` 메타 접근 경로 제공.
    - 내부 에셋 경로 로드 시 unsafe 경로(`../`, 절대경로, 드라이브 경로) 차단.
  - `app/main.py`
    - `Save`에서 파일 확장자가 `.macro`면 `MacroIO.save_macro(...)`로 ZIP 패키지 저장.
    - `.macro` 로드 fallback 시 `meta.target_window` 복원 반영.
- **테스트 보강**:
  - 신규 `tests/test_macro_io_package.py`
    - `template.json + assets/` 저장 구조 검증
    - 레거시 `scenario.json + images/` 로드 호환 검증
    - unsafe asset path 차단 검증
  - `tests/test_macro_load_formats.py`
    - `MainWindow.save_macro()`의 `.macro` ZIP 저장 검증
    - `.macro` 로드시 `meta.target_window` 복원 검증
- **검증 결과**:
  - `pytest -q tests/test_macro_io_package.py tests/test_macro_load_formats.py` → `6 passed`
  - `pytest -q` → `352 passed, 1 skipped`

## [2026-02-22] 세션 56 — Packaging MVP(PyInstaller + 런타임 경로/OCR 설정) 구현
- **목표**: 배포 환경(onefile/onedir)에서 리소스 경로와 OCR 의존성 문제를 줄이고, 빌드 파이프라인 초안을 코드베이스에 내장.
- **변경사항**:
  - 런타임 경로 유틸 추가: `app/utils/runtime_paths.py`
    - `sys._MEIPASS` 대응 `get_resource_path(...)`
    - writable app data 경로 `get_writable_app_dir(...)`
  - 시나리오 마법사 경로 개선: `app/core/scenario_wizard.py`
    - builtin 템플릿 경로를 리소스 경로 기반으로 로드
    - 사용자 템플릿 기본 저장 위치를 writable app data로 변경
  - OCR 런타임 설정 코어 추가: `app/core/ocr_runtime.py`
    - env/settings/default/PATH 순서로 Tesseract 경로 해석
    - `configure_tesseract_cmd()`로 pytesseract 런타임 적용
  - OCR 호출 연동:
    - `app/core/vision.py`의 초기 경로 설정 로직을 `ocr_runtime`로 통합
    - `app/core/runner.py` OCR 텍스트 호출 전에 `configure_tesseract_cmd()` 적용
  - UI 설정 연동: `app/main.py`
    - Settings 메뉴에 `OCR (Tesseract) Path...` 추가
    - 최초 실행 시 OCR 경로 미설정 안내/설정 유도(오프스크린/CI에서는 자동 스킵)
    - `USER_GUIDE.md` 오픈 경로를 리소스 경로 기반으로 정규화
  - 빌드 파이프라인 추가:
    - `ImageMacro.spec`
    - `tools/build_exe.ps1`
    - `.github/workflows/build-exe.yml` (manual dispatch)
- **테스트 보강**:
  - 신규 `tests/test_runtime_paths.py`
  - 신규 `tests/test_ocr_runtime.py`
  - `tests/test_vision_logic.py` 갱신(새 OCR 경로 설정 구조 반영)
- **검증 결과**:
  - `pytest -q tests/test_runtime_paths.py tests/test_ocr_runtime.py tests/test_vision_logic.py tests/test_scenario_wizard_user_templates.py` → `19 passed`
  - `pytest -q` → `357 passed, 1 skipped`

## [2026-02-23] 세션 57 — 데이터 주도 자동화 V2(CSV/XLSX + 컬럼 매핑 + 사전 검증)
- **목표**: 데이터 기반 자동화를 CSV 중심에서 CSV/XLSX 공통으로 확장하고, 마법사에서 컬럼 매핑 UX/검증을 강화.
- **변경사항**:
  - 신규 `app/io/data_loader.py` 추가:
    - CSV/Excel(`.xlsx/.xlsm/.xltx/.xltm`) 공통 로딩
    - 컬럼 헤더 정규화(빈 헤더 보정/중복 헤더 suffix)
    - 빈 행 자동 스킵 + 메타(`columns`, `row_count`, `empty_row_count`) 제공
  - `app/core/runner.py`
    - `load_data_file`가 `load_data_rows(...)` 사용하도록 변경(CSV/XLSX 공통)
    - 로드 후 컬럼/행 데이터 정규화 저장(`_data_rows`, `_data_columns`, `_data_row_values`, `_data_list`)
    - 데이터 토큰(`{column}`) 누락 컬럼 사전 검증 실패 시 실행 차단
  - `app/core/scenario_wizard.py`
    - 생성 스텝 검증에 데이터 바인딩 검증 추가
      - 누락 컬럼: Error
      - 빈 행: Warning
      - 데이터 파일 파싱 불가/헤더 비어있음: Warning
    - 데이터 템플릿의 로드 스텝 명칭을 `Load Data`로 통일
  - `app/ui/scenario_wizard.py`
    - 데이터 템플릿의 문자열 입력 필드에 `컬럼` 버튼 추가
    - 데이터 파일 경로 변경 시 컬럼 목록 재로딩
    - 컬럼 선택 시 `{column_name}` 토큰 자동 삽입
  - `app/core/scenario_wizard_templates.json`
    - 데이터 템플릿 3종의 파일 필터를 `CSV + XLSX`로 확장
    - 제목/요약/라벨을 `CSV` 고정 표현에서 `데이터` 표현으로 정리
  - 배포/의존성:
    - `requirements-dev.txt`에 `openpyxl` 추가
    - `ImageMacro.spec` hiddenimports에 `openpyxl` 추가
- **테스트 추가/수정**:
  - 신규:
    - `tests/test_data_loader.py`
    - `tests/test_scenario_wizard_data_validation.py`
    - `tests/test_scenario_wizard_data_mapping_ui.py`
  - 수정:
    - `tests/test_runner_logic.py` (`load_data_rows` 기반으로 갱신 + 누락 컬럼 실패 케이스 추가)
- **검증 결과**:
  - `pytest -q tests/test_data_loader.py tests/test_runner_logic.py tests/test_scenario_wizard_core.py tests/test_scenario_wizard_data_validation.py tests/test_scenario_wizard_data_mapping_ui.py` → `32 passed`
  - `pytest -q` → `364 passed, 1 skipped`
## [2026-02-22] 세션 58 — 규칙 적용률 강화(AGENTS 동기화/트리거/가드 테스트)
- **목표**: 커서룰스 품질은 유지하면서 멀티툴(Codex 포함) 환경에서 규칙 적용률을 높이는 보강.
- **변경 사항**:
  - `AGENTS.md`와 `.cursorrules` 동시 업데이트.
  - `Precision` 강제 전환 트리거를 기계식으로 명시:
    - touched files >= 5
    - `StepData` 변경
    - serialization/load-save 변경
    - thread/signal orchestration 변경
    - runner flow(`goto/repeat/branch`) 변경
    - 재현 불명/회귀 범위 불명
  - Session Start 게이트 강화:
    - `PROJECT_STATUS.md` 선확인
    - Current Focus 2줄 요약
    - 편집 전 모드 선언
  - 실행 가능한 가드 추가:
    - `tests/test_rule_guard_steps_mutation.py`
    - `app/main.py`에서 `self.steps` 직접 변이(`append/extend/insert/pop/remove/clear/sort/reverse`, 인덱스 대입/삭제, `+=`) 감지 시 실패.
- **검증**:
  - `pytest -q tests/test_rule_guard_steps_mutation.py` → `1 passed`
  - `pytest -q tests/test_scenario_wizard_data_validation.py tests/test_runner_logic.py` → `23 passed`
  - `pytest -q` → `365 passed, 1 skipped`
- **비고**:
  - 백업 디렉터리(`backups/`)는 미수정.

## [2026-02-22] 세션 59 — 규칙 체계 2단 구조 전환(정본/상세본 + 단방향 동기화)
- **목표**: 규칙 자체 변경이 아니라 멀티툴 적용률과 유지보수성을 높이기 위한 구조 개편.
- **변경 사항**:
  - `AGENTS.md`를 Canonical 실행 규약(요약본)으로 압축 재작성.
  - `.cursorrules`를 상세 헌법/운영 노트로 재구성하고 상단에 동기화 블록(`SYNC_BLOCK_START/END`) 배치.
  - 동기화 정책을 단방향(`AGENTS.md -> .cursorrules`)으로 고정하고 루프 위험 제거.
  - 실행 가드 강화:
    - `tests/test_rule_guard_steps_mutation.py`에 allowlist 기반 `self.steps = ...` 재바인딩 감시 추가
    - 허용 함수: `__init__`, `_load_macro_from_path`
  - 신규 검증 테스트:
    - `tests/test_rule_docs_sync.py` (AGENTS/.cursorrules 동기화 블록 일치 강제)
- **검증**:
  - `pytest -q tests/test_rule_docs_sync.py tests/test_rule_guard_steps_mutation.py` → `2 passed`
  - `pytest -q tests/test_runner_logic.py tests/test_scenario_wizard_data_validation.py` → `23 passed`
  - `pytest -q` → `366 passed, 1 skipped`
- **비고**:
  - `backups/` 영역 미수정.

## [2026-02-22] 세션 60 — Multi-Agent 운영 프로토콜(2-Agent 기본, 3-Agent 승격) 반영
- **목표**: API 추가 없이 역할 분리(Planner/Executor/Guardian) 운영을 규칙 체계에 내재화.
- **변경 사항**:
  - `AGENTS.md`(정본)에 Multi-Agent 워크플로 추가:
    - 기본: `Executor -> Guardian`
    - 승격: Precision 트리거 시 `Planner -> Executor -> Guardian`
    - 역할 제약(Planner 코드수정 금지, Guardian 읽기전용 PASS/FAIL 게이트) 명시
    - 규칙 파일 변경 단독 변경 세트 원칙 추가
  - `.cursorrules`(상세본)에 Multi-Agent 상세 운영 섹션 추가.
  - 동기화 블록에 Multi-Agent 핵심 규약 라인 추가(정본/미러 동시 반영).
  - 신규 문서 `MULTI_AGENT_PROTOCOL.md` 추가:
    - 도입 단계(2-Agent/3-Agent), 트리거, 실행 프로토콜
    - Planner/Executor/Guardian 복붙 프롬프트 템플릿
    - 2~4주 관찰 지표
- **검증**:
  - `pytest -q tests/test_rule_docs_sync.py tests/test_rule_guard_steps_mutation.py` (동기화/가드)
  - `pytest -q` (전체 회귀)
- **비고**:
  - 규칙/문서 중심 변경(런타임 로직 변경 없음).
  - `backups/` 미수정.

## [2026-02-22] 세션 61 — Git 도입 및 규칙 파일 보호 정책 적용
- **목표**: 규칙 체계/대형 리팩터 안정화를 위한 Git 기반 거버넌스 도입.
- **변경 사항**:
  - 로컬 Git 초기화 및 사용자 설정 반영.
  - 베이스라인 커밋 생성(`baseline_before_git_governance`).
  - `.gitignore` 추가 커밋(`chore_add_gitignore`).
  - `AGENTS.md`에 Git Governance 섹션 추가:
    - 헌법급 파일 지정(`AGENTS.md`, `.cursorrules`, `tests/test_rule_docs_sync.py`, `tests/test_rule_guard_steps_mutation.py`)
    - delete/recreate 금지, edit+diff 검토, 단독 변경 세트 원칙
    - runner/signal/StepData 리팩터 전 snapshot 커밋 원칙
  - `.cursorrules` 상세본에 동일 정책 확장 반영.
  - SYNC_BLOCK에 Git 거버넌스 핵심 라인 동기화 반영.
- **검증**:
  - `python -m pytest -q tests/test_rule_docs_sync.py tests/test_rule_guard_steps_mutation.py` → `2 passed`
  - `python -m pytest -q` → `366 passed, 1 skipped`
- **비고**:
  - `backups/` 미수정.

## [2026-02-22] 세션 62 — Post-Task Commit Gate 강제 반영
- **목표**: 작업 종료 시 테스트/디프/커밋 품질 게이트를 강제로 통일.
- **변경 사항**:
  - `AGENTS.md` Git Governance에 `Post-Task Commit Gate` 추가.
  - SYNC_BLOCK에 commit 게이트 핵심 라인 추가(정본/미러 동시 반영):
    - targeted 선실행
    - 리스크 트리거 시 full pytest
    - `git diff` 확인 후 clean 상태에서만 커밋
    - 커밋 메시지 테스트 블록(`targeted`, `full suite`) 의무화
  - `.cursorrules` 상세본 Git Governance 섹션에도 동일 규칙 확장.
  - `MULTI_AGENT_PROTOCOL.md` Executor 역할에 commit gate 규칙 추가.
- **검증**:
  - `python -m pytest -q tests/test_rule_docs_sync.py tests/test_rule_guard_steps_mutation.py`
  - 리스크 트리거(규칙 파일 다중 수정)로 `python -m pytest -q` 전체 실행

## [2026-02-22] 세션 63 — Waste-Reduction Protocol 강제 반영
- **목표**: 검색/열람/출력 낭비를 줄이고 증거 중심 답변을 강제.
- **변경 사항**:
  - `AGENTS.md`에 Waste-Reduction Protocol(검색 예산/중복 금지/write-first/no dump/output contract) 추가.
  - SYNC_BLOCK에 동일 핵심 라인 추가(정본/미러 정합 유지).
  - `.cursorrules` 상세본에 Waste-Reduction 상세 섹션 추가.
  - `MULTI_AGENT_PROTOCOL.md` Executor 역할에 Waste-reduction gate 반영.
  - 상태 문서(`PROJECT_STATUS.md`, `now_spec.md`)에 운영 원칙 반영.
- **검증**:
  - `python -m pytest -q tests/test_rule_docs_sync.py tests/test_rule_guard_steps_mutation.py`
  - 리스크 트리거(규칙 파일 다중 수정)로 `python -m pytest -q` 전체 실행
 
## [2026-02-23] Session 64 - Multi-Manager pending auto-recovery 
- Changes: 
  - app/core/session_manager.py: added per-session recovery backoff, optional runner_provider, pending escalation to error after thresholds. 
  - app/ui/tabs/manager_tab.py: inject runner provider via SessionManager constructor. 
  - tests/test_session_manager.py: added backoff recovery and escalation tests. 
- Verification: 
  - python -m pytest -q tests/test_session_manager.py tests/test_manager_tab_integration.py > 8 passed in 0.58s 
  - python -m pytest -q > 368 passed, 1 skipped in 11.79s
 
## [2026-02-23] Session 65 - Global Input Lock (timeout + JSONL events) 
- Changes: 
  - app/core/input_lock.py: added context-manager based GlobalInputManager and InputLockTimeoutError. 
  - app/core/runner.py: wired global input lock into keyboard/mouse physical input paths. 
  - app/core/runner.py: structured events added (input_lock_waiting/acquired/released/timeout). 
  - tests/test_input_lock_runner.py: added lock timeout and runner log behavior tests. 
- Verification: 
  - python -m pytest -q tests/test_input_lock_runner.py tests/test_runner_structured_jsonl.py tests/test_runner_logic.py > 27 passed in 5.64s 
  - python -m pytest -q > 371 passed, 1 skipped in 14.35s

## [2026-02-23] Session 66 - Data Orchestration V2 Step 2C (UI integration)
- Changes:
  - `app/main.py`
    - Added Excel orchestration UI controls (`Excel Data Mode`, file picker, parallelism, progress bar, status label).
    - Added run-path branching: Excel mode uses orchestrator flow while legacy single-macro `run_macro` path remains intact.
    - Integrated `JobQueueManager` + `SessionJobAdapter` + `ExcelDataLoader/ExcelResultExporter`.
    - Added signal-based runtime updates (`excelOrchEvent`, `excelOrchFinished`) and safe stop/close cleanup.
  - `tests/test_ui_orchestration_integration.py`
    - Added success-flow integration test (load Excel -> run adapters -> export output file).
    - Added stop-flow integration test (manual stop -> safe shutdown, no forced export).
- Verification:
  - `python -m pytest -q tests/test_ui_orchestration_integration.py tests/test_ui_integration.py tests/test_data_orchestration_v2.py tests/test_session_adapter_v2.py tests/test_excel_io.py` -> `41 passed in 6.02s`
  - `python -m pytest -q` -> `385 passed, 1 skipped in 16.75s`

## [2026-02-23] Session 67 - Total System Audit (binding/test integrity/concurrency)
- Changes:
  - Runtime binding path audit + repair
    - `app/main.py`: Excel fallback template selector fixed to use `StepData.type` and `keyboard_mode` (legacy `action_type`/`key_mode`도 호환).
    - `app/main.py`: Excel text output remains centralized via `TemplateProcessor`; unresolved placeholders fail fast.
  - Test integrity hardening
    - `tests/test_excel_payload_runner_template.py`: switched from ad-hoc namespace to real `StepData`; added keyboard-text fallback case.
    - `tests/test_ui_orchestration_integration.py`: added black-box fallback scenario (`{{user_name}}` from step template + Excel row value), and unresolved-placeholder failure scenario (no raw typing + FAILED export row).
    - `tests/test_integration_core_logic_patch_guard.py`: integration tests에서 핵심 바인딩/큐/락 경로 monkeypatch 금지 가드 추가.
  - Concurrency/retry effectiveness tests
    - `tests/test_data_orchestration_v2.py`: added retry-backoff timing gate and `is_fully_done` inflight strictness test.
    - `tests/test_input_lock_runner.py`: added two-runner concurrent execution serialization test (`max_active == 1`) for shared global input lock.
- Verification:
  - `python -m pytest -q tests/test_excel_payload_runner_template.py tests/test_ui_orchestration_integration.py tests/test_data_orchestration_v2.py tests/test_session_adapter_v2.py tests/test_input_lock_runner.py tests/test_integration_core_logic_patch_guard.py` -> `25 passed in 5.88s`
  - `python -m pytest -q` -> `397 passed, 1 skipped in 18.07s`

## [2026-02-23] Session 68 - Excel 멀티 워커 입력 직렬화(Global Input Lock)
- Summary:
  - `app/main.py` Excel payload runner 입력 경로에 전역 입력 락을 적용해 멀티 워커 간 키보드/클립보드 간섭을 차단.
  - 비-ASCII 텍스트(`Ctrl+V`)와 ASCII 타입라이트(`pyautogui.write`) 모두 lock acquire 범위 안에서 실행하도록 통일.
  - Hotkey Run이 기존 `run_macro()` 고정 호출을 우회하지 않도록 `_on_run_button_clicked()` 경유로 통일.
- Code:
  - `app/main.py`
    - `from .core.input_lock import get_global_input_manager` 추가
    - `_ExcelPayloadRunner.__init__`에 전역 입력 락 매니저/timeout 초기화
    - `_paste_text`를 `keyboard_paste` 락 범위로 감싸 clipboard set/paste/restore 전체를 원자화
    - ASCII `pyautogui.write`도 `keyboard_typewrite` 락 범위에서 실행
    - `_act_run_from_hotkey` -> `_on_run_button_clicked()` 호출로 분기 일치
  - `tests/test_excel_payload_runner_template.py`
    - `_FakeInputLockManager` 추가
    - `test_excel_payload_runner_ascii_write_is_locked` 추가
    - `test_excel_payload_runner_non_ascii_paste_is_locked` 추가
    - 기존 `test_excel_payload_runner_uses_clipboard_paste_for_non_ascii` 유지
- Verification:
  - `python -m pytest -q tests/test_excel_payload_runner_template.py tests/test_ui_orchestration_integration.py` -> `13 passed in 5.68s`
  - `python -m pytest -q` -> `402 passed, 1 skipped in 20.04s`

## [2026-02-23] Session 69 - Excel 모드 툴바 반응형 가시성 보강
- Summary:
  - 창 폭 축소 시 Excel 컨트롤이 사라지던 문제를 해결하기 위해 옵션 툴바를 가로 스크롤 컨테이너로 전환.
  - `Excel Data Mode`와 병렬도(`P:`)를 고정 크기/고정 정책으로 설정해 우선 가시성 보장.
  - 엑셀 경로 입력 필드는 `ElidedPathLineEdit`로 교체해 화면에는 말줄임 표시, 내부 값은 full path 유지.
- Code:
  - `app/main.py`
    - `ElidedPathLineEdit` 추가(`text()`는 full path 반환, 표시 텍스트는 `Qt.ElideRight`).
    - 옵션 툴바를 `QScrollArea + QHBoxLayout` 구조로 변경.
    - Excel 우선 컨트롤(`Excel Data Mode`, `P:`) 고정 크기 정책 적용.
  - `tests/test_excel_toolbar_responsive.py` 신규:
    - `test_excel_toolbar_priority_controls_are_fixed`
    - `test_excel_path_field_elides_but_keeps_full_text`
- Verification:
  - `python -m pytest -q tests/test_excel_toolbar_responsive.py tests/test_ui_orchestration_integration.py` -> `8 passed in 5.13s`

## [2026-02-23] Session 70 - Excel 템플릿 우선순위/대소문자 매핑 보강
- Summary:
  - Excel payload runner의 텍스트 결정 우선순위를 `스텝 템플릿 > payload(text/message)`로 변경.
  - `TemplateProcessor`에 대소문자 무시 placeholder lookup fallback을 추가해 `user_name`/`USER_NAME` 모두 매핑되도록 보강.
- Code:
  - `app/main.py`
    - `execute_job()`에서 먼저 `_get_excel_text_template()`를 렌더링하고, 템플릿이 없을 때만 payload(`text`/`message`) 사용.
  - `app/core/template_processor.py`
    - 키 exact match 실패 시 lower-case 맵 fallback으로 치환.
  - `tests/test_excel_payload_runner_template.py`
    - payload-only 경로 테스트 명확화(템플릿 없을 때)
    - 템플릿 우선 + 대소문자 무시 매핑 테스트 추가.
  - `tests/test_ui_orchestration_integration.py`
    - `USER_NAME` 템플릿이 message 열보다 우선 적용되는 UI 통합 테스트 추가.
- Verification:
  - `python -m pytest -q tests/test_template_processor.py tests/test_excel_payload_runner_template.py tests/test_ui_orchestration_integration.py` -> `17 passed in 5.30s`
  - `python -m pytest -q` -> `406 passed, 1 skipped in 20.40s`

## [2026-02-23] Session 71 - UI 현대화 Stage 2-1 PR-1 (조건부 액션 위저드 MVP)
- Summary:
  - Scenario 탭에 `조건 위저드` 버튼을 추가해 질문형 입력으로 OCR 조건 분기 스텝 생성을 지원.
  - 새 스키마 없이 기존 `StepData`만 조합해 `ocr_jump_if`, `jump_if`, `click_point`, `comment` 흐름을 생성.
  - 생성 스텝은 `AddStepsCommand`로 삽입되어 Undo/Redo 경로를 그대로 유지.
- Code:
  - `app/ui/dialogs.py`
    - `ConditionalActionWizardDialog` 추가(의도/텍스트/성공 동작/실패 동작 질문 UI).
    - 실패 경로 전용 `jump_if` 라우팅 스텝을 자동 생성해 성공 클릭 경로와 충돌하지 않도록 구성.
  - `app/main.py`
    - `btnConditionalWizard` 추가 및 `open_conditional_action_wizard()` 연결.
    - 위저드 생성 스텝을 시나리오 선택 다음(또는 끝)에 `AddStepsCommand`로 삽입.
  - `tests/test_conditional_wizard_generation.py` 신규:
    - 질문 조합별 생성 스텝 타입/타겟 매핑 검증
    - `AddStepsCommand` + `UndoStack` 호환 검증
    - 메인 버튼 클릭 삽입 경로 검증
- Verification:
  - `python -m pytest -q tests/test_conditional_wizard_generation.py` -> `4 passed in 0.48s`
  - `python -m pytest -q` -> `427 passed, 1 skipped in 20.52s`

## [2026-02-23] Session 72 - UI 현대화 Stage 2-1 PR-2 (시나리오 흐름/데이터 미리보기)
- Summary:
  - Scenario 스텝 카드에 분기/루프 흐름 힌트와 Excel 변수 미리보기를 표시하도록 리스트 렌더링 경로를 확장.
  - Excel 미리보기는 첫 데이터 행을 사용하며 placeholder 헤더 매핑은 대소문자 무시(`USER_NAME`/`user_name`)로 동작.
  - Excel 모드 토글/데이터 경로 변경 시 리스트를 즉시 재렌더링해 UI 표시가 실시간 동기화되도록 연결.
- Code:
  - `app/main.py`
    - `refresh_step_list`/`refresh_list_item`/`add_list_item`에 `flow_hint`, `excel_preview`, `tooltip` 전달 경로 추가.
    - `_extract_placeholders`, `_get_excel_preview_payload`, `_build_step_flow_hint`, `_build_step_excel_preview` 추가.
    - `chkExcelDataMode.toggled`, `edExcelDataPath.textChanged`를 미리보기 캐시 무효화 + 리스트 갱신 경로로 연결.
  - `app/ui/widgets.py`
    - `StepItemWidget`에 `flow_label`, `preview_label` 추가.
    - `StepList`에 동적 아이템 높이 계산(`_calc_item_height`) 및 hint/preview 기반 렌더링 추가.
  - `tests/test_scenario_flow_hints.py` 신규:
    - jump/loop 흐름 힌트 생성 검증.
    - Excel placeholder 미리보기(대소문자 무시 매핑) UI 반영 검증.
- Verification:
  - `python -m pytest -q tests/test_scenario_flow_hints.py tests/test_conditional_wizard_generation.py tests/test_excel_toolbar_responsive.py` -> `14 passed in 0.84s`
  - `python -m pytest -q` -> `429 passed, 1 skipped in 20.49s`

## [2026-02-23] Session 73 - UI 현대화 Stage 2-1 PR-3 (Flow Arrow Lane 시각화)
- Summary:
  - 시나리오 리스트 좌측에 jump/branch/loop 연결선을 그리는 `Flow Arrow Lane` 렌더링을 추가.
  - 기존 텍스트 흐름 힌트/Excel 미리보기는 유지하면서 카드 좌측 마진을 조정해 선/화살표와 겹치지 않도록 보강.
  - `refresh_step_list` 시 edge 집계를 수행해 리스트 위젯에 전달, 편집/갱신 시 즉시 재렌더링되도록 연결.
- Code:
  - `app/main.py`
    - `_collect_step_flow_edges()` 추가(`jump_if`, `ocr_jump_if`, `image_branch`, `end_loop` 대상 edge 수집).
    - `refresh_step_list`/`refresh_list_item`에서 `StepList.set_flow_edges(...)` 호출.
  - `app/ui/widgets.py`
    - `StepList.paintEvent()` 확장: edge별 색상선 + 방향 화살표 렌더링.
    - `StepItemWidget` 좌측 margin 확장(화살표 lane 확보).
    - `StepList.set_flow_edges()` 추가.
  - `tests/test_scenario_flow_hints.py`
    - 리스트 edge 집계(`jump_true`, `loop_back`) 검증 테스트 추가.
- Verification:
  - `python -m pytest -q tests/test_scenario_flow_hints.py tests/test_excel_toolbar_responsive.py tests/test_conditional_wizard_generation.py` -> `15 passed in 5.58s`
  - `python -m pytest -q` -> `430 passed, 1 skipped in 21.69s`

## [2026-02-24] Session 74 - 조건 위저드 의도 확장 (OCR 재시도/이미지 분기)
- Summary:
  - 조건 위저드 의도를 1종에서 3종으로 확장:
    - `특정 텍스트가 보이면 클릭`
    - `텍스트가 보이지 않으면 재시도 후 중단`
    - `이미지 확인 후 클릭/분기`
  - 의도 선택에 따라 입력 UI를 동적으로 노출(텍스트/이미지 경로/재시도 횟수/지연/타임아웃/성공·실패 라우팅).
  - Flow Arrow Lane edge 수집을 일반화해 `on_match_goto_id`, `branch_on_fail_goto_id` 기반 경로도 시각화.
- Code:
  - `app/ui/dialogs.py`
    - `ConditionalActionWizardDialog` 확장:
      - 의도별 액션 콤보 동적 구성
      - 이미지 경로 선택/검증
      - 재시도 설정 입력
      - 의도별 스텝 생성기 추가:
        - `_build_steps_ocr_text_then_click`
        - `_build_steps_ocr_retry_then_stop`
        - `_build_steps_image_check_then_click_branch`
  - `app/main.py`
    - `_collect_step_flow_edges`에 generic edge(`on_match_goto_id`, `branch_on_fail_goto_id`) 반영.
  - `tests/test_conditional_wizard_generation.py`
    - 재시도 의도/이미지 의도 스텝 생성 검증 추가.
  - `tests/test_scenario_flow_hints.py`
    - step-level success/fail goto edge 시각화 검증 추가.
- Verification:
  - `python -m pytest -q tests/test_conditional_wizard_generation.py tests/test_scenario_flow_hints.py tests/test_excel_toolbar_responsive.py` -> `18 passed in 1.14s`
  - `python -m pytest -q` -> `433 passed, 1 skipped in 21.76s`

## [2026-02-24] Session 75 - UI 현대화 Stage 2-2 PR-1 (실시간 Flow Preview)
- Summary:
  - 드래그 중 임시 순서를 받아 실시간 Flow Preview를 렌더링하는 경로를 추가.
  - Flow edge에 상태(`ok`, `self_jump`, `dangling`)를 부여하고, 상태별 색상/점선 경고를 적용.
  - Drop/drag-leave 시 프리뷰를 해제하고 최종 `sync_order()` 경로와 충돌 없이 정리되도록 연결.
- Code:
  - `app/ui/widgets.py`
    - `flowPreviewRequested = pyqtSignal(list)` 추가.
    - `dragMoveEvent`에 30ms throttle + 임시 순서 계산(`_build_drag_preview_order`) 구현.
    - `dropEvent`/`dragLeaveEvent`에서 프리뷰 해제 emit.
    - `set_flow_edges`/`paintEvent` 확장: status 기반 렌더(`self_jump` 주황, `dangling` 빨강 점선).
  - `app/main.py`
    - `_build_flow_preview_edges(temp_steps)` 추가:
      - 상태 판정(`ok/self_jump/dangling`)
      - `(order_hash, edge_source_hash)` 캐시 적용.
    - `_on_flow_preview_requested(preview_rows)` 추가:
      - 임시 순서 렌더 적용/해제.
    - `StepList.flowPreviewRequested` 연결 + reorder 후 프리뷰 상태 정리.
  - `tests/test_visual_drag_drop_logic.py` 신규:
    - 상태 판정 정확성 검증(`ok/self_jump/dangling`).
    - preview cache hit 검증.
    - preview apply/clear 동작 검증.
  - `tests/test_scenario_flow_hints.py`
    - edge 튜플 포맷(상태 포함) 기대값 갱신.
- Verification:
  - `python -m pytest -q tests/test_visual_drag_drop_logic.py tests/test_scenario_flow_hints.py tests/test_conditional_wizard_generation.py tests/test_excel_toolbar_responsive.py` -> `21 passed in 1.80s`
  - `python -m pytest -q` -> `436 passed, 1 skipped in 22.25s`

## [2026-02-24] Session 76 - UI 현대화 Stage 2-2 PR-2 (Logic Path Simulator)
- Summary:
  - 실제 실행 없이 현재 스텝/엑셀 컨텍스트 기준의 예상 실행 경로를 계산하는 `LogicPathSimulator`를 추가.
  - Scenario 탭에 `경로 시뮬레이션` 버튼과 `센서 성공 가정` 토글을 추가해 OCR/이미지 의존 분기를 가상 실행 가능하게 구성.
  - 시뮬레이션 결과 방문 스텝을 청록색으로 하이라이트하고, 경로/경고를 로그창에 출력.
- Code:
  - `app/core/logic_path_simulator.py` 신규:
    - `SimulationReport`, `SimulationTransition`, `LogicPathSimulator` 구현.
    - 지원 경로:
      - `jump_if`, `ocr_jump_if`, `image_branch`
      - sensor-step(`wait_for_image`, `ocr_check_text`, `image_click`, `pixel_check`, `compare_images`)의 match/fail 분기
      - `start_loop`/`end_loop` loop counter 추적
      - `max_hops` 종료 가드
  - `app/main.py`
    - `run_logic_simulation()`, `_build_simulation_context()`, `clear_logic_simulation_highlight()` 추가.
    - Scenario 탭 버튼/체크박스 추가:
      - `btnSimulate`
      - `chkSensorAssume`
    - 시뮬레이션 결과를 `StepList.set_simulated_indices()`로 하이라이트 연동.
  - `app/ui/widgets.py`
    - `StepItemWidget`에 simulated 시각 상태(청록 배경) 추가.
    - `StepList.set_simulated_indices()` 추가.
  - `tests/test_logic_path_simulator.py` 신규:
    - jump_if 컨텍스트 분기 검증.
    - 무한 루프 `max_hops` 가드 검증.
    - MainWindow 시뮬레이션 실행 시 하이라이트 반영 검증.
- Verification:
  - `python -m pytest -q tests/test_logic_path_simulator.py tests/test_visual_drag_drop_logic.py tests/test_scenario_flow_hints.py tests/test_conditional_wizard_generation.py tests/test_excel_toolbar_responsive.py` -> `24 passed in 1.24s`
  - `python -m pytest -q` -> `439 passed, 1 skipped in 21.09s`

## [2026-02-24] Session 77 - UI 현대화 Stage 2-2 PR-3 (Smart Snap)
- Summary:
  - 위저드 세트 스텝 보호를 위해 Smart Snap 로직을 `sync_order()` 경로에 추가.
  - `collect_step_group(seed_index)` 유틸로 `WZ` 마커 + 내부 참조 ID를 결합해 논리 그룹을 추론.
  - 세트 일부만 드래그해도 그룹 전체를 블록 이동으로 보정하고, 재배치 후 legacy 인덱스 필드를 자동 재정규화.
  - 그룹 분리/댕글링 연결 발생 시 Flow Arrow Lane 경고 edge와 토스트/상태바 경고를 즉시 노출.
- Code:
  - `app/main.py`
    - Smart Snap 옵션 플래그(`chkSmartSnap`) 추가 및 `QSettings` 로드/저장 연동.
    - 그룹 추론/보정 유틸 추가:
      - `_smart_snap_enabled`
      - `_step_has_wz_marker`
      - `_extract_step_ref_ids`
      - `collect_step_group`
      - `_collect_wz_groups`
      - `_normalize_legacy_jump_indices`
      - `_apply_smart_snap_reorder`
    - `sync_order` 확장:
      - Smart Snap 재배치 적용
      - focus step 유지
      - 경고 조건 시 Flow warning edge + 토스트/상태바 알림.
  - `tests/test_smart_snap_logic.py` 신규:
    - WZ 그룹 인식 검증.
    - 세트 동반 이동 + legacy 인덱스 재정규화 검증.
    - dangling 경고 edge 렌더링 검증.
- Verification:
  - `python -m pytest -q tests/test_smart_snap_logic.py tests/test_visual_drag_drop_logic.py tests/test_main_trigger_scheduler_integration.py` -> `28 passed in 2.47s`
  - `python -m pytest -q tests/test_conditional_wizard_generation.py` -> `6 passed in 0.51s`
  - `python -m pytest -q` -> `442 passed, 1 skipped in 20.98s`

## [2026-02-24] Session 78 - UI 현대화 Stage 3-1 PR-1 (Visual Image Capturer)
- Summary:
  - 초보자용 드래그 캡처 기반 이미지 스텝 생성 기능을 추가.
  - 툴바 `스마트 캡처` 버튼에서 `이미지 클릭 스텝`/`이미지 대기 스텝`을 선택해 즉시 생성 가능.
  - 캡처 오버레이는 실시간 좌표/크기(`X,Y,W,H`)를 표시하며 ESC/우클릭 취소를 지원.
- Code:
  - `app/ui/overlay.py` 신규:
    - `VisualImageCaptureOverlay` 구현(반투명 오버레이, 드래그 선택, 좌표/크기 HUD, 취소/완료 시그널).
    - `capture_from_screen()` 정적 진입점 제공.
  - `app/main.py`:
    - Core 툴바에 `btnSmartCapture` 추가 + 실행 중 자동 비활성화(`_sync_toolbar_run_stop_buttons`).
    - 캡처 처리 경로 추가:
      - `_open_smart_capture_menu`
      - `_run_visual_capture`
      - `_resolve_visual_capture_image_dir`
      - `_build_visual_capture_step`
    - 캡처 이미지를 `images/smart_capture_*.png`로 저장 후 `AddStepsCommand`로 시나리오 삽입.
  - `tests/test_visual_capturer.py` 신규:
    - 캡처 좌표 -> 생성 스텝 좌표 매핑 검증.
    - 이미지 파일 생성/경로 연결 무결성 검증.
    - 실행 중 캡처 차단 검증.
- Verification:
  - `python -m pytest -q tests/test_visual_capturer.py tests/test_excel_toolbar_responsive.py tests/test_main_trigger_scheduler_integration.py` -> `33 passed in 2.60s`
  - `python -m pytest -q` -> `445 passed, 1 skipped in 21.21s`

## [2026-02-24] Session 79 - UI 현대화 Stage 3-2 PR-3-2-1 (Coordinate Guide Overlay 코어)
- Summary:
  - 스텝 좌표를 실제 화면 위에 표시하는 좌표 가이드 오버레이 코어를 추가.
  - 십자선/레이저 포인트/`#번호 타입` 라벨 렌더링과 `bbox` 점선 박스(옵션) 렌더링을 지원.
  - 오버레이는 마우스 클릭 관통(`WA_TransparentForMouseEvents`)과 공유 인스턴스 재사용(`get_shared`) 경로를 제공.
- Code:
  - `app/ui/overlay.py`:
    - `CoordinateGuideOverlay` 추가.
    - API: `show_marker(...)`, `clear_marker()`, `to_overlay_point(...)`, `get_shared(...)`.
    - DPI/가상 화면 보정: `_detect_physical_bounds()`, `_refresh_geometry_and_scale()` 구현.
  - `tests/test_coordinate_overlay_mapping.py` 신규:
    - `show_marker` payload 저장 상태 검증.
    - 클릭 관통 속성(`WA_TransparentForMouseEvents`) 검증.
    - 공유 인스턴스 재사용 검증.
- Verification:
  - `python -m pytest -q tests/test_coordinate_overlay_mapping.py tests/test_visual_capturer.py` -> `6 passed in 2.36s`
  - `python -m pytest -q` -> `448 passed, 1 skipped in 25.25s`

## [2026-02-24] Session 80 - UI 현대화 Stage 3-2 PR-3-2-2 (StepList 좌표 프리뷰 이벤트 발행)
- Summary:
  - `StepList`에 좌표 프리뷰 전용 신호(`coordinatePreviewRequested`, `coordinatePreviewCleared`)를 추가.
  - Hover(`itemEntered`)와 Selection(`currentItemChanged`)에서 좌표 스텝 payload를 송출하도록 구현.
  - 좌표 없는 스텝 선택/리스트 이탈 시 clear 신호를 emit하여 오버레이 잔상 경로를 정리.
  - 동일 payload 재발행을 signature 캐시로 억제해 빠른 포인터 이동 시 불필요한 이벤트를 줄임.
- Code:
  - `app/ui/widgets.py`:
    - 신호 추가: `coordinatePreviewRequested(dict)`, `coordinatePreviewCleared()`.
    - 이벤트 핸들러 추가: `_on_item_entered`, `_on_current_item_changed`, `leaveEvent`.
    - payload 추출/필터링: `_extract_coordinate_payload`, `_emit_coordinate_preview_for_item`.
    - 좌표 필드(`click_x`, `click_y`) 기반 스텝만 송출, optional `image_path` 포함.
  - `tests/test_coordinate_overlay_mapping.py` 확장:
    - 좌표 스텝 선택 시 `coordinatePreviewRequested` payload 검증.
    - 무좌표 스텝 선택 전환 시 `coordinatePreviewCleared` 신호 검증.
- Verification:
  - `python -m pytest -q tests/test_coordinate_overlay_mapping.py tests/test_visual_drag_drop_logic.py` -> `8 passed in 1.14s`
  - `python -m pytest -q` -> `450 passed, 1 skipped in 21.63s`

## [2026-02-24] Session 81 - UI 현대화 Stage 3-2 PR-3-2-3 (MainWindow 오버레이 라우팅)
- Summary:
  - `MainWindow`에 StepList 좌표 이벤트 라우팅을 연결해 Coordinate Guide Overlay를 실제 표시/해제.
  - `image_click` 프리뷰에서 템플릿 이미지 크기(`image_path`/`png_bytes`)를 캐시 로드해 bbox(`W,H`) 전달.
  - 매크로/Excel 실행 중 좌표 프리뷰를 차단하고, 시작 시 clear/완료 시 복구되도록 실행 가드를 추가.
- Code:
  - `app/main.py`:
    - StepList 신호 연결: `coordinatePreviewRequested -> _on_coordinate_preview_requested`, `coordinatePreviewCleared -> _clear_coordinate_preview`.
    - 오버레이 라우팅 메서드 추가:
      - `_get_coordinate_overlay`
      - `_set_coordinate_preview_suspended`
      - `_is_coordinate_preview_blocked`
      - `_load_image_size_cached`
      - `_resolve_coordinate_preview_bbox`
      - `_on_coordinate_preview_requested`
      - `_clear_coordinate_preview`
    - 실행 경로 보호:
      - `run_macro` 시작 시 preview suspend + 시작 실패 시 restore
      - `_on_macro_finished`에서 restore
      - `run_excel_orchestration` 시작 시 suspend
      - `_on_excel_orch_finished` 경로에서 restore
  - `app/ui/overlay.py`:
    - `CoordinateGuideOverlay.show_marker`가 `bbox=(W,H)` 2튜플 입력을 지원하도록 확장.
  - `tests/test_coordinate_overlay_mapping.py` 확장:
    - MainWindow에서 StepList 선택 시 overlay `show_marker` 호출 검증
    - 실행 상태 플래그(`_excel_mode_running`/runner running)에서 프리뷰 차단 검증
    - `image_click`에서 bbox 크기 전달 검증
- Verification:
  - `python -m pytest -q tests/test_coordinate_overlay_mapping.py tests/test_excel_toolbar_responsive.py` -> `16 passed in 1.93s`
  - `python -m pytest -q` -> `453 passed, 1 skipped in 21.75s`

## [2026-02-24] Session 82 - UI 현대화 Stage 3-3 PR-3-3-1 (Recorder Raw Stream + Self-Filter)
- Summary:
  - `InputRecorder`에 `raw_event_received(dict)`, `control_event_received(str)` 채널을 추가해 Smart Recorder용 Raw Event 스트림을 확보.
  - `lock_hwnd`를 기준으로 HWND 루트 비교 필터를 적용해 앱 자체 UI 이벤트(셀프 캡처)를 기록/송출에서 제외.
  - ESC/F12를 제어 이벤트(`stop_hotkey`)로 소비하도록 처리해 스텝 변환에서 제외.
  - 세션 시작/종료 시 큐/버퍼/리스너를 재초기화하고 worker stop 경로를 보강해 세션 안정성을 개선.
- Code:
  - `app/core/recorder.py`:
    - Win32 HWND 조회/정규화 헬퍼(`_window_from_point`, `_foreground_hwnd`, `_normalize_hwnd`) 추가
    - 셀프-캡처 필터(`_is_self_capture_hwnd`) 추가
    - Raw/Control 이벤트 emit 헬퍼(`_emit_raw_event`, `_emit_control_event`) 추가
    - `_on_key_press/_on_key_release/_on_click`에 표준 Raw payload 송출 및 stop hotkey 소비 로직 추가
    - `_on_move/_on_scroll`에 self-window 제외 가드 추가
    - `start/stop/_process_queue`에 큐/리스너 정리 로직 보강
  - `tests/test_smart_recorder_core.py`(신규):
    - self-window click exclusion 검증
    - ESC stop hotkey consume(스텝 비기록) 검증
    - raw callback 예외 swallow + raw payload 송출 검증
- Verification:
  - `python -m pytest -q tests/test_smart_recorder_core.py` -> `3 passed in 0.10s`
  - `python -m pytest -q` -> `456 passed, 1 skipped in 22.15s`

## [2026-02-24] Session 83 - UI 현대화 Stage 3-3 PR-3-3-2 (Smart Transformer)
- Summary:
  - Raw Event 기반 지능형 변환 코어 `SmartTransformer`를 추가해 텍스트 병합/분리 로직을 구현.
  - 클릭 release 이벤트 시 `click_point`와 `image_click`을 동시 제안하는 `SmartProposal` 생성 경로를 추가.
- Code:
  - `app/core/smart_recorder.py`(신규):
    - `SmartStep`, `SmartProposal`, `SmartTransformer` 구현
    - 텍스트 병합:
      - 연속 printable 키는 버퍼 병합
      - flush 조건: 이동/수정 키, modifier(ctrl/alt/win), typed gap(기본 1.5초), finalize
    - 클릭 시각 제안:
      - 클릭 좌표 주변 캡처(기본 60x60) -> `images/record_prop_*.png` 저장
      - `click_point` + `image_click` 제안 객체 동시 반환
  - `tests/test_smart_recorder_transformer.py`(신규):
    - `Hello` 연속 입력이 `type_text` 1개로 병합되는지 검증
    - `Hello + LeftArrow + !`가 `type_text / key_press / type_text`로 분리되는지 검증
    - 클릭 이벤트에서 듀얼 제안과 이미지 파일 생성이 정상인지 검증
- Verification:
  - `python -m pytest -q tests/test_smart_recorder_transformer.py tests/test_smart_recorder_core.py` -> `6 passed in 0.19s`
  - `python -m pytest -q` -> `459 passed, 1 skipped in 25.98s`

## [2026-02-24] Session 84 - UI 현대화 Stage 3-3 PR-3-3-3 (MainWindow Smart Recorder 통합)
- Summary:
  - `MainWindow` 녹화 파이프라인에 `SmartTransformer`를 연결하여 Raw Event -> SmartStep/SmartProposal 변환 흐름을 활성화.
  - 녹화 종료 시 `transformer.finalize()` 결과를 포함해 최종 스텝을 구성하고, 제안(좌표/이미지/개별/취소) 선택 UI를 추가.
  - 확정된 스텝은 `AddStepsCommand`로 현재 선택 위치 다음에 batch 삽입하고, 삽입된 스텝 범위를 자동 선택 하이라이트.
  - 제안에서 미채택된 임시 이미지(`record_prop_*.png`)는 자동 정리해 누수 방지.
- Code:
  - `app/main.py`:
    - `_start_record`에서 `SmartTransformer` 초기화 + `raw_event_received/control_event_received` 연결
    - `_on_record_raw_event`, `_on_record_control_event` 추가
    - `_choose_record_proposal_mode`, `_choose_individual_proposal_step`, `_materialize_recorded_steps` 추가
    - `_cleanup_record_temp_images`, `_record_insert_index`, `_highlight_inserted_steps` 추가
    - `_on_record_done`에서 smart 결과 finalize/materialize 후 `AddStepsCommand` 삽입 경로로 통합
  - `tests/test_ui_integration.py` 확장:
    - 녹화 종료 시 `AddStepsCommand` 호출/삽입 인덱스/결과 타입 검증
    - 제안 선택(이미지 선택)이 최종 `StepData`에 반영되는지 검증
- Verification:
  - `python -m pytest -q tests/test_ui_integration.py tests/test_smart_recorder_transformer.py tests/test_smart_recorder_core.py` -> `35 passed in 1.61s`
  - `python -m pytest -q` -> `461 passed, 1 skipped in 23.97s`

## [2026-02-24] Session 85 - UI 현대화 Stage 3-3 PR-3-3-4 (Recording Overlay/HUD)
- Summary:
  - 녹화 상태 HUD(`RecordingStatusOverlay`)를 추가해 `Recording...` 상태와 스텝 카운트를 우측 상단에 실시간 표시.
  - Raw click 이벤트를 오버레이로 전달해 클릭 지점에 Ripple 애니메이션을 렌더링.
  - MainWindow 녹화 파이프라인과 HUD를 연동:
    - 녹화 시작 시 HUD show + count reset
    - SmartTransformer 출력 발생 시 HUD count update
    - 녹화 중지/종료 시 HUD hide
  - 공유 오버레이 인스턴스 stale 포인터(RuntimeError) 문제를 `get_shared()` 재생성 가드로 보강.
- Code:
  - `app/ui/overlay.py`:
    - `RecordingStatusOverlay` 신규 구현
    - `set_recording`, `set_step_count`, `trigger_click_ripple` API 추가
    - `CoordinateGuideOverlay.get_shared` / `RecordingStatusOverlay.get_shared`에 삭제된 공유 인스턴스 재생성 가드 추가
  - `app/main.py`:
    - `RecordingStatusOverlay` import 및 `_get_recording_overlay`/HUD 제어 메서드 추가
    - `_start_record`, `_stop_record`, `_on_record_raw_event`, `_on_record_done`, `closeEvent`에 HUD 연동
  - `tests/test_recording_integration.py`(신규):
    - 녹화 시작/종료 시 HUD 가시성 검증
    - 클릭 raw event 발생 시 ripple 트리거 전달 검증
- Verification:
  - `python -m pytest -q tests/test_recording_integration.py tests/test_ui_integration.py tests/test_smart_recorder_transformer.py tests/test_smart_recorder_core.py` -> `37 passed in 1.16s`
  - `python -m pytest -q` -> `463 passed, 1 skipped in 21.14s`

## [2026-02-24] Session 86 - UI 현대화 Stage 3-3 PR-3-3-5 (최종 검증/정비)
- Summary:
  - 녹화 배치 삽입 경로를 기록 전용 커맨드(`AddRecordedStepsCommand`)로 강화해 Undo/Redo 시 이미지 임시 자산 롤백/복원을 보장.
  - 녹화 취소/예외/종료 경로의 임시 이미지(`record_prop_*.png`) 정리 경로를 테스트로 검증.
  - Stage 3-3의 핵심 축(원시 이벤트 수집, Smart 변환, 제안 선택, HUD 피드백, cleanup/rollback)을 통합 검증 완료.
- Code:
  - `app/core/commands.py`:
    - `AddRecordedStepsCommand` 신규 추가
      - `undo()`: 스텝 제거 + 미참조 관리 이미지 파일 삭제
      - `execute()`: 누락 이미지 파일을 캐시 바이트로 복원 후 삽입(redo-safe)
  - `app/core/smart_recorder.py`:
    - `image_click` 제안 스텝 생성 시 `png_bytes` 동시 보관(복원 소스)
  - `app/main.py`:
    - `_on_record_done`에서 image proposal이 포함되면 `AddRecordedStepsCommand` 사용
  - `tests/test_final_cleanup_guard.py`(신규):
    - 녹화 취소 시 `record_prop_*` 파일 삭제 검증
    - 배치 삽입 후 Undo 시 파일 삭제/Redo 시 파일 복원 + 스텝 복원 검증
- Verification:
  - `python -m pytest -q tests/test_final_cleanup_guard.py tests/test_recording_integration.py tests/test_ui_integration.py tests/test_smart_recorder_transformer.py tests/test_smart_recorder_core.py` -> `39 passed in 5.79s`
  - `python -m pytest -q` -> `465 passed, 1 skipped in 23.96s`
## Session 87 - UI Stage 3-4 PR-3-4-1 (Toolbar Cleanup / Smart Capture Relocation)
- Removed duplicate top-toolbar `Run/Stop` buttons in `app/main.py`.
- Moved `Smart Capture` button to the left scenario action panel (`스마트 캡처 (Ctrl+Alt+S)`).
- Slimmed left action button density via shared `32px` min-height helper and reduced per-button inline style reliance.
- Unified left stop dispatch path to `_on_stop_button_clicked`.
- Updated responsive toolbar tests to validate new layout contract.
- Test status:
  - `python -m pytest -q tests/test_excel_toolbar_responsive.py` -> `9 passed`
  - `python -m pytest -q` -> `466 passed, 1 skipped`
## Session 88 - UI Stage 3-4 PR-3-4-2 (Style Unification / Minimal Design)
- Removed inline color styles from left scenario action buttons in `app/main.py`; migrated to class-property based styling.
- Added role-based button classes and centralized palette in `app/ui/styles.py`.
- Updated pause/resume run-button visual switch to dynamic class (`left-run` <-> `left-run-paused`) instead of inline stylesheet string swap.
- Slimmed toolbar style (lighter bottom border, smaller spacing/padding) for minimal look.
- Test status:
  - `python -m pytest -q tests/test_excel_toolbar_responsive.py tests/test_ui_integration.py` -> `38 passed`
  - `python -m pytest -q` -> `466 passed, 1 skipped`
## Session 89 - UI Stage 3-4 PR-3-4-3 (3-Column Micro Grid)
- Left scenario action panel switched to compact 3-column grid layout.
- Button size reduced to micro density (`minimumHeight=26`), spacing tightened (`2`), margins removed.
- Action label text shortened for small form factor (`동작+`, `캡처`, `분기`, `주석`, `마법사`, `조건`, `시뮬`).
- Global button style updated in `app/ui/styles.py`:
  - `font-size: 9pt`
  - `padding: 1px 3px`
  - `border-radius: 2px`
- Test status:
  - `python -m pytest -q tests/test_excel_toolbar_responsive.py tests/test_ui_integration.py` -> `38 passed`
  - `python -m pytest -q` -> `466 passed, 1 skipped`
## Session 90 - UI Stage 3-5 PR-3-5-1 (MenuBar Refactor / Toolbar Simplification)
- Moved file/edit core operations to menu bar:
  - `File`: Open (`Ctrl+O`), Save (`Ctrl+S`)
  - `Edit`: Undo (`Ctrl+Z`), Redo (`Ctrl+Y`)
- Removed toolbar icon action group for Save/Open/Undo/Redo from `app/main.py`.
- Added menu styling in `app/ui/styles.py` (`QMenuBar`, `QMenu`, selected highlight).
- Added tests in `tests/test_excel_toolbar_responsive.py`:
  - menu action wiring dispatch validation
  - toolbar icon group removal validation
- Test status:
  - `python -m pytest -q tests/test_excel_toolbar_responsive.py tests/test_ui_integration.py` -> `40 passed`
  - `python -m pytest -q` -> `468 passed, 1 skipped`
## Session 91 - UI Stage 3-5 PR-3-5-3 (Panel Min-Width + Snap Collapse)
- Added left-panel snap collapse logic in `app/main.py`:
  - splitter index 0 set collapsible
  - auto-collapse to width 0 when below threshold (`_left_panel_snap_threshold_px=80`)
  - guard flag to avoid recursive `splitterMoved` loops
- Relaxed min-width constraints:
  - `app/ui/tabs/manager_tab.py`: containers/table/inputs/buttons configured for narrow shrink
  - `app/main.py` trigger tab root/list/buttons configured for narrow shrink
  - global button style allows `min-width: 0px`
- Added/updated tests in `tests/test_excel_toolbar_responsive.py`:
  - left splitter collapsible + snap behavior
  - manager/trigger min-width relaxation checks
- Test status:
  - `python -m pytest -q tests/test_excel_toolbar_responsive.py tests/test_ui_integration.py` -> `42 passed`
  - `python -m pytest -q` -> `470 passed, 1 skipped`

## Session 92 - Git Governance Hard Gate (Hook Enforcement)
- Added repository-managed Git hook guards:
  - `.githooks/commit-msg`: validates mandatory commit metadata sections and tests lines.
  - `.githooks/pre-commit`: blocks constitutional file delete/rename/copy and staged runtime artifacts.
- Added guard implementation/utilities:
  - `tools/git_hook_guards.py` (shared validators + hook entrypoints)
  - `tools/install_git_hooks.py` (`core.hooksPath=.githooks` installer)
- Added tests:
  - `tests/test_git_hook_guards.py` (commit message validation, staged-name-status checks)
- Updated governance docs:
  - `AGENTS.md` + `.cursorrules` with mandatory hook install/enforcement lines.
  - `.gitignore` includes `logs/run_events_*.jsonl`.

## Session 93 - Governance Escalation (Hard Enforcement Upgrade)
- Strengthened hook governance from advisory to enforced gate:
  - `pre-commit` now blocks:
    - any staged change under `backups/`
    - mixed constitutional + non-constitutional staging
    - commit without fresh `.git/post_task_gate.json` proof (HEAD/staged-hash match required)
  - `post-task gate` script added:
    - `python tools/post_task_gate.py --targeted "<targeted pytest command>"`
    - auto-runs full suite when risk trigger is active
    - writes proof record consumed by `pre-commit`
  - `pre-push` added:
    - runs rule guard tests (`docs sync`, `steps mutation`, `hook guards`)
- Added unit tests for new guard logic in `tests/test_git_hook_guards.py`.

## Session 94 - Governance P0 Backstop (Commit/Gate Match + CI Server Gate)
- `commit-msg` hardening:
  - Commit `Tests` lines must match summaries recorded in `.git/post_task_gate.json`.
  - Prevents fabricated/stale test summaries in commit messages.
- CI backstop for `--no-verify` bypass:
  - Added `tools/ci_governance_guard.py`.
  - CI now validates commit-message schema and commit-level file-policy across commit range.
  - `.github/workflows/ci.yml` runs governance guard before pytest.
- Extended guard tests:
  - `tests/test_git_hook_guards.py` adds tests for tests-line extraction and gate-summary matching.

## Session 95 - DX Workflow Optimization (Auto Targeted + Atomic Scope + CI Parallel)
- Added auto targeted test selector:
  - `tools/test_selector.py` maps changed paths -> related pytest targets.
  - `tools/post_task_gate.py` now supports `--targeted auto`.
- Refined risk-based full suite trigger:
  - high-risk paths only: `thread/signal/runner/StepData/serialization/BaseCommand/UndoStack`.
- Added staged scope hard guard:
  - `pre-commit` now blocks oversized staged scope (file/line threshold) to enforce atomic commits.
- Added standardized finish flow:
  - `tools/task_finish.py` runs post-task gate and writes `.git/TASK_COMMIT_TEMPLATE.md`.
- Added repo cleanup utility and applied tracked artifact cleanup:
  - `tools/cleanup_repo_artifacts.py` (`--apply` removes tracked artifacts from index only).
  - cleaned tracked `__pycache__`, `*.pyc`, `logs/*.jsonl` from Git index.
- CI optimization:
  - `.github/workflows/ci.yml` split into `changes`/`rule-guard`/`pytest` jobs.
  - path filtering + pip cache + parallelizable guard/pytest paths.
- Added tests:
  - `tests/test_test_selector.py`
  - `tests/test_task_finish.py`
  - `tests/test_post_task_gate.py`
  - `tests/test_ci_governance_guard.py`
  - expanded `tests/test_git_hook_guards.py`

## Session 96 - DX Guard Phase 
- Added tools/task_start_guard.py to block starting new work when staged entries exist.
- Added atomic cleanup rule: 10+ artifact deletions must be isolated in chore(cleanup) commit.
- Hardened post_task_gate.py: fail when app code changed but auto-targeted tests resolve to zero.
- Tests: targeted 31 passed in 0.11s; full suite 505 passed, 1 skipped in 21.68s.

## Session 97 - DX Guard Phase Two
- Added 30-minute gate freshness TTL via timestamp in post_task_gate record.
- Strengthened commit-msg validation with mandatory Scope label values.
- task_finish now recommends scope and writes Scope line in commit template.
- Tests: targeted 39 passed in 0.38s; full suite 509 passed, 1 skipped in 31.24s.
- Risk trigger now ignores artifact paths to avoid unnecessary full-suite runs on cleanup-only changes.
- Updated tests: targeted 40 passed in 0.27s; full suite 510 passed, 1 skipped in 22.31s.

## Session 98 - DX Phase Three
- CI workflow keeps rule-guard and pytest as parallel jobs and now uses actions/cache for pip cache restore.
- Added pre-commit scope-size warning thresholds: file count 7, line count 500.
- Added preflight environment check tool and task_finish preflight execution gate.
- Tests: targeted 40 passed in 0.20s; full suite 518 passed, 1 skipped in 21.44s.
 
- CI workflow keeps rule-guard and pytest as parallel jobs and now uses actions/cache for pip cache restore. 
- Added scope-size warning thresholds in pre-commit: file count 7, line count 500. 
- Added preflight environment check tool and task_finish preflight execution gate. 
- Tests: targeted 44 passed in 0.28s; full suite 517 passed, 1 skipped in 21.59s.
## Session 97 - Stage 3-5 PR-3-5-2 (Toolbar Grouping Cleanup)
- Date: 2026-02-26
- Summary:
  - 상단 옵션 툴바를 `Targeting / Flags / Excel` 3개 논리 그룹으로 재배치.
  - 그룹 사이 `VLine` 구분선을 추가해 시각적 경계를 명확화.
  - 툴바 체크박스 라벨을 축약(`Debug`, `Human`, `Dry`, `Mini`, `CapFail`, `Snap`).
  - 툴바 입력 위젯 높이를 버튼 높이와 일치하도록 정렬(주요 입력 26px).
  - Excel 그룹(`optExcelGroup`)에 전용 스타일(옅은 배경/테두리) 적용.
- Validation:
  - `python -m pytest -q tests/test_excel_toolbar_responsive.py` -> `13 passed in 2.72s`
  - `python -m pytest -q tests/test_ui_integration.py` -> `29 passed in 1.49s`

## Session 99 - Stage 4 PR-4-1 (커스텀 예외 계층/엔진 가드 강화)
- Date: 2026-02-26
- Summary:
  - `app/core/exceptions.py` 신규 추가:
    - `MacroBaseError`, `ExecutionError`, `ResourceError`, `ActionError`, `TargetWindowError`.
  - `app/core/runner.py` 예외 처리 고도화:
    - 스텝 예외 분류(`_to_macro_error`) 및 정밀 텔레메트리(`step_exception`: `step_index`, `exception_type`) 추가.
    - 실행 루프 예외 텔레메트리(`run_exception`) 추가.
    - 실행 종료 `finally`에서 입력 해제 + 상태 `engine_state=IDLE` 강제 복구.
    - 리소스 가드(`_validate_step_resources`)로 이미지/비교 리소스 누락을 실행 전에 포착.
    - 타겟 창 활성화 실패를 `TargetWindowError` 타입 이벤트로 기록.
  - `tests/test_exceptions.py` 신규 추가:
    - 예외 계층 구조 검증
    - 리소스 예외 검증
    - 타겟 창 예외 텔레메트리 검증
    - 스텝 예외 텔레메트리(`step_index`/`exception_type`) 및 IDLE 복구 검증
- Validation:
  - `python -m pytest -q tests/test_exceptions.py tests/test_runner_logic.py::test_normalize_step_template_path_uses_macro_base tests/test_window_integration.py tests/test_input_lock_runner.py` -> `15 passed in 4.58s`
  - `python -m pytest -q` -> `522 passed, 1 skipped in 37.29s`

## Session 100 - Stage 4 Patch (동적 리소스 경로 precheck 보정)
- Date: 2026-02-26
- Summary:
  - `app/core/runner.py`
    - `_validate_step_resources`에 동적 경로 스킵 규칙을 추가.
    - `{{...}}`, `#`, `@`, `?` 토큰이 포함된 경로는 런타임 치환을 전제로 precheck를 생략.
    - 정적 경로는 기존 존재 검사 유지(누락 시 `ResourceError`).
  - `tests/test_exceptions.py`
    - 동적 템플릿 경로 precheck 스킵 테스트 추가.
    - 동적 `compare_images` 경로 precheck 스킵 테스트 추가.
- Validation:
  - `python -m pytest -q tests/test_exceptions.py` -> `6 passed in 2.18s`
  - `python -m pytest -q` -> `524 passed, 1 skipped in 37.01s`

## Session 101 - Stage 4 PR-4-2 (Self-Healing Retry / Recovery)
- Date: 2026-02-26
- Summary:
  - `app/core/runner.py`
    - 이미지 계열 스텝(`image_click`, `wait_for_image`, `image_branch`, `compare_images`)의 `ResourceError`에 대해 bounded retry 추가.
    - 재시도 텔레메트리 추가:
      - `step_retry` (attempt/max/delay/exception)
      - `step_retry_success` (최종 성공 시 재시도 횟수)
    - `ActionError` 발생 시 self-heal 복구 루틴 추가:
      - 런타임 입력 해제
      - non-dry-run에서 ESC 입력 + 마우스 홈 이동(10,10)
      - 복구 결과 `step_recovery` 이벤트 기록
  - `tests/test_exceptions.py`
    - 일시적 `ResourceError` 이후 재시도 성공 시나리오 검증
    - `ActionError` 시 `step_recovery` 이벤트 검증
- Validation:
  - `python -m pytest -q tests/test_exceptions.py` -> `8 passed in 4.04s`
  - `python -m pytest -q` -> `526 passed, 1 skipped in 40.94s`

## Session 102 - Governance Automation / Asset Management System
- Date: 2026-02-26
- Summary:
  - 루트 자산 지도 `ASSET_MAP.md` 신설(코드/규칙/도구/문서/CI 인벤토리 표준화).
  - 감사 스크립트 `tools/project_audit.py` 추가:
    - 자산 존재 여부 점검
    - 게이트 TTL(30분) 신선도 확인
    - 핵심 문서 mtime 정합성 점검
    - `project_audit_latest.md` 리포트 생성
  - `tools/task_finish.py` 보강:
    - 문서 부분 수정 시 `--confirm-doc-sync` 확인 절차 추가
    - 성공 시 감사 실행 가이드 출력
    - `--run-audit` 옵션으로 감사 즉시 실행 지원
  - `tools/task_start_guard.py` 메시지 보강:
    - 작업 시작 필수 게이트 정책 출력
  - 문서 동기화:
    - `DOC_INDEX.md`에 `ASSET_MAP.md`와 audit 루틴 반영
    - `PROJECT_STATUS.md`/`now_spec.md`에 운영체계 고도화 항목 반영
- Validation:
  - `python -m pytest -q tests/test_task_finish.py tests/test_task_start_guard.py tests/test_project_audit.py tests/test_rule_docs_sync.py` -> `14 passed in 0.14s`
  - `python -m pytest -q` -> `532 passed, 1 skipped in 41.43s`

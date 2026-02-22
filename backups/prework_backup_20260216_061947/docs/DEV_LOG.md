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

## [2026-01-05] 세션 13 — Undo/Redo 경로 단일화 & UI 정리
- **목표**: 중복 메서드 정리, Undo/Redo 경로 단일화, 녹화 완료 처리 통일, 문서 최신화.
- **변경사항**:
  - 드래그/드롭 재정렬을 `ReorderStepsCommand`로 기록해 Undo/Redo 경로 통일.
  - 인라인 이름 변경(`requestRename` → `rename_step_at`)과 브랜치 변환(`convert_to_branch_step`)을 커맨드 패턴으로 통합.
  - 녹화 완료 처리: `_stop_record`는 종료만 수행하고, 요약/스텝 추가는 `_on_record_done`에서 처리하도록 경로 단일화(`_record_show_summary` 플래그 사용).
  - `MainWindow` 내 중복 메서드 정의 제거(실제 사용되는 최신 정의만 유지).
  - Settings 탭의 타겟 창 입력/버튼 제거, 상단 툴바 입력으로 단일화.
  - 테스트: `python -m pytest tests/test_e2e_basic.py -k record`, `python run_health_check.py` 통과(74 passed, 1 skipped).
- **이슈/버그**:
  - comment 스텝의 `comment` 텍스트가 `StepData` 필드에 없어 저장/로드 시 유실 가능.
- **다음 단계**:
  - `comment` 필드 추가 및 직렬화/로드/UI/테스트 동시 반영.

## [2026-01-05] 세션 14 — comment 직렬화 필드 보강
- **목표**: comment 스텝 텍스트 저장/로드 유실 이슈 해결.
- **변경사항**:
  - `StepData.comment` 필드 추가로 직렬화/역직렬화 경로에서 comment 텍스트 유지.
  - 관련 테스트 보강: serialization 기본값 확인, JSON 로드 시 `comment` 보존 검증.
- **테스트**:
  - `python run_health_check.py` 통과(74 passed, 1 skipped).

## [2026-01-06] 세션 15 — 이미지 매칭 고정밀 모드
- **목표**: 이미지 매칭 고정밀 개선과 UI 제어 추가.
- **변경사항**:
  - `StepData.match_quality`/`top_k` 필드 반영 및 직렬화 테스트 보강.
  - Matcher에 멀티 패스 전처리, 스케일+회전 조합 검색, 강제 그레이 패스 색상 게이트 우회 처리 추가.
  - ImageStepDialog에 품질 프리셋/멀티스케일/회전/ORB 폴백 UI 추가 및 테스트 매칭 반영.
- **테스트**:
  - `python run_health_check.py` 실행: 74 passed, 1 skipped. 종료 시 콘솔 인코딩(✅) 오류 발생.

## [2026-01-06] 세션 16 — 헬스 체크 콘솔 인코딩 정리
- **목표**: Windows 콘솔(cp949) 환경에서 헬스 체크 종료 오류 제거.
- **변경사항**:
  - `run_health_check.py` 출력 메시지를 ASCII로 통일(✅/❌ 제거).
- **테스트**:
  - `python run_health_check.py` 통과(74 passed, 1 skipped).

## [2026-01-06] 세션 17 — 고정밀 매칭 최적 선택 & 프리셋 토글
- **목표**: 고정밀 모드에서 최고 점수 선택 + 프리셋 자동 토글 적용.
- **변경사항**:
  - 고정밀 모드에서 패스 전체를 평가하고 최고 점수 결과를 반환하도록 매칭 로직 개선.
  - 품질 프리셋 변경 시 스케일/회전/ORB 토글을 자동으로 반영하도록 UI 동작 추가.
  - 고정밀 결과 선택 검증용 단위 테스트 추가.
- **테스트**:
  - `python run_health_check.py` 통과(75 passed, 1 skipped).

## [2026-01-06] 세션 18 — 고정밀 색상 예외 제거 & 리셋 프리셋
- **목표**: 고정밀 모드의 색상 매칭 일관성 확보와 프리셋 UX 보강.
- **변경사항**:
  - `match_color` 활성 시 강제 그레이 패스를 제외하도록 고정밀 패스 구성 조정.
  - Normal 프리셋은 사용자 마지막 조정 상태를 유지하고, Reset 프리셋으로 초기 상태 복원 가능하게 추가.
  - 고정밀+색상 조합에서 강제 그레이 패스 제외 검증 테스트 추가.
- **테스트**:
  - `python run_health_check.py` 통과(76 passed, 1 skipped).

## [2026-01-06] 세션 20 — 고성능 녹화/재생 모드 추가
- **목표**: 매크로 녹화/실행 성능 개선 및 토글 제공.
- **변경사항**:
  - Settings 탭에 `High Performance Playback/Recording` 토글 추가(QSettings 저장/복원).
  - 고성능 녹화: InputRecorder 큐 20,000 / 이동 최소거리 1px 적용.
  - 고성능 재생: MacroRunner `perf_mode` 추가, `poll_interval=0`, `pyautogui` 내부 딜레이 최소화.
  - 이미지 매칭 루프에서 mss 프레임 copy 제거, step ID 맵 캐싱으로 루프 비용 감소.
  - 녹화 딜레이 기록 토글 기본값을 ON으로 변경(`rec/record_delay_enabled`).
- **테스트**:
  - `python run_health_check.py` 통과(76 passed, 1 skipped).

## [2026-01-06] 세션 19 — 녹화/실행 딜레이 제거(임시)
- **목표**: 녹화/재생 속도 체감 개선.
- **변경사항**:
  - StepData 기본 딜레이(press/pre-move/drag/scroll interval)를 0으로 조정.
  - 녹화 pre_delay_ms를 0으로 기록하도록 변경.
  - 드래그 duration 최소값을 0으로 허용.
- **테스트**:
  - `python run_health_check.py` 통과(76 passed, 1 skipped).

## [2026-01-06] 세션 21 — 성능 레벨(1/2/3) 추가 + 체크박스 연동
- **목표**: 고성능 모드 강도 선택(레벨) 지원 및 기본 동작 보존.
- **변경사항**:
  - Settings 탭에 `Performance Level` 콤보 추가(1/2/3), QSettings 저장/복원.
  - `High Performance Playback/Recording` 체크박스는 유지하고, ON일 때만 레벨 매핑 적용.
  - 녹화 레벨 매핑: L1(큐 20000/이동 1px), L2(큐 50000/이동 0px), L3(큐 100000/이동 0px).
  - 재생 레벨 매핑: L1(0.05), L2(0.01), L3(0.0) poll interval 적용.
- **테스트**:
  - `python run_health_check.py` 통과(76 passed, 1 skipped).

## [2026-01-06] 세션 22 — 테스트 갱신(성능 레벨/설정/딜레이 경로)
- **목표**: 최신 성능/설정 로직에 맞게 테스트 커버리지 보강.
- **변경사항**:
  - QSettings 격리 fixture 추가(UI/시나리오 테스트).
  - 성능 레벨 L1/L2/L3 매핑 및 perf_mode 전달/저장 로드 검증 테스트 추가.
  - 녹화 딜레이 ON/OFF가 실제 클릭 스텝에 반영되는 통합 경로 테스트 추가.
  - perf_mode에서 pyautogui 딜레이 적용/복원 테스트 추가.
- **테스트**:
  - `python run_health_check.py` 통과(90 passed, 1 skipped).

## [2026-01-06] 세션 23 — 테스트 추가 갱신(QSettings 저장/기본값/Runner 기본)
- **목표**: 설정 저장/기본값/Runner 기본 동작 회귀 방지 강화.
- **변경사항**:
  - QSettings 저장 경로(perf_playback/recording/level) 검증 테스트 추가.
  - record_delay_enabled 기본값 ON 검증 테스트 추가.
  - perf_mode True/False에 따른 poll_interval 기본값 검증 테스트 추가.
- **테스트**:
  - `python run_health_check.py` 통과(93 passed, 1 skipped).

## [2026-01-19] 세션 24 — 경로 해석 & OCR 옵션 확장
- **Phase 1: 경로 해석 안정화**
  - MacroRunner에서 `run_macro`/`load_data_file`/`compare_images`/`screenshot_roi` 경로를 현재 매크로 파일 기준으로 해석.
  - 상대 경로 해석 단위 테스트 추가.
- **Phase 2: OCR 옵션 UX**
  - OCR Check/Jump If에 Scale/Invert 컨트롤 추가 및 저장 경로 반영.
  - Action dialog 테스트에 Scale/Invert 저장/가시성 검증 추가.
- **Phase 3: 문서 업데이트**
  - `USER_GUIDE.md`에 OCR Scale/Invert, 상대 경로 사용법 추가.
  - `docs/PROJECT_STATUS.md` 최신화.
- **테스트**:
  - `python run_health_check.py` (162 passed, 1 skipped).

## [2026-01-19] 세션 25 — 캡처 실패 처리 & OCR 옵션 적용
- **목표**: 실패 캡처 실동작 보강, OCR whitelist/target_height 적용 경로 추가, 테스트 강화.
- **변경사항**:
  - capture_on_fail에서 ROI가 비어도 전체 화면 캡처로 저장되도록 보강.
  - `ocr_whitelist`/`ocr_target_height`는 값이 있을 때만 OCR 텍스트 경로에 적용.
  - 테스트 추가: 전체 화면 캡처 fallback, capture_on_fail 트리거, OCR whitelist/target_height 적용.
- **테스트**:
  - `python run_health_check.py` (165 passed, 1 skipped).

## [2026-02-15] 세션 26 — 런타임 예외 경로 보강
- **목표**: 실행/스케줄러/트리거의 시작 실패 경로에서 UI/상태 불일치 제거.
- **변경사항**:
  - `run_macro` 시작 실패 시 UI 상태(실행/정지/녹화 버튼, 최소화 상태) 자동 복구.
  - 스케줄러 실행 경로에서 runner 미생성 시 `notify_macro_finished(False)` 호출 보강.
  - 메인 러너가 없는 트리거 단독 실행 실패 시 예외 전파 대신 오류 로그/정리 처리.
  - 회귀 테스트 추가(`tests/test_ui_integration.py`, `tests/test_main_trigger_scheduler_integration.py`).
- **테스트**:
  - `python -m pytest -q` (212 passed, 1 skipped)
  - `python run_health_check.py` (SYSTEM HEALTHY)

## [2026-02-15] 세션 27 — E2E 오케스트레이션/로그 노이즈/CI 고정
- **목표**: 실사용 흐름 검증 강화 및 품질 게이트 자동화.
- **변경사항**:
  - E2E 오케스트레이션 테스트 추가:
    - 트리거 실행 시 메인 일시정지→재개
    - 스케줄러 큐 순차 실행
    - 녹화→재생 전환
  - `ConfigManager` 숫자 파싱 예외를 구체 타입(`TypeError`, `ValueError`, `OverflowError`)으로 정밀화.
  - 트리거 시작 로그(`Trigger Watcher Started.`) 기본 숨김 처리, 환경변수(`IMAGEMACRO_TRIGGER_START_LOG=1`)로 재활성화 가능.
  - GitHub Actions CI 추가(`.github/workflows/ci.yml`): `pytest -q` + `run_health_check.py`.
- **테스트**:
  - `python -m pytest -q` (218 passed, 1 skipped)
  - `python run_health_check.py` (SYSTEM HEALTHY)

## [2026-02-15] 세션 28 — 기능 구현 검증 테스트 강화(코어 단위)
- **목표**: 구현 의도 검증을 코어 레벨까지 촘촘히 확장.
- **변경사항**:
  - 스케줄러 코어 테스트 추가(`tests/test_scheduler_core.py`):
    - enable/disable 상태 전이, 신호/로그, 일일 1회 실행, 날짜 변경 리셋, 큐 진행 로직.
  - 트리거 엔진 코어 테스트 추가(`tests/test_trigger_engine_core.py`):
    - 프레임 캡처 변환(RGB/BGRA), 비정상 입력 처리, 조건 판정 경로.
- **테스트**:
  - `python -m pytest -q` (231 passed, 1 skipped)
  - `python run_health_check.py` (SYSTEM HEALTHY)

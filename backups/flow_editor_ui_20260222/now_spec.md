# Project Technical Specification (now_spec)

## 1. Project Overview
- Python 3.13 기준(PyQt5) 게임 자동화 봇: 매크로 작성·실행, 화면 인식(OCR/이미지), 인간적 입력을 제공.
- 목표: 안티치트 회피(인간적 입력, 창 포커싱), 모듈성(Logic-UI 분리, Command 패턴), 안정성·가시성(테스트/헬스체크/메트릭).

## 2. Tech Stack & Dependencies
- UI: PyQt5 (Widgets/QtCore/QtGui), QSettings.
- Vision: opencv-python (cv2), pytesseract + Tesseract-OCR, numpy.
- Capture/Input: mss(화면 캡처), pyautogui(입력; HumanMouse 래핑), pynput(InputRecorder).
- Windows Control: pywin32(win32gui/con/process), psutil(프로세스명); 없으면 안전하게 무시.
- QA: pytest, pytest-qt, pytest-mock, coverage; 스크립트 run_health_check.py, auto_inspect.py, run_smoke_suite.py.

## 3. System Architecture
- UI Layer: `MainWindow`(스텝 목록, 실행/정지/녹화, 타겟 창 입력·Find/Fix/Selector), `ScenarioWizardDialog`(템플릿 선택+입력+검증+미리보기), `ManagerTab`(멀티 세션 관리), 각종 다이얼로그(`WindowSelectorDialog` 등).
- Logic Layer: `MacroRunner`(QThread; 스텝 실행, human_mode, OCR/브랜칭/서브스크립트, optional 타겟 포커스), `InputRecorder`(pynput, 필터/리샘플/메트릭), `SessionManager`(라운드로빈 전환/일일 리셋 코어; ManagerTab Start All에서 runner 자동연결 지원).
- Wizard Core: `app/core/scenario_wizard.py`(JSON 템플릿 로드, 입력 검증, `StepData` 생성, 생성 스텝 정합성 검증).
- Core Utilities: `WindowManager`(find/activate/force_refresh 1px shake + 목록 열거), `ImageProcessor`(OCR 전처리·숫자 추출), `HumanMouse`(베지에 곡선+이지ング+지터), `UndoStack`/Commands(Add/Remove/Edit/Move).
- Data Flow: 매크로 파일(JSON/역호환 .macro) 로드 → meta/repeat/steps 파싱 → UI 반영 → Runner 시작 → 필요 시 타겟 창 활성화 → mss 캡처 → Vision/OCR → HumanMouse/pyautogui 액션 → 로그/신호/오버레이 업데이트.

## 4. Key Features
- Undo/Redo: Command 패턴, 모든 CRUD/Move/중복을 `_push_command` 경유, Ctrl+Z/Ctrl+Y.
- Scenario Wizard: 기존 수동 스텝 편집과 독립된 별도 버튼/다이얼로그 제공. `추천/전체/검색` 템플릿 목록, 필수값 입력, 오류/경고 검증, 생성 스텝 미리보기 후 `AddStepsCommand`로 삽입. 템플릿 카탈로그는 46종이며(`app/core/scenario_wizard_templates.json`), 갱신용 생성 스크립트는 `tools/generate_scenario_wizard_templates.py`. 사용자 템플릿은 별도 카탈로그(`app/core/scenario_wizard_user_templates.json`)로 저장/병합되며, 기본 템플릿은 읽기 전용 정책을 유지.
- Sub-scripts: `run_macro` 액션, 콜 스택+재귀 가드(깊이 5), 변수 컨텍스트 공유.
- Window Management: 제목 기반 find/activate, 1px 흔들기로 렌더링 글리치 복구; 제목 비어있거나 미발견 시 경고 후 계속.
- Window Selector: 필터(`title:`, `class:`, `proc:`, `!exclude`) 지원, 프로세스명 미확인 항목은 제목만 표시.
- Recorder: 큐 한도(기본 5000), 거리+시간 하이브리드 필터(지터 제거), 드래그 경로 리샘플링(~20점), 메트릭 반환→UI 표시, 안전 stop.
- Multi-Manager: 세션 편집/라운드로빈 코어 제공(타겟/스크립트/리셋 설정 포함). `Start All` 경로에서 세션 script_path를 기준으로 runner 자동 생성/연결을 시도하며, 스크립트 미지정/로드 실패 세션만 `pending` 상태.
- Stability/QA: run_health_check.py, auto_inspect.py, run_smoke_suite.py, 광범위한 pytest(시뮬레이션/스트레스/브랜칭/OCR/입출력/메타/윈도우).

## 5. Data Models & File Format
- `StepData`: id/name/type, pre_delay_ms, 이미지/타깃, key/text, OCR 필드(roi/invert/high_contrast/var), branching(`jump_if` with step_id 우선), run_macro(target_macro_path), loop/log/comment, 고급 매칭 옵션(`hq_color_bg_robust`, `alpha_mask_enable`, `auto_fg_mask_enable`, `auto_fg_mask_bg_percentile`, `auto_fg_mask_dynamic_scale`, `auto_fg_mask_min_distance`, `auto_fg_suggest_std_low`, `auto_fg_suggest_std_high`, `auto_fg_suggest_edge_low`, `auto_fg_suggest_edge_high`) 등.
- 시나리오 마법사 템플릿 카탈로그: `app/core/scenario_wizard_templates.json` (schema_version=1).
- 시나리오 마법사 사용자 템플릿 카탈로그: `app/core/scenario_wizard_user_templates.json` (schema_version=1, 없으면 자동 빈 카탈로그로 처리).
- custom flow 코어 유틸: `app/core/scenario_wizard_flow.py`
  - `atomic_write_json(...)`: 동일 디렉터리 `.tmp` 작성 후 `os.replace`로 원자적 저장
  - `validate_custom_flow_steps(...)`: 중복 ID/고아 참조/루프 페어링/self-jump 검사 + 미도달/루프 위험 경고
  - `validate_custom_flow_blueprint(...)`: UI 편집 중 blueprint 단계에서 상세 이슈(`code`, `step_id`) 리포트 제공
  - `materialize_custom_flow_steps(...)`: blueprint(`step_uuid`)를 실행용 `StepData`로 변환하고 참조 ID 리매핑
  - `find_references_in_blueprint(...)`, `delete_step_with_lazy_repair(...)`: 삭제 전 참조 탐색 및 삭제 후 자동 보정(next/None)
- `ActionType`(코어 상수): `image_click`, `image_move`, `image_drag`, `image_branch`, `target`, `comment`, `action`, `run_macro`.
- 실행 스텝 타입(`StepData.type`)은 위 상수 외 `keyboard`, `mouse`, `screen_check`, `jump_if`, `compare_images`, `screenshot_roi`, `ocr_check_text`, `ocr_jump_if`, `ocr_store`, `load_data_file`, `file_action` 등을 포함.
- Add Action UI 지원 타입과 기능 매핑:
  - 키입력: `keyboard`, `text`, `key`, `key_down`, `key_up`, `key_hold`
  - 마우스: `mouse`, `click_point`, `drag`, `scroll`
  - 화면확인/OCR: `screen_check`, `pixel_check`, `ocr_check_text`, `ocr_store`, `ocr_jump_if`
  - 로직/제어: `jump_if`, `start_loop`, `end_loop`, `wait`, `comment`
  - 파일/서브스크립트: `file_action`, `load_data_file`, `run_macro`
  - 유틸: `screenshot_roi`, `compare_images`
  - 레거시: `loop`(호환 no-op), `action`(다이얼로그에서 `keyboard`로 매핑)
- JSON 저장 포맷:
  ```json
  {
    "meta": {"version": "1.0", "target_window": "<title>", "description": ""},
    "repeat": { ... RepeatConfig ... },
    "steps": [ ... StepData dict ... ]
  }
  ```
  구버전 리스트 JSON 및 `.macro` 파일은 역호환 로드 유지.

## 6. Runtime Robustness (Latest)
- `run_macro` 시작 실패 시 UI 버튼 상태 및 최소화 상태를 즉시 복구해 반쯤 실행된 상태를 남기지 않음.
- 앱 시작 시 Target 입력은 항상 빈 값으로 시작해 이전 세션 잔존 타겟이 자동 적용되지 않음.
- `MacroRunner(target_window_title=None)`은 빈 문자열로 정규화되어 암묵적 타겟 참조를 하지 않음.
- 스케줄러 경로에서 macro load/runner start 실패를 구분하고, 실패 시 `notify_macro_finished(False)`로 시퀀스 정체를 방지.
- 트리거 단독 실행(메인 러너 없음)에서도 시작 실패 예외를 안전하게 처리하고 `trigger_runner`를 정리.
- 스케줄러 실패 정책을 런타임 옵션으로 지원:
  - `continue_next`
  - `stop_sequence`
  - `retry_then_continue` (`max_retries`, `retry_delay_ms`)
- 스케줄러 상태 시그널을 UI 라벨과 연동해 실행/재시도/실패중단 상태를 즉시 표시.
- 실패 정책 UI에서 `retry_then_continue` 선택 시에만 Retry Count/Delay 입력을 활성화해 오설정을 줄임.
- TriggerWatcher는 event 기반 대기(`_wait_or_wake`)와 `stop(timeout)`을 사용해 종료 반응성을 높이고 hang 가능성을 줄임.
- 창 목록 조회는 pywin32 미가용 환경에서 `ctypes` EnumWindows 폴백을 사용해 Selector 빈 목록 가능성을 낮춤.
- 스텝 재정렬은 `sync_order`에서 `ReorderStepsCommand`를 통해 Undo/Redo 스택에 기록됨.
- `NotImageDialog` 취소 시 저장되지 않도록 호출부(`add_not_image_step`, `edit_step_at`)를 정정해 의도치 않은 변경 반영을 방지.
- `NotImageDialog` 내부 중복 Run Macro 그룹을 제거해 UI 가시성 혼선을 줄임.
- 고급 이미지 매칭에서 `match_color=True`일 때도 `hq_color_bg_robust=True`를 켜면 gray/CLAHE/edge fallback 패스를 추가로 실행해 배경 변화 내성을 높임(기본값 Off로 역호환 유지).
- PNG 템플릿 로드 시 알파 채널을 마스크로 추출하고(`alpha_mask_enable=True`), 매칭/색상게이트에서 마스크 영역만 평가해 투명 배경 영향을 줄임.
- 알파 없는 템플릿에서도 `auto_fg_mask_enable=True`면 자동 전경 마스크를 생성(테두리 배경색 기반 + edge 폴백)해 매칭에 적용.
- 자동 전경 마스크 임계값(`bg_percentile`, `dynamic_scale`, `min_distance`)을 스텝별 설정으로 튜닝 가능.
- 자동 전경 마스크 프리셋(`stable`, `accurate`, `aggressive`)을 ImageStepDialog에서 즉시 적용 가능.
- Auto FG 프리셋 설명 힌트와 `Suggest` 버튼으로 템플릿 기반 초기 추천을 제공.
- Suggest 결과는 confidence(%)와 지표(`std`, `edge density`)를 함께 표시해 추천 근거를 제공.
- Suggest 분류 임계값(`std/edge low/high`)을 스텝별로 조절해 추천 성향을 템플릿 특성에 맞게 보정 가능.

## 7. Test & QA Baseline
- Core + Integration + E2E 테스트를 분리 운영:
  - 런타임 오케스트레이션 E2E: `tests/test_e2e_runtime_orchestration.py`
  - 스케줄러 코어: `tests/test_scheduler_core.py`
  - 트리거 엔진 코어: `tests/test_trigger_engine_core.py`
  - 윈도우 셀렉터/타겟 회귀: `tests/test_window_selector_dialog.py`, `tests/test_window_integration.py`
  - 멀티 매니저 코어/통합: `tests/test_session_manager.py`, `tests/test_manager_tab_integration.py`
- 스모크 실행 진입점:
  - `python run_smoke_suite.py --quick` (핵심 런타임/매칭 게이트)
  - `python run_smoke_suite.py` (핵심 게이트 + 전체 health check)
- 최신 로컬 기준: `python -m pytest -q` = `314 passed, 1 skipped`.
- 헬스 체크 기준: `python run_health_check.py` = `SYSTEM HEALTHY`.

## 8. CI/CD Gate
- GitHub Actions: `.github/workflows/ci.yml` (Windows + Python 3.13).
- 필수 게이트:
  1. `python -m pytest -q`
  2. `python run_health_check.py`
- 환경값: `QT_QPA_PLATFORM=offscreen`, `IMAGEMACRO_TRIGGER_START_LOG=0`.

## 9. Documentation Baseline
- 문서 기준 인덱스: `DOC_INDEX.md`
- 운영 기준 문서:
  - `now_spec.md`
  - `PROJECT_STATUS.md`
  - `USER_GUIDE.md`
  - `SMOKE_TEST_CHECKLIST.md`
  - `BUTTON_CHECK.md`
  - `DEV_LOG.md`
- 과거 단건 검토/개선 문서는 `archive/docs_legacy_20251124/`에서 참고용으로만 보관.

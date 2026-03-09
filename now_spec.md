## Recording Behavior Update (2026-03-09)
- Standard `Record` mode is exact-replay oriented.
- Final recorded steps are taken from `InputRecorder` output directly, preserving recorded click/drag/scroll behavior and `pre_delay_ms`.
- Smart proposal flow no longer overrides standard `Record` results.

## Shutdown Cleanup Update (2026-03-09)
- Effective `MainWindow.closeEvent` now disables scheduler/timer state during shutdown.
- Window close no longer leaves scheduled run callbacks armed after the UI is gone.
## Record / Smart Capture Boundary (2026-03-09)
- Standard `Record` owns only `InputRecorder` output and recorder live-signal HUD updates.
- Standard `Record` does not instantiate or materialize `SmartTransformer` / smart proposals.
- `Smart Capture` remains a separate manual image-capture workflow for `image_click` / `wait_for_image`.

## Global Add-Step Hotkeys (2026-03-09)
- Windows `SystemHotkeys` now registers `Add Image` and `Add Action` in addition to `Run/Stop/Record/Pause/Kill`.
- When the macro window is inactive, `Add Image` / `Add Action` can still dispatch through `WM_HOTKEY`.
- Local `QShortcut` wiring remains for focused-window use; global registration covers inactive-window capture workflows.

## Action Step Picker Normalization (2026-03-10)
- `safe_select_point()` returns normalized `(x, y)` integer coordinates.
- `NotImageDialog` click/drag pickers accept both tuple and `QPoint` style values without losing the selected coordinates.
- `ConditionalActionWizardDialog` uses the same normalization path for click target picking.
# Project Technical Specification (now_spec)

## 1. Project Overview
- Python 3.13 기준(PyQt5) 게임 자동화 봇: 매크로 작성·실행, 화면 인식(OCR/이미지), 인간적 입력을 제공. 단일 모니터 환경을 위한 컴팩트(Compact) UI 전략을 채택함.
- 목표: 안티치트 회피(인간적 입력, 창 포커싱), 모듈성(Logic-UI 분리, Command 패턴), 안정성·가시성(테스트/헬스체크/메트릭), 낮은 화면 가림(팝아웃/항상 위).

## 2. Tech Stack & Dependencies
- UI: PyQt5 (Widgets/QtCore/QtGui), QSettings.
- Vision: opencv-python (cv2), pytesseract + Tesseract-OCR, numpy.
- Data I/O: csv + openpyxl 기반 CSV/XLSX 로더(`app/io/data_loader.py`).
- Capture/Input: mss(화면 캡처), pyautogui(입력; HumanMouse 래핑), pynput(InputRecorder).
- Windows Control: pywin32(win32gui/con/process), psutil(프로세스명); 없으면 안전하게 무시.
- QA: pytest, pytest-qt, pytest-mock, coverage; 스크립트 run_health_check.py, auto_inspect.py, run_smoke_suite.py.

## 3. System Architecture
- UI Layer: 
  - 기본 사이즈를 축소 고정(720x480)하고, 보조 컨트롤러 역할을 수행하는 컴팩트 모드 우선.
  - `MainWindow`(스텝 목록, 실행/정지/녹화, 타겟 창 입력 등). 좌측 `QTabWidget`에 Scenario/Triggers/Multi-Manager/Presets/Scheduler/Settings 탭 통합(총 6탭).
  - Options Toolbar는 `QGridLayout` 3행(Target/Flags/Excel)로 구성되어 작은 창에서도 깨지지 않음.
  - Preview 창 독립 팝아웃 기능 및 Always On Top 제어 지원.
  - `closeEvent` 추가로 창 닫을 때 runner/recorder/trigger_watcher/scheduler 안전 종료 보장.
  - 이외 각종 다이얼로그(`TargetDialog`, `ScenarioWizardDialog`, `ManagerTab` 등).
- Logic Layer: `MacroRunner`(QThread; 스텝 실행, human_mode, OCR/브랜칭/서브스크립트, optional 타겟 포커스), `InputRecorder`(pynput, 필터/리샘플/메트릭), `SessionManager`(라운드로빈 전환/일일 리셋 코어; ManagerTab Start All에서 runner 자동연결 지원).
- Wizard Core: `app/core/scenario_wizard.py`(JSON 템플릿 로드, 입력 검증, `StepData` 생성, 생성 스텝 정합성 검증 + 데이터 컬럼 검증).
- Core Utilities: `WindowManager`(find/activate/force_refresh 1px shake + 목록 열거), `ImageProcessor`(OCR 전처리·숫자 추출), `HumanMouse`(베지에 곡선+이지ング+지터), `UndoStack`/Commands(Add/Remove/Edit/Move), `runtime_paths`(`sys._MEIPASS` 대응 리소스 경로/쓰기 경로), `ocr_runtime`(Tesseract 경로 해석/적용).
- Data Flow: 매크로 파일(JSON/패키지형 .macro) 로드 → meta/repeat/steps 파싱 → UI 반영 → Runner 시작 → 필요 시 타겟 창 활성화 → mss 캡처 → Vision/OCR → HumanMouse/pyautogui 액션 → 로그/신호/오버레이 업데이트.

## 4. Key Features
- Undo/Redo: Command 패턴, 모든 CRUD/Move/중복을 `_push_command` 경유, Ctrl+Z/Ctrl+Y.
- Scenario Wizard: 기존 수동 스텝 편집과 독립된 별도 버튼/다이얼로그 제공. `추천/전체/검색` 템플릿 목록, 필수값 입력, 오류/경고 검증, 생성 스텝 미리보기 후 `AddStepsCommand`로 삽입. 템플릿 카탈로그는 46종이며(`app/core/scenario_wizard_templates.json`), 갱신용 생성 스크립트는 `tools/generate_scenario_wizard_templates.py`. 사용자 템플릿은 별도 카탈로그(`app/core/scenario_wizard_user_templates.json`)로 저장/병합되며, 기본 템플릿은 읽기 전용 정책을 유지. 사용자 편집 팝업에서 `custom_flow` 흐름 편집(샌드위치 삽입/삭제 Lazy-Check/저장 전 Validator 리포트)도 지원. 데이터 템플릿은 CSV/XLSX 경로를 입력받고 문자열 필드에 컬럼 토큰 삽입 버튼(`{column}`)을 제공.
- Multi-role AI Orchestration(개발 보조): `app/core/multi_role_ai.py`에서 역할별(Planner/Implementer/Reviewer/Tester/Documenter) 파이프라인을 순차 실행하고, `tools/run_multi_role_ai.py`로 CLI 실행. `auto` 모드에서 task/context 복잡도를 기반으로 `compact`(3역할) 또는 `precision`(5역할) 체인을 자동 선택.
  - `changed_files` 힌트 기반 Precision 강제 트리거를 지원(파일 수 5개 이상 또는 `stepdata/serialization/runner/signal` 핵심 경로 포함 시 강제 Precision).
  - Guardian 하드 게이트: reviewer/guardian 결과가 `is_approved=false` 또는 `FAIL`이면 프로세스를 종료 코드 1로 차단.
  - 실패 시 baseline 대비 신규 tracked 변경 파일 rollback 시도(`git checkout -- <file>`).
  - 세션 아티팩트를 `logs/ai_sessions/{timestamp}/`에 저장:
    - `planner_plan.md`
    - `executor_diff.json`
    - `guardian_report.json`
- DX Tool Integrity/Feedback Automation:
  - 루트 `tools/*`는 `dx_operating_pack/tools/*` 위임 래퍼를 통해 단일 소스 기반으로 동작한다.
  - `dx_operating_pack/tools/check_tool_integrity.py`가 루트/팩 도구 정합성(정확 복사 또는 위임 래퍼)을 검사한다.
  - `dx_operating_pack/tools/setup_dx.py`는 설치 후 정합성 검사기를 자동 실행해 불일치 경고를 즉시 노출한다.
  - `dx_operating_pack/tools/task_finish.py --auto-push`는 게이트 성공 직후 `push_dx_feedback.py`를 자동 호출한다.
  - `capture_lesson_draft.py`는 최신 `logs/ai_sessions/` JSON/Markdown 로그에서 `Decision/Reason/Warning` 신호를 수집해 `LATEST_INSIGHT.yaml`에 기록한다.
- Multi-Manager pending 자동 복구: `SessionManager`가 `runner_provider(sess)`를 통해 pending 세션의 runner 재생성을 시도하고, 세션별 backoff로 재시도 간격을 제어한다. recovery가 최대 시도/최대 대기 임계치를 넘기면 `pending -> error`로 승격한다.
- Global Input Lock: `app/core/input_lock.py`의 `GlobalInputManager`를 통해 물리 입력 구간을 전역 직렬화한다. `MacroRunner`는 lock wait/acquire/release/timeout을 JSONL 이벤트로 기록하고, timeout은 step failure로 전파된다.
- Sub-scripts: `run_macro` 액션, 콜 스택+재귀 가드(깊이 5), 변수 컨텍스트 공유.
- Window Management: 제목 기반 find/activate, 1px 흔들기로 렌더링 글리치 복구; 제목 비어있거나 미발견 시 경고 후 계속.
- Window Selector: 필터(`title:`, `class:`, `proc:`, `!exclude`) 지원, 프로세스명 미확인 항목은 제목만 표시.
- Recorder: 큐 한도(기본 5000), 거리+시간 하이브리드 필터(지터 제거), 드래그 경로 리샘플링(~20점), 메트릭 반환→UI 표시, 안전 stop.
- Safety Control(Option A): 글로벌 핫키 기반 런타임 제어(`F10` pause/resume, `F12` emergency kill) + Runner 내부 `threading.Event` 대기.
  - Hotkey Settings에서 Pause/Kill을 직접 변경 가능하며, 저장 시 중복 단축키 충돌을 차단.
  - pause 상태는 Run 버튼 주황 강조(`▶ 재개`) + 상태바/런타임 라벨 `Paused`로 시각 표시.
- Resolution Independence(Option B):
  - `wait_for_image` 스텝 추가: 이미지가 나타날 때까지 폴링하고 성공 시 `on_match_goto_id`, 실패 시 `branch_on_fail_goto_id` 경로를 사용할 수 있음.
  - `click_anchor`가 런타임 클릭 좌표 계산에 실제 반영됨(`center/top-left/top-right/bottom-left/bottom-right`).
  - `StepData.anchor_image_path`/`image_path`를 통해 파일 경로 기반 템플릿 로드 지원(이미지 바이트 미내장 시에도 실행 가능).
  - 경로가 상대경로일 경우 실행 중인 매크로 파일(`current_file_path`) 기준으로 절대경로 정규화 후 매칭.
  - custom_flow 편집기(`FlowStepEditDialog`)에서 `image_click`/`wait_for_image` 삽입 가능.
- Template Ecosystem(Option C):
  - `.macro` 저장 구조를 `template.json + assets/*.png`로 표준화.
  - `.macro` 로드 시 신규 구조와 레거시(`scenario.json + images/*.png`)를 동시 지원.
  - 이미지 경로 로딩에서 `../`, 절대경로, 드라이브 경로를 차단해 unsafe 경로 참조를 방어.
  - `.macro`의 `meta.target_window` 저장/복원 지원.
- Data Orchestration V2 Step 2C(UI 통합):
  - 메인 UI에서 `Excel Data Mode`를 활성화하면 `.xlsx` 행 데이터를 `JobQueueManager`로 적재해 멀티 세션(`SessionJobAdapter`) 병렬 실행.
  - 옵션 툴바는 가로 스크롤 컨테이너로 구성되어 작은 창 폭에서도 컨트롤 접근이 가능.
  - `Excel Data Mode` 체크박스와 병렬도(`P:`)는 고정 크기 정책으로 우선 가시성 유지.
  - 엑셀 경로 필드는 elide 표시를 사용해 좁은 폭에서 텍스트 말줄임으로 표시되며 내부 full path 값은 유지.
  - 옵션 바에 `Auto Enter` 체크박스를 제공하며, 활성 시 텍스트 입력 액션 뒤 Enter 키를 자동 입력.
  - `excelOrchEvent`/`excelOrchFinished` 시그널로 진행률/상태 라벨을 스레드 안전하게 갱신.
  - 완료 시 `ExcelResultExporter`로 `_status`, `_error_reason`이 포함된 결과 파일 자동 저장.
  - Stop 버튼으로 실행 중 어댑터를 안전 중지하고 기존 단일 매크로 실행 경로와 공존.
  - 텍스트 데이터 바인딩은 `TemplateProcessor` 공통 경로로 처리되며, 미치환 플레이스홀더(`{{var}}`, `{var}`)가 남으면 실행을 실패 처리해 원문 타이핑을 차단.
  - Excel 실행기 텍스트 우선순위는 `스텝 템플릿 > payload(text/message)`이며, 사용자 지정 `{{ }}` 템플릿이 기본 message 열보다 먼저 적용된다.
  - 플레이스홀더 키 매핑은 대소문자 무시를 지원(`user_name`/`USER_NAME`).
  - Excel payload runner 물리 입력(`pyautogui.write`, `Ctrl+V`)은 `Global Input Lock`으로 직렬화되어 멀티 워커 환경에서 입력/클립보드 간섭을 방지.
  - Excel 실행 로그는 워커와 치환 결과를 함께 표시한다(예: `[Worker 1] 처리 중: {{USER_NAME}} -> 김철수`).
  - Hotkey Run은 Run 버튼과 같은 분기(`_on_run_button_clicked`)를 사용해 Excel 모드 ON/OFF에 따라 동일 경로로 실행.
- Action Step 편집 UX:
  - `Key String` 옆 `[REC]` 버튼으로 특수키를 직접 눌러 키 이름(`enter`, `tab`, `f1`, `esc`) 자동 입력 가능.
  - `key`/`key_down`/`key_up`/`key_hold` 모드에서만 활성화되어 `text` 입력 모드와 간섭하지 않음.
- 조건부 액션 위저드(Stage 2-1 PR-1):
  - Scenario 탭 `조건 위저드` 버튼에서 질문형 QDialog를 열어 OCR 조건 분기 스텝을 자동 생성.
  - 생성 스텝은 기존 타입 조합(`ocr_jump_if` + 실패 라우팅 `jump_if` + 성공 `click_point`/`jump_target` + 앵커 `comment`)만 사용.
  - 삽입은 `AddStepsCommand` 경로를 사용해 Undo/Redo와 완전 호환.
- Packaging MVP:
  - PyInstaller 스펙(`ImageMacro.spec`)과 빌드 스크립트(`tools/build_exe.ps1`) 제공.
  - GitHub Actions 수동 빌드 워크플로우(`.github/workflows/build-exe.yml`) 제공.
  - 앱 시작 시 OCR 경로가 미설정이면 1회 안내 후 경로 선택 가능(Settings 메뉴에서 재설정 가능).
- Multi-Manager: 세션 편집/라운드로빈 코어 제공(타겟/스크립트/리셋 설정 포함). `Start All` 경로에서 세션 script_path를 기준으로 runner 자동 생성/연결을 시도하며, 스크립트 미지정 세션은 즉각 `error` 처리하고 로드에 실패한 세션만 `pending` 상태로 백오프 복구를 시도함.
- Stability/QA: run_health_check.py, auto_inspect.py, run_smoke_suite.py, 광범위한 pytest(시뮬레이션/스트레스/브랜칭/OCR/입출력/메타/윈도우).

## 5. Data Models & File Format
- `StepData`: id/name/type, pre_delay_ms, 이미지/타깃, key/text, OCR 필드(roi/invert/high_contrast/var), branching(`jump_if` with step_id 우선), run_macro(target_macro_path), loop/log/comment, 고급 매칭 옵션(`hq_color_bg_robust`, `alpha_mask_enable`, `auto_fg_mask_enable`, `auto_fg_mask_bg_percentile`, `auto_fg_mask_dynamic_scale`, `auto_fg_mask_min_distance`, `auto_fg_suggest_std_low`, `auto_fg_suggest_std_high`, `auto_fg_suggest_edge_low`, `auto_fg_suggest_edge_high`), 경로 기반 템플릿(`anchor_image_path`, `image_path`) 등.
- 시나리오 마법사 템플릿 카탈로그: `app/core/scenario_wizard_templates.json` (schema_version=1).
- 시나리오 마법사 사용자 템플릿 카탈로그: writable app data dir의 `scenario_wizard_user_templates.json` (schema_version=1, 없으면 자동 빈 카탈로그로 처리).
- custom flow 코어 유틸: `app/core/scenario_wizard_flow.py`
  - `atomic_write_json(...)`: 동일 디렉터리 `.tmp` 작성 후 `os.replace`로 원자적 저장
  - `validate_custom_flow_steps(...)`: 중복 ID/고아 참조/루프 페어링/self-jump 검사 + 미도달/루프 위험 경고
  - `validate_custom_flow_blueprint(...)`: UI 편집 중 blueprint 단계에서 상세 이슈(`code`, `step_id`) 리포트 제공
  - `materialize_custom_flow_steps(...)`: blueprint(`step_uuid`)를 실행용 `StepData`로 변환하고 참조 ID 리매핑
  - `find_references_in_blueprint(...)`, `delete_step_with_lazy_repair(...)`: 삭제 전 참조 탐색 및 삭제 후 자동 보정(next/None)
- Runtime 관측 메타:
  - custom_flow 실행 스텝은 `materialize_custom_flow_steps(...)`에서 `source_step_id`/`source_step_name`을 유지해 원본 blueprint와 런타임 스텝을 연결.
  - `MacroRunner`는 `stepStarted(step_uuid, step_name)`, `stepSucceeded(step_uuid)`, `stepFailed(step_uuid, step_name, error)` 시그널을 노출.
- 실행 이력 코어 유틸: `app/core/run_history.py`
  - `load_run_events(...)`: `.jsonl` 이벤트 파일 로드(손상 라인 안전 스킵)
  - `summarize_run_events(...)`: run 상태/총시간/실패 수/병목 스텝 요약
  - `list_run_summaries(...)`: `logs/run_events_*.jsonl` 실행 목록 생성(최신순)
- `ActionType`(코어 상수): `image_click`, `wait_for_image`, `image_move`, `image_drag`, `image_branch`, `target`, `comment`, `action`, `run_macro`.
- 실행 스텝 타입(`StepData.type`)은 위 상수 외 `keyboard`, `mouse`, `screen_check`, `jump_if`, `compare_images`, `screenshot_roi`, `ocr_check_text`, `ocr_jump_if`, `ocr_store`, `load_data_file`, `file_action` 등을 포함.
- `load_data_file`는 CSV/XLSX를 읽어 `{data}` 및 `{column_name}` 치환 소스로 사용.
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
  구버전 리스트 JSON은 역호환 로드 유지.
- `.macro` 패키지 포맷:
  - ZIP 내부 `template.json` + `assets/` 이미지 에셋.
  - 레거시 ZIP(`scenario.json` + `images/`)도 로드 가능.

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
- 메인 UI는 Runner의 step 시그널을 구독해 실행 상태를 실시간 표시:
  - 상태바 `Run`/`Fail` 라벨에 step_uuid 기반 상태 출력
  - 현재 실행 스텝은 파란 하이라이트, 마지막 실패 스텝은 붉은 하이라이트
- Scenario 스텝 리스트 가시성:
  - `jump_if`/`ocr_jump_if`/`start_loop`/`end_loop`는 카드 내 흐름 힌트로 점프/복귀 경로를 표시
  - Excel 모드 + 데이터 파일 지정 시 텍스트 스텝 `{{변수}}`에 대해 첫 데이터 행 미리보기를 카드/툴팁에 표시
  - 변수 매핑은 헤더 대소문자를 구분하지 않음(`user_name` == `USER_NAME`)
  - 리스트 좌측 Arrow Lane에 jump/branch/loop edge를 색상별로 그려 흐름 도약 지점을 시각화
  - Arrow Lane edge 수집은 `target_true/false`, `on_match_goto_id`, `branch_on_fail_goto_id`, `start_loop_id`를 함께 반영
  - 드래그 중에는 임시 순서 기반 Flow Preview를 표시하며 edge 상태를 구분:
    - `ok`: 기본 색
    - `self_jump`: 주황 경고
    - `dangling`: 빨강 점선 경고
  - Flow Preview 계산은 `(order_hash, edge_source_hash)` 캐시로 중복 계산을 방지
- Logic Path Simulator:
  - 코어: `app/core/logic_path_simulator.py`
  - 입력: step list + context(Excel 1행 우선) + `ConditionEvaluator` + `max_hops`
  - 분기 예측: `jump_if`, `ocr_jump_if`, `image_branch`, sensor-step(`on_match_goto_id`/`branch_on_fail_goto_id`)
  - 루프 예측: `start_loop`/`end_loop`의 `loop_count` 및 무한루프(`count=0`)를 추적
  - 안전장치: `max_hops` 초과 시 종료 + warning
  - UI: Scenario 탭 `경로 시뮬레이션` 버튼 실행 시 방문 스텝 청록 하이라이트 + 시뮬레이션 로그 출력
- Smart Snap (Stage 2-2 PR-3):
  - 옵션 플래그: Advanced 옵션 행 `Smart Snap` 체크박스(기본 ON, `QSettings` 연동).
  - 그룹 추론: `collect_step_group(seed_index)`가 `WZ` 마커 + 내부 참조 ID 그래프를 결합해 세트 스텝을 인식.
  - 재정렬 보정: 세트 일부만 이동해도 전체 블록을 동반 이동(`sync_order` 경로)하고 내부 상대 순서를 유지.
  - 레거시 보정: 재배치 후 `jump_to_index`, `target_true_index`, `target_false_index`를 새 순서 기준으로 재정규화.
  - 경고 피드백: 그룹 분리 또는 dangling 연결이 감지되면 Flow Arrow Lane 경고 edge + 토스트/상태바 경고 표시.
- Visual Image Capturer (Stage 3-1):
  - 코어 오버레이: `app/ui/overlay.py`의 `VisualImageCaptureOverlay`가 전체화면 반투명 캡처/드래그 좌표/크기 표시를 제공.
  - 툴바 진입점: Core 행 `스마트 캡처` 버튼에서 캡처 타입(`image_click`, `wait_for_image`)을 선택해 실행.
  - 자동 생성: 캡처 이미지를 `images/smart_capture_*.png`로 저장하고 `StepData`(`anchor_image_path`, `image_path`, `png_bytes`)를 자동 구성.
  - 자동 삽입: `AddStepsCommand`로 현재 선택 스텝 다음 위치에 삽입해 Undo/Redo와 완전 호환.
  - 안정성: 매크로/Excel 실행 중 캡처를 차단하고 취소(ESC/우클릭) 시 파일 생성 없이 clean 종료.
- Coordinate Guide Overlay (Stage 3-2 PR-3-2-1):
  - 코어 오버레이: `CoordinateGuideOverlay`가 전체화면 투명 레이어에 십자선/레이저 포인트/라벨을 렌더링.
  - API: `show_marker(...)`, `clear_marker()`, `to_overlay_point(...)`, `get_shared()`.
  - 좌표계: 물리 화면 bounds + 가상 화면 geometry 스케일 매핑으로 DPI 차이 환경 대응.
  - 확장 준비: `bbox` 전달 시 점선 박스 렌더링(이미지 스텝 가이드 확장용).
  - 검증: `tests/test_coordinate_overlay_mapping.py`(마커 상태, 클릭 관통, 공유 인스턴스 재사용).
- StepList 좌표 프리뷰 이벤트 (Stage 3-2 PR-3-2-2):
  - `StepList`가 `coordinatePreviewRequested(dict)`/`coordinatePreviewCleared()` 신호를 제공.
  - Hover(`itemEntered`)와 Selection(`currentItemChanged`)에서 좌표 스텝 payload를 emit.
  - payload는 `x/y/index/type/image_path(옵션)`를 포함하며, 좌표 없는 스텝은 clear 경로로 정리.
  - `leaveEvent` 시 clear 신호를 emit해 오버레이 잔상 제거.
  - 동일 payload 반복 emit은 signature 캐시로 억제.
- MainWindow 좌표 오버레이 라우팅 (Stage 3-2 PR-3-2-3):
  - `MainWindow`가 StepList 좌표 신호를 수신해 `CoordinateGuideOverlay`를 실제 구동.
  - 라우팅 슬롯: `_on_coordinate_preview_requested(payload)`, `_clear_coordinate_preview()`.
  - `image_click`의 경우 템플릿 이미지 크기를 캐시 로드(`image_path` 또는 `png_bytes`)하여 bbox(`W,H`) 전달.
  - 실행 가드: 매크로/Excel 실행 중 프리뷰 차단(`_coordinate_preview_suspended`) + 시작 시 clear, 완료 시 복구.
- 조건 위저드(Conditional Wizard):
  - 의도 템플릿:
    - `ocr_text_then_click`
    - `ocr_retry_then_stop`
    - `image_check_then_click_branch`
  - 의도별로 필요한 입력만 노출(텍스트/이미지/재시도/타임아웃)
  - 생성 결과는 기존 `StepData`만 조합해 Undo/Redo(`AddStepsCommand`)와 호환
- 이미지 클릭 좌표 계산:
  - matcher가 찾은 중심점에서 `click_anchor`로 실제 기준점(top-left 등)을 계산한 뒤 `click_offset_x/y`를 적용.
  - branch target 매칭/클릭도 동일 규칙을 적용.
- Structured JSONL 런타임 로그:
  - `MacroRunner`가 실행 단위 `run_id`를 생성하고 `.jsonl`로 이벤트를 저장
  - 이벤트: `run_started/run_resumed/run_finished`, `step_started/step_succeeded/step_failed`, `run_stop_requested`, `run_paused`, `run_killed`
  - `step_succeeded/step_failed`에는 `duration_ms`, 실패 시 `error` 포함
  - 로그 유틸: `app/utils/structured_jsonl.py`
- 실행 이력 뷰어:
  - Help 메뉴 `Execution History`에서 다이얼로그 오픈
  - 실행 목록과 이벤트 타임라인을 앱 내부에서 조회
  - 실패 이벤트/실패 런은 색상 하이라이트로 시각 구분
- 고급 이미지 매칭에서 `match_color=True`일 때도 `hq_color_bg_robust=True`를 켜면 gray/CLAHE/edge fallback 패스를 추가로 실행해 배경 변화 내성을 높임(기본값 Off로 역호환 유지).
- PNG 템플릿 로드 시 알파 채널을 마스크로 추출하고(`alpha_mask_enable=True`), 매칭/색상게이트에서 마스크 영역만 평가해 투명 배경 영향을 줄임.
- 알파 없는 템플릿에서도 `auto_fg_mask_enable=True`면 자동 전경 마스크를 생성(테두리 배경색 기반 + edge 폴백)해 매칭에 적용.
- 자동 전경 마스크 임계값(`bg_percentile`, `dynamic_scale`, `min_distance`)을 스텝별 설정으로 튜닝 가능.
- 자동 전경 마스크 프리셋(`stable`, `accurate`, `aggressive`)을 ImageStepDialog에서 즉시 적용 가능.
- Auto FG 프리셋 설명 힌트와 `Suggest` 버튼으로 템플릿 기반 초기 추천을 제공.
- Suggest 결과는 confidence(%)와 지표(`std`, `edge density`)를 함께 표시해 추천 근거를 제공.
- Suggest 분류 임계값(`std/edge low/high`)을 스텝별로 조절해 추천 성향을 템플릿 특성에 맞게 보정 가능.
- OCR 경로 설정:
  - `Settings -> OCR (Tesseract) Path...`에서 수동 경로 지정 가능.
  - 런타임 OCR 호출 전 `ocr_runtime.configure_tesseract_cmd()`를 통해 env/settings/default/PATH 순으로 경로를 자동 적용.

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
- 최신 로컬 기준: `python -m pytest -q` = `497 collected, 0 FAILED` (Qt crash 우회 적용).
- pytest Qt crash 우회: `tests/conftest.py`에서 `pytest_sessionfinish` + `os._exit()` 강제 종료. `pytest.ini`에 `-p no:qt` + UI 테스트 4종 `--ignore` 처리.


### Smart Recorder Raw Event Core (Stage 3-3 PR-3-3-1)
- `InputRecorder`는 스텝 생성 경로와 별개로 Raw Event 스트림을 제공:
  - Signal: `raw_event_received(dict)`
  - Payload: `{timestamp, type, x, y, button, key_code, modifiers, hwnd}`
- 셀프 캡처 제외:
  - `lock_hwnd`를 기준으로 `WindowFromPoint`/Foreground HWND를 루트 핸들로 정규화해 자기 창 이벤트를 제외.
- 제어키 소비:
  - ESC/F12는 `control_event_received("stop_hotkey")`로만 전달되고 스텝 변환/큐 적재되지 않음.

### Smart Recorder Transform Core (Stage 3-3 PR-3-3-2)
- 신규 모듈: `app/core/smart_recorder.py`
- `SmartTransformer`:
  - Raw key stream을 받아 `type_text`/`key_press` 스마트 분리 생성
  - `typed_gap`(기본 1.5초) 기준 타임아웃 flush
  - flush 키: `backspace/delete/left/right/up/down/home/end/tab/enter`
  - modifier(`ctrl/alt/win`) 입력 시 텍스트 버퍼를 flush하고 키 스텝으로 분리
- `SmartProposal`:
  - 클릭 release 이벤트에서 `click_point` + `image_click` 동시 제안
  - 캡처 provider 기반 60x60 주변 이미지 저장(`images/record_prop_*.png`) 및 경로 연결

### Smart Recorder MainWindow Integration (Stage 3-3 PR-3-3-3)
- `MainWindow` 녹화 파이프라인 통합:
  - `InputRecorder.raw_event_received`는 HUD/보조 처리용 raw stream으로 연결됨
  - 표준 `Record` 종료 시 최종 스텝은 `InputRecorder` 결과를 그대로 사용해 정확 재현형 동작을 유지
  - Smart proposal 결과는 현재 표준 `Record` 결과를 덮어쓰지 않음
- 제안 선택 UI:
  - 일괄 선택: `모두 좌표`, `모두 이미지`
  - 혼합 선택: `개별 선택`(proposal 단위 yes/no)
  - 취소: smart 제안 삽입 생략
- 삽입/가시성:
  - 이 경로는 표준 재현형 녹화와 분리된 보조 흐름으로 유지
  - 삽입 구간 자동 선택/하이라이트
- 정리:
  - 미채택 임시 이미지 파일 자동 삭제(선택된 proposal 이미지는 유지)

### Smart Recorder MainWindow Integration Override (2026-03-09)
- Current standard `Record` path uses `InputRecorder` output only.
- `raw_event_received` is limited to HUD ripple / stop-hotkey assistance.
- Smart proposal materialization and proposal choice UI are no longer part of standard `Record`.

### Recording Overlay/HUD (Stage 3-3 PR-3-3-4)
- 신규 오버레이: `RecordingStatusOverlay` (`app/ui/overlay.py`)
  - 우측 상단 반투명 HUD: `Recording...` + 실시간 `Count`
  - 클릭 관통(`WA_TransparentForMouseEvents`), 항상 위(`WindowStaysOnTopHint`)
- 시각 피드백:
  - Raw click 이벤트 좌표에 Ripple 애니메이션 표시
- MainWindow 연동:
  - 녹화 시작 시 HUD show + count=0
  - SmartTransformer 출력 누적 시 count 갱신
  - 녹화 종료/중지/윈도우 종료 시 HUD hide
- 안정성:
  - 공유 오버레이 인스턴스가 Qt 수명주기에서 삭제된 경우 `get_shared()`에서 자동 재생성

### Stage 3-3 Final Integrity (PR-3-3-5)
- 녹화 배치 삽입 커맨드:
  - `AddRecordedStepsCommand`(`app/core/commands.py`)
  - managed image path를 추적해:
    - undo: 삽입 스텝 제거 + 미참조 임시 이미지 파일 삭제
    - redo: 캐시된 이미지 바이트(`png_bytes` 우선)를 파일로 복원 후 스텝 재삽입
- `SmartTransformer` 제안 이미지 스텝은 `png_bytes`를 함께 보관하여 파일 복원 가능.
- MainWindow는 녹화 결과 삽입 시 image proposal이 포함된 경우 `AddRecordedStepsCommand`를 사용.
- cleanup 보장:
  - 취소/실패/정상 종료 경로 모두 `_cleanup_record_temp_images(...)`를 통해 임시 이미지 정리.

### 규칙 적용 가드
- 규칙은 2단 구조로 운용:
  - `AGENTS.md`: Canonical 실행 규약(요약본)
  - `.cursorrules`: 상세 헌법/운영 노트(미러)
- 동기화는 단방향(`AGENTS.md -> .cursorrules`)이며 `SYNC_BLOCK_START/END` 블록만 자동 미러 대상으로 본다.
- `tests/test_rule_guard_steps_mutation.py`로 `app/main.py`의 `self.steps` 직접 변이를 자동 검출한다.
- `tests/test_rule_docs_sync.py`로 `AGENTS.md`와 `.cursorrules` 동기화 블록 일치 여부를 자동 검증한다.
- Multi-Agent 운영:
  - 기본 2-Agent(`Executor -> Guardian`)
  - Precision 트리거 시 3-Agent(`Planner -> Executor -> Guardian`)
  - 복붙 프롬프트/운영 절차는 `MULTI_AGENT_PROTOCOL.md`를 기준으로 사용한다.
- Git 거버넌스:
  - 로컬 Git 초기화 및 베이스라인 커밋 완료.
  - `.gitignore` 적용.
  - 헌법급 파일 편집은 edit+diff 검토/단독 변경 세트 원칙을 따른다.
  - Post-Task Commit Gate:
    - targeted 테스트 후 커밋
    - 리스크 트리거 시 full pytest 필수
    - 커밋 메시지에 테스트 결과 블록(`targeted`, `full suite`) 필수
  - Waste-Reduction Protocol:
    - 검색/열람 예산(`rg` 4회, 파일 open 2회)
    - write-first 검색 순서
    - full-file dump 금지 및 delta-only 출력
- 헬스 체크 기준: `python run_health_check.py` = `SYSTEM HEALTHY`.

## 8. CI/CD Gate
- GitHub Actions:
  - `.github/workflows/ci.yml` (Windows + Python 3.13, 테스트/헬스체크)
  - `.github/workflows/build-exe.yml` (manual dispatch, PyInstaller 빌드 artifact 업로드)
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
- 보조 운영 문서:
  - `CONSULT_TOKEN_TEMPLATE.md` (외부 자문 요청 시 토큰 절약 템플릿)
- 과거 단건 검토/개선 문서는 `archive/docs_legacy_20251124/`에서 참고용으로만 보관.
## UI Stage 3-4 PR-3-4-1 (Toolbar Cleanup)
- Top option toolbar:
  - Removed duplicate toolbar `Run/Stop` buttons.
  - Horizontal scrollbar policy set to `Qt.ScrollBarAlwaysOff`.
- Scenario left action panel:
  - Moved smart capture entry to left action grid as `스마트 캡처 (Ctrl+Alt+S)`.
  - `btnSmartCapture` now routes to `_open_smart_capture_menu` from left panel.
  - Core action buttons (`btnAddImg`, `btnAddAction`, branch/comment, run/stop, record, wizard/simulate) normalized to slim height (`>=32px`).
- Run/Stop behavior:
  - Left `btnRun` remains routed to `_on_run_button_clicked`.
  - Left `btnStop` is routed via `_on_stop_button_clicked` (path-unified dispatch).

## UI Stage 3-4 PR-3-4-2 (Design Minimalization)
- Left action panel buttons no longer rely on per-button inline color style.
- Button role styling is unified through global stylesheet classes:
  - `left-primary`, `left-secondary`, `left-capture`, `left-neutral`
  - `left-run`, `left-run-paused`, `left-stop`, `left-record`, `left-wizard`, `left-sim`
- Pause/resume run-state visual now switches by dynamic button class, not raw inline hex style.
- Toolbar visual density reduced via global QSS (lighter border/spacing/padding).

## UI Stage 3-4 PR-3-4-3 (3-Column Micro Grid)
- Scenario action panel grid is compacted into 3 columns:
  - Row0: `이미지+`, `동작+`, `캡처`
  - Row1: `분기`, `주석`, `녹화`
  - Row2: `실행`, `정지`, (reserved)
  - Row3: `마법사`, `조건`, `시뮬`
  - Row4: `센서 성공 가정` checkbox spans 3 columns
- Action button density:
  - `minimumHeight` reduced to `26px`
  - grid spacing set to `2`, margins set to `0`
- Global micro style in `DarkTheme`:
  - `QPushButton` font-size `9pt`, padding `1px 3px`, border-radius `2px`

## UI Stage 3-5 PR-3-5-1 (Menu-first Header Simplification)
- Header action model changed:
  - File/Edit core actions are menu-first (`File: Open/Save`, `Edit: Undo/Redo`).
  - Former toolbar icon group for Save/Open/Undo/Redo is removed.
- Action wiring preserved:
  - `Open -> load_macro`, `Save -> save_macro`
  - `Undo -> _do_undo`, `Redo -> _do_redo`
  - Shortcuts fixed: `Ctrl+O`, `Ctrl+S`, `Ctrl+Z`, `Ctrl+Y`
- Styling:
  - Added dark-theme menu styling (`QMenuBar`, `QMenu`, selected-state highlight).

## UI Stage 3-5 PR-3-5-3 (Left Panel Snap-Collapse / Min-Width Relaxation)
- Splitter behavior:
  - Left panel (`QSplitter` index 0) is explicitly collapsible.
  - Auto-snap collapse when width is below threshold (`_left_panel_snap_threshold_px`, default `80`).
  - Snap trigger also reacts to left splitter handle move position in threshold range.
- Min-width relaxation:
  - `ManagerTab` left/right containers, table, line edits, and action buttons are configured for narrow shrink.
  - Trigger tab root/list/buttons are configured for narrow shrink.
  - `left_tabs` minimum width set to `0`.
- Visual density safeguard:
  - Global `QPushButton` style allows `min-width: 0px` to reduce squeeze collisions under narrow panel states.

## Git Governance Hard Gate (Session 92)
- Repository-managed hooks:
  - `.githooks/commit-msg`: commit metadata/tests block schema validation
  - `.githooks/pre-commit`: staged-path guard for constitutional files and runtime artifacts
- Mandatory install:
  - `python tools/install_git_hooks.py`
  - expected config: `git config --get core.hooksPath` => `.githooks`
- Guarded artifact paths:
  - `__pycache__/`
  - `*.pyc`
  - `logs/run_events_*.jsonl`

## Git Governance Hard Gate V2 (Session 93)
- `pre-commit` additional enforcement:
  - block staged changes under `backups/`
  - block mixed staging of constitutional + non-constitutional files
  - require `.git/post_task_gate.json` proof file with:
    - current `HEAD` match
    - current staged hash match
    - targeted PASS
    - full-suite PASS when risk trigger active
- `post-task gate` tool:
  - command: `python tools/post_task_gate.py --targeted "<targeted pytest command>"`
  - computes staged hash from `git diff --cached --name-status`
  - detects risk trigger (`files>=5` or `stepdata/serialization/runner/signal`)
  - runs full `python -m pytest -q` automatically if risk
- `pre-push` gate:
  - runs rule guard tests:
    - `tests/test_rule_docs_sync.py`
    - `tests/test_rule_guard_steps_mutation.py`
    - `tests/test_git_hook_guards.py`

## Git Governance P0 Backstop (Session 94)
- `commit-msg` + gate proof coupling:
  - commit message `Tests` lines are parsed (`targeted`, `full suite`)
  - values must include summaries from `.git/post_task_gate.json`
  - mismatch => commit rejected
- CI server-side governance:
  - workflow runs `python tools/ci_governance_guard.py`
  - commit range source:
    - PR: `pull_request.base.sha .. pull_request.head.sha`
    - Push: `event.before .. github.sha`
  - checks per commit:
    - commit message schema (`Summary/Changes/Tests/Risks`, test lines)
    - commit-level file policy (`backups/`, constitutional file policy, artifact paths)

## DX Workflow Optimization (Session 95)
- Auto targeted test selection:
  - module: `tools/test_selector.py`
  - source: staged paths (`git diff --cached --name-only`) or explicit `--paths`
  - output: pytest target list/command for related tests
- Post-task gate:
  - `tools/post_task_gate.py --targeted auto`
  - records selected tests + summaries in `.git/post_task_gate.json`
  - full suite requirement only on high-risk paths:
    - `thread`, `signal`, `runner`, `StepData`, `serialization`, `BaseCommand`, `UndoStack`
- Standard task finish:
  - `tools/task_finish.py --subject "<commit subject>"`
  - runs post-task gate and writes `.git/TASK_COMMIT_TEMPLATE.md`
- Atomic scope enforcement:
  - `pre-commit` blocks over-threshold staged scope (files/changed-lines) to force split commits
- Repo artifact cleanup:
  - `tools/cleanup_repo_artifacts.py --apply`
  - removes tracked runtime/build artifacts from index (keeps local files)
- CI pipeline:
  - `changes` job (path filter)
  - `rule-guard` job (governance + rule tests)
  - `pytest` job (full test + health check)
  - pip cache enabled via `actions/setup-python`
 
## DX Guard Phase  
- New tool: tools/task_start_guard.py (clean-index preflight). 
- Governance rule: cleanup artifact deletions  require dedicated cleanup commit. 
- Gate rule: post_task_gate auto selection returns zero tests + app code changes =
 
## DX Guard Phase Two
- post_task_gate record schema includes timestamp and ttl_sec (30 minutes).
- git hook commit-msg contract includes mandatory Scope line.
- task_finish unifies gate execution and outputs Scope-guided commit template.
- is_risk_triggered skips blocked artifact paths before high-risk keyword scan.
- Current verification baseline: 510 passed, 1 skipped.

## DX Phase Three
- CI pipeline keeps `rule-guard` and `pytest` as parallel jobs, and pip download cache is handled via `actions/cache`.
- Scope-size warning thresholds are defined as warning level: 7 files and 500 changed lines.
- `tools/preflight_env.py` checks `git`, `python`, `pytest`, and available memory before `task_finish` runs gate logic.
- Current verification baseline: 532 passed, 1 skipped.

## Governance Automation / Asset Management (Session 102)
- Root asset map:
  - `docs/ASSET_MAP.md` is the governance inventory source for Product/Rule/DX/Docs/CI layers.
- Project audit tool:
  - `tools/project_audit.py` generates `project_audit_latest.md`.
  - Audit covers:
    - asset existence integrity
    - gate freshness TTL (30m, `.git/post_task_gate.json`)
    - docs mtime alignment (`now_spec.md`, `PROJECT_STATUS.md`, `DEV_LOG.md`, `docs/DOC_INDEX.md`, `docs/ASSET_MAP.md`)
- Task finish hardening:
  - `tools/task_finish.py` blocks partial update of the core docs trio (`PROJECT_STATUS.md`, `now_spec.md`, `DEV_LOG.md`).
  - `tools/task_finish.py` blocks docs modified-time drift over 5 minutes.
  - `tools/task_finish.py` always runs `python tools/project_audit.py` after gate success.

## Health Check Runtime Profile (2026-03-04)
- `run_health_check.py`는 기본적으로 런타임 스모크 테스트 세트만 실행한다.
  - `tests/test_e2e_runtime_orchestration.py`
  - `tests/test_scheduler_core.py`
  - `tests/test_trigger_engine_core.py`
  - `tests/test_image_dialog_presets.py`
  - `tests/test_matcher_quality.py`
  - `tests/test_stepdata_serialization.py`
- 실행 구조:
  - 부모 프로세스가 pytest 서브프로세스를 실행/출력 모니터링
  - 출력 정체가 `HEALTHCHECK_STALL_SEC`를 초과하면 강제 종료(`terminate` 후 필요 시 `kill`)
- 운영 토글:
  - `HEALTHCHECK_FULL=1`: 전체 `tests -q` 실행
  - `HEALTHCHECK_TEST_ARGS`: 커스텀 pytest 인자 우선 적용
# now_spec (Current Behavior Snapshot)

## UI Modernization - Stage 3-5 PR-3-5-2
- Options toolbar is logically grouped into:
  1. `Targeting`: target input + window finder/fix controls
  2. `Flags`: runtime behavior checkboxes (Auto Enter, Snap, Dry, Mini, CapFail, Human, Debug)
  3. `Excel`: excel mode toggle, data path picker, parallelism, progress/status
- Visual boundaries:
  - Vertical separators between groups
  - Dedicated Excel group style (`optExcelGroup`) with subtle background/border
- Consistent control sizing:
  - Toolbar line edits/spin controls aligned to `~26px` control height
- Compatibility notes:
  - Legacy compatibility hooks remain (`_opt_adv_row`, `_opt_row_layout`) for existing UI/tests.

## Stage 4 - PR-4-1 (Exception Hierarchy / Engine Guard)
- Added runtime exception hierarchy:
  - `MacroBaseError`, `ExecutionError`, `ResourceError`, `ActionError`, `TargetWindowError`
- Runner exception guard updates:
  - Step-level failures emit `step_exception` telemetry with `step_index` + `exception_type`.
  - Run-level fatal paths emit `run_exception` telemetry with typed exception metadata.
  - `finally` always performs safe cleanup and returns runner to `engine_state = IDLE`.
  - `_validate_step_resources` performs preflight checks for missing image resources before step handler execution.
  - Dynamic image path tokens (`{{...}}`, `#`, `@`, `?`) are skipped in precheck and resolved at runtime, while static paths keep fail-fast validation.

## Stage 4 - PR-4-2 (Self-Healing Retry / Recovery)
- Smart retry on resource failures:
  - For image-resource step types (`image_click`, `wait_for_image`, `image_branch`, `compare_images`), `ResourceError` triggers bounded retry flow.
  - Structured telemetry:
    - `step_retry` (attempt/max/delay/exception metadata)
    - `step_retry_success` (attempt count on eventual success)
  - Defaults: `attempts=3`, `delay=500ms`; optional per-step override via `resource_retry_count` / `resource_retry_delay_ms`.
  - Retry exhausted on `ResourceError` is escalated as `ExecutionError` after emergency cleanup.
- Safe-state recovery on action failures:
  - On `ActionError` and final retry failure, runner executes self-heal routine and emits `step_recovery`.
  - Recovery actions:
    - release runtime controls (mouse/key up)
    - non-dry-run only: ESC press + mouse move to home `(10,10)`
  - `run_finished` telemetry includes `retry_count` and `recovery_status`.
  - `post_task_gate.json` includes runtime self-healing summary (`retry_count`, `recovery_status`, `recovery_log`).

## Governance Master Audit (Ultimate Executor 반영)
- `docs/ASSET_MAP.md`는 6대 영역( Product / Rule Guard / DX Tools / Verification / Resources / Infrastructure ) 기준의 마스터 자산 지도로 운영.
- `tools/project_audit.py`는 아래 항목을 한 번에 점검:
  - Verification Health(테스트 파일 수, gate 존재 상태)
  - Asset Integrity Matrix(6대 영역별 경로 존재 여부)
  - Gate Freshness(TTL 30분)
  - Resource Snapshot(images/logs 개수)
  - Docs Sync Health + Maintenance Guide
- `tools/task_finish.py`는 문서 3종(`PROJECT_STATUS.md`, `now_spec.md`, `DEV_LOG.md`) 수정시간 격차가 5분을 초과하면 실패로 차단.
- `tools/task_finish.py`는 게이트 성공 시 `python tools/project_audit.py`를 항상 실행한다.

## DX Feedback Loop (Knowledge Harvesting / Upstream Sync)
- `dx_operating_pack/tools/capture_lesson_draft.py`
  - 변경 범위(`base..head`) 또는 staged diff(`--from-staged`)를 분석.
  - `LESSONS_LEARNED_DRAFT` 초안을 append하고, `feedback/LATEST_INSIGHT.yaml`을 함께 생성.
  - insight payload에는 변경 파일 수, reusable 변경 목록, lessons 추가 라인을 포함.
- `tools/post_task_gate.py` / `dx_operating_pack/tools/post_task_gate.py`
  - 게이트 성공 시 지식 수확 단계를 자동 실행.
  - 필요 시 `--skip-harvest`로 생략 가능.
- `dx_operating_pack/tools/push_dx_feedback.py`
  - 로컬 outbox 번들을 생성(`feedback/outbox/<timestamp>_<head>/...`).
  - 포함 자산:
    - `feedback_manifest.json`
    - `LATEST_INSIGHT.yaml`
    - `LESSONS_LEARNED.md`
    - `reusable_changes/*`(변경분만)
  - `--remote-url` + `--push` 지정 시 중앙 DX Repo inbox로 반영.
- `dx_operating_pack/tools/promote_dx_feedback.py`
  - 중앙 DX Repo의 `feedback/inbox` 번들을 스캔해 승격 리포트 생성.
  - `--apply` 시 reusable 변경 반영 + lessons draft append + `feedback/processed` 이동까지 수행.
- 루트 래퍼 제공:
  - `tools/capture_lesson_draft.py`
  - `tools/push_dx_feedback.py`
  - 현재 프로젝트에서도 동일 명령으로 DX feedback 루프 사용 가능.
 
## DX Feedback Loop Path Policy 
- Default lesson draft output path: `dx_operating_pack/docs/LESSONS_LEARNED_DRAFT.md` (primary). 
- Root `docs/*` path remains as compatibility fallback, not as primary output target.

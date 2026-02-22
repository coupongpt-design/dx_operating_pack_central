# Project Technical Specification (now_spec)

## 1. Project Overview
- Python 3.14 / PyQt5 기반 게임 자동화 봇: 매크로 작성·실행, 화면 인식(OCR/이미지), 인간적 입력을 제공.
- 목표: 안티치트 회피(인간적 입력, 창 포커싱), 모듈성(Logic-UI 분리, Command 패턴), 안정성·가시성(테스트/헬스체크/메트릭).

## 2. Tech Stack & Dependencies
- UI: PyQt5 (Widgets/QtCore/QtGui), QSettings.
- Vision: opencv-python (cv2), pytesseract + Tesseract-OCR, numpy.
- Capture/Input: mss(화면 캡처), pyautogui(입력; HumanMouse 래핑), pynput(InputRecorder).
- Windows Control: pywin32(win32gui/con/process), psutil(프로세스명); 없으면 안전하게 무시.
- QA: pytest, pytest-qt, pytest-mock, coverage; 스크립트 run_health_check.py, auto_inspect.py.

## 3. System Architecture
- UI Layer: `MainWindow`(스텝 목록, 실행/정지/녹화, 타겟 창 입력·Find/Fix/Selector), 각종 다이얼로그(`WindowSelectorDialog` 등).
- Logic Layer: `MacroRunner`(QThread; 스텝 실행, human_mode, OCR/브랜칭/서브스크립트, optional 타겟 포커스), `InputRecorder`(pynput, 필터/리샘플/메트릭).
- Core Utilities: `WindowManager`(find/activate/force_refresh 1px shake), `ImageProcessor`(OCR 전처리·숫자 추출), `HumanMouse`(베지에 곡선+이지ング+지터), `UndoStack`/Commands(Add/Remove/Edit/Move).
- Data Flow: 매크로 파일(JSON/역호환 .macro) 로드 → meta/repeat/steps 파싱 → UI 반영 → Runner 시작 → 필요 시 타겟 창 활성화 → mss 캡처 → Vision/OCR → HumanMouse/pyautogui 액션 → 로그/신호/오버레이 업데이트.

## 4. Key Features
- Undo/Redo: Command 패턴, 모든 CRUD/Move/중복을 `_push_command` 경유, Ctrl+Z/Ctrl+Y.
- Sub-scripts: `run_macro` 액션, 콜 스택+재귀 가드(깊이 5), 변수 컨텍스트 공유.
- Window Management: 제목 기반 find/activate, 1px 흔들기로 렌더링 글리치 복구; 제목 비어있거나 미발견 시 경고 후 계속.
- Recorder: 큐 한도(기본 5000), 거리+시간 하이브리드 필터(지터 제거), 드래그 경로 리샘플링(~20점), 메트릭 반환→UI 표시, 안전 stop.
- Stability/QA: run_health_check.py, auto_inspect.py, 광범위한 pytest(시뮬레이션/스트레스/브랜칭/OCR/입출력/메타/윈도우).

## 5. Data Models & File Format
- `StepData`: id/name/type, pre_delay_ms, 이미지/타깃, key/text, OCR 필드(roi/invert/high_contrast/var), branching(`jump_if` with step_id 우선), run_macro(target_macro_path), loop/log/comment 등.
- `ActionType`: image/text/key/drag/scroll/ocr_store/ocr_check/jump_if/run_macro 등.
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
- 스케줄러 경로에서 macro load/runner start 실패를 구분하고, 실패 시 `notify_macro_finished(False)`로 시퀀스 정체를 방지.
- 트리거 단독 실행(메인 러너 없음)에서도 시작 실패 예외를 안전하게 처리하고 `trigger_runner`를 정리.

## 7. Test & QA Baseline
- Core + Integration + E2E 테스트를 분리 운영:
  - 런타임 오케스트레이션 E2E: `tests/test_e2e_runtime_orchestration.py`
  - 스케줄러 코어: `tests/test_scheduler_core.py`
  - 트리거 엔진 코어: `tests/test_trigger_engine_core.py`
- 최신 로컬 기준: `python -m pytest -q` = `231 passed, 1 skipped`.
- 헬스 체크 기준: `python run_health_check.py` = `SYSTEM HEALTHY`.

## 8. CI/CD Gate
- GitHub Actions: `.github/workflows/ci.yml` (Windows + Python 3.13).
- 필수 게이트:
  1. `python -m pytest -q`
  2. `python run_health_check.py`
- 환경값: `QT_QPA_PLATFORM=offscreen`, `IMAGEMACRO_TRIGGER_START_LOG=0`.

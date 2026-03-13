# 구현 시스템 인벤토리

이 문서는 현재 프로젝트에 구현된 시스템을 한 번에 파악하기 위한 기준 문서다.
정리 기준은 아래 2단계다.

1. canonical 문서 기준 재구성
   - `PROJECT_STATUS.md`
   - `now_spec.md`
   - `docs/DOC_INDEX.md`
   - `docs/ASSET_MAP.md`
   - `docs_for_ai/CONTEXT_SNAPSHOT.md`
2. 코드 대조로 추가 확인
   - `app/core/data_orchestration.py`
   - `app/core/session_adapter.py`
   - `app/core/trigger_engine.py`
   - `app/core/template_processor.py`
   - `app/core/run_history.py`
   - `app/core/ocr_runtime.py`

## 1) 제품 핵심 시스템

### 1. 매크로 편집/저장 시스템
- `StepData` 기반 스텝 모델
- 이미지 스텝 / 액션 스텝 / 조건 분기 / OCR / 파일 액션 / 서브매크로 편집
- `UndoStack` + Command 패턴 기반 CRUD / 이동 / 중복 / 재정렬
- JSON 저장/로드
- `.macro` 패키지 저장/로드
- 메타데이터(`target_window`, repeat, assets) 저장/복원

### 2. 실행 엔진 시스템
- `MacroRunner` 중심 스텝 실행 엔진
- 이미지 기반 클릭/대기/드래그/분기
- 키보드/마우스/텍스트 출력
- `run_macro` 서브스크립트 실행
- 분기/점프/루프/반복
- 비교/스크린샷/파일 액션 실행
- 실패 정책 및 런타임 상태 복구

### 3. 이미지 인식 / OCR 시스템
- OpenCV 기반 이미지 매칭
- grayscale / blur / CLAHE / edge / sharpen 등 전처리
- color match / alpha mask / auto foreground mask
- relative target image search
  - anchor 이미지 기준 2차 타겟 탐색
  - `px` / `ratio` 탐색 영역 지원
- Tesseract OCR 기반 텍스트 인식
- OCR 값 저장 / OCR 조건 분기 / OCR 점프

### 4. 입력 / 녹화 / 재현 시스템
- `InputRecorder` 기반 정확 재현형 녹화
- 클릭 / 드래그 / 스크롤 / 키 입력 기록
- scroll 위치 보존 재생
- `pre_delay_ms` 보존
- `HumanMouse` 기반 인간형 마우스 이동
- 글로벌 입력 락(`GlobalInputManager`)
- 글로벌 핫키
  - Run / Stop / Record / Pause / Kill
  - Add Image / Add Action

### 5. 캡처 / 위저드 / 보조 작성 시스템
- `Smart Capture`
- Visual Image Capturer
- Conditional Wizard
- Scenario Wizard
- custom_flow 편집
- Logic Path Simulator
- Smart Snap
- 좌표 가이드 오버레이 / 녹화 HUD / 좌표 프리뷰

### 6. 창 / 세션 / 스케줄 / 트리거 시스템
- `WindowManager`
  - 창 찾기 / 활성화 / 1px shake refresh / selector
- `MacroScheduler`
  - 시간 기반 실행 / retry 정책 / 상태 라벨 연동
- `TriggerWatcher`
  - 트리거 감시 / trigger run_macro 실행
- `SessionManager`
  - Multi-Manager 세션 라운드로빈 / pending recovery / daily reset
- Manager Tab
  - Start All / 세션별 runner 자동 연결

### 7. 데이터 기반 자동화 시스템
- CSV / XLSX 로드
- `load_data_file`
- `{data}` / `{column}` 토큰 바인딩
- Excel 기반 실행 보조 UI
- Data Orchestration V2 계열 흐름

### 8. 런타임 관측 / 분석 시스템
- JSONL 실행 로그
- 실행 이력 파싱 / 요약 / 뷰어
- Runtime observability 신호
- `run_health_check.py`
- `run_smoke_suite.py`
- `auto_inspect.py`

### 9. 초보자 진입 / 사용성 시스템
- quick-start card
- 초보자용 버튼명 정리
- 옵션 툴바 기본/고급 분리
- 이미지 스텝 다이얼로그 스크롤/높이 제한
- 좌표/타겟 선택 UX 개선

## 2) DX / 거버넌스 시스템

### 1. 작업 규칙 / 헌법 시스템
- `AGENTS.md`
- `.cursorrules`
- session gate / mode policy / waste-reduction protocol
- `MainWindow.steps` 직접 변이 가드
- rule docs sync 가드

### 2. Git 게이트 / 훅 시스템
- `install_git_hooks.py`
- pre-commit / commit-msg / pre-push 가드
- `post_task_gate.py`
- `task_finish.py`
- CI governance guard

### 3. DX Pack 설치 / 동기화 시스템
- `setup_dx.py`
- `sync_dx_pack.py`
- branch-aware sync
- 보호 파일 복원 정책
- bootstrap / transplant / integrity check

### 4. DX Feedback Loop / 중앙 PACK 시스템
- lesson draft harvest
- latest insight capture
- outbox bundle 생성
- 중앙 inbox 업로드
- central promote/apply
- central pack operating model

### 5. 멀티 에이전트 / AI 협업 시스템
- Multi-role AI orchestration
- Planner / Implementer / Reviewer / Tester / Documenter 체인
- heuristic backend
- Gemini CLI backend
- semi-auto backend
  - precision 작업에서 planner/reviewer/tester 자동 라우팅

## 3) 코드 대조로 추가 확인된 시스템

아래는 문서에서 상대적으로 덜 드러나지만 코드상 분명히 존재하는 지원 시스템이다.

### 1. 템플릿 치환 강제 계층
- `TemplateProcessor`
- 텍스트 출력 전 placeholder 치환의 중앙 경로
- raw placeholder 출력 금지 규칙의 실제 구현 축

### 2. OCR 런타임 설정 계층
- `ocr_runtime`
- Tesseract 경로 탐지 / 저장 / 적용 / 상태 확인

### 3. 실행 이력 코어 API
- `run_history`
- 실행 로그 로드 / 요약 / 목록화
- 실행 이력 뷰어의 기반 계층

### 4. 트리거 코어 감시 계층
- `TriggerWatcher`
- 문서에는 트리거 기능으로 보이지만, 코드상 별도 감시 코어로 분리돼 있음

### 5. 데이터 오케스트레이션 큐 계층
- `OrchestrationJob`
- `ResultAggregator`
- `JobQueueManager`
- 데이터 실행 흐름을 큐/집계 단위로 다루는 보조 계층

### 6. 세션-러너 어댑터 계층
- `SessionJobAdapter`
- 세션 구동과 runner 실행을 연결하는 래핑 계층

## 4) 현재 구조상 한 몸처럼 움직이는 핵심 축

실전 운영에서 특히 같이 봐야 하는 묶음은 아래다.

1. 편집 + 저장 + 실행
   - `StepData` / dialogs / macro_io / `MacroRunner`
2. 녹화 + 재현 + 입력
   - `InputRecorder` / runtime replay / hotkeys / `HumanMouse`
3. 이미지/OCR + 분기
   - image matching / OCR / jump/store / relative target
4. 세션 + 스케줄 + 트리거
   - `SessionManager` / `MacroScheduler` / `TriggerWatcher`
5. DX 작업 흐름
   - `task_start_guard` / 구현 / `post_task_gate` / `task_finish`
6. 중앙 PACK 환류
   - harvest / push_dx_feedback / promote / sync_dx_pack

## 5) 정리 메모

- 제품 기능 시스템, DX 시스템, 프로젝트 전용 QA 시스템, 중앙 PACK 시스템이 모두 공존한다.
- 신규 프로젝트 재사용성 기준에서는 `dx_operating_pack/**`가 가장 중요한 이식 단위다.
- 공용 QA 운영 기준도 이제 `dx_operating_pack/docs/CROSS_PROJECT_QA_PLAYBOOK.md`에 들어가 있어 DX Pack 설치/최신화만으로 같이 내려간다.
- 프로젝트 전용 문서는 계속 `docs/dev/**`에 남겨서 로컬 운영 기준을 분리한다.

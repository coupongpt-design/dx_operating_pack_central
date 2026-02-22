# 프로젝트 상태

## 코어 모듈
- **MacroRunner**: 스텝 실행(OCR, 분기, 서브스크립트, 휴먼 모드 입력), 콜 스택 및 타겟 창 활성화 관리.
- **ImageProcessor**: OCR 전처리(확대/임계/반전) 및 숫자 추출.
- **HumanMouse**: 베지에/이지ング 마우스 움직임, 클릭/드래그 래핑(failsafe 준수).
- **UndoStack/Commands**: Add/Remove/Edit/Move에 대한 커맨드 패턴과 Undo/Redo.
- **WindowManager**: 창 찾기/활성화/강제 리프레시(1px shake); pywin32 없으면 안전히 무시.
- **SessionManager**: 다중 세션 라운드로빈/일일 리셋 코어(ManagerTab와 연동).
- **MultiRoleAIOrchestrator**: 다중 역할(기획/구현/리뷰/테스트/문서) 순차 실행 파이프라인, auto 모드(Compact/Precision) 선택, 커스텀 역할 JSON 로딩 지원.

## 완료된 주요 기능 [Completed]
- OCR & 이미지 매칭 + 디버그 오버레이.
- 조건 분기(`jump_if`) 스텝 ID 우선 점프; **고급 조건 빌더**: Jump If UI에 변수 자동완성(OCR_STORE 스캔 + `loop_index`/`loop_count`).
- 서브스크립트(`run_macro`) 지원: 콜 스택, 공유 변수 컨텍스트, 재귀 가드(깊이 5).
- Undo/Redo 완전 연결: `MainWindow` CRUD/이동/복제 모두 `_push_command` + UndoStack, Ctrl+Z/Ctrl+Y.
- 녹화기 최적화: 거리+시간 필터, 드래그 경로 리샘플링, 메트릭 UI 표시.
- 창 관리: 대상 창 입력 + Find/Fix/Selector UI, 실행 전 자동 포커스/리프레시(창 미발견 시 경고 후 진행).
- 시나리오 마법사: 기존 수동 편집과 분리된 별도 버튼/다이얼로그, `추천/전체/검색` 템플릿 선택 + 필수 입력 + 생성 미리보기/검증 + 삽입 위치 선택(선택 다음/끝) 지원. 템플릿 카탈로그 46종(채팅/키보드/마우스/파일/OCR 분기 + 리니지류 실전 템플릿) 운영.
- 데이터 주도 자동화 V2:
  - `load_data_file`가 CSV/XLSX(`openpyxl`)를 공통 로드
  - 시나리오 마법사 입력 필드에 컬럼 매핑 버튼(`{column}` 토큰 삽입) 추가
  - 템플릿 생성 전 데이터 검증(누락 컬럼 Error, 빈 행 Warning, 데이터 파일 파싱 상태 안내) 추가
- 사용자 템플릿 관리(B안): 기본 템플릿 읽기 전용 + 팝업 `복제 저장`/`사용자 편집`/`사용자 삭제` 지원.
- custom_flow 편집 UI 연동 완료:
  - 사용자 템플릿 편집 팝업에서 `흐름 편집 열기` 제공
  - 스텝 사이 `+ 스텝 추가`(샌드위치 삽입), 시스템/사용자 스텝 시각 분리
  - 삭제 시 Lazy-Check 경고 + 자동 참조 보정
  - 저장 전 상세 검증 모달(Error/Warning) 연동
- Runtime Observability 연동:
  - Runner 시그널 확장(`stepStarted`, `stepSucceeded`, `stepFailed`)
  - custom_flow 스텝에 `source_step_id` 메타 주입
  - 메인 UI에서 현재 실행 스텝/마지막 실패 스텝 상태바 표시 + 실패 스텝 붉은 하이라이트
- 구조화 실행 로그(JSON Lines) 추가:
  - `MacroRunner`가 `run_id`를 각 실행마다 부여
  - `step_started`/`step_succeeded`/`step_failed` 이벤트를 `.jsonl`로 기록
  - `duration_ms`(스텝/런 단위)와 실패 `error`를 함께 남겨 사후 분석 가능
  - 구현 파일: `app/utils/structured_jsonl.py`, `app/core/runner.py`
- 긴급 제어(Option A) 추가:
  - 글로벌 핫키 `F10` 일시정지/재개, `F12` 긴급 종료(Kill)
  - `MacroRunner`에 스레드 안전 pause/resume(`threading.Event`) 적용
  - 구조화 로그에 `run_paused`/`run_resumed`/`run_killed` 이벤트 기록
  - Hotkey Settings에 `Pause/Resume`, `Emergency Kill` 항목 노출 + 중복 단축키 충돌 검증
  - Paused 상태에서 Run 버튼 주황 강조(`▶ 재개`) + 상태바 `PAUSED` 시각화
- 범용성 강화(Option B) 추가:
  - `wait_for_image` 런타임 스텝 추가(이미지가 나타날 때까지 폴링 대기, 성공/실패 분기 연계)
  - `click_anchor` 실동작 반영(`center/top-left/top-right/bottom-left/bottom-right`)
  - `StepData.anchor_image_path`/`image_path` 지원으로 파일 경로 기반 앵커 이미지 로드
  - 시나리오 마법사 custom_flow 편집기에서 `image_click`/`wait_for_image` 스텝 삽입 지원
  - `.macro` 입출력에서 `wait_for_image` 이미지 에셋 저장/복원 지원
- 템플릿 생태계(Option C) 추가:
  - `.macro` 저장 시 패키지 구조를 `template.json + assets/`로 표준화
  - 기존 `scenario.json + images/` 포맷은 로드 단계에서 완전 역호환 유지
  - 패키지 내부 이미지 경로 로드 시 `../`, 절대경로, 드라이브 경로를 차단해 unsafe 경로 참조를 방어
  - `.macro` 저장/로드에서 `meta.target_window` 보존 및 복원 지원
- 배포 파이프라인(MVP) 추가:
  - PyInstaller 스펙 파일 `ImageMacro.spec` 추가(`template catalog`, `USER_GUIDE.md`, 샘플 `.macro` 데이터 번들)
  - 빌드 스크립트 `tools/build_exe.ps1` 추가(정리 → 빌드 → 선택적 smoke launch)
  - 수동 실행 GitHub Actions 워크플로우 `.github/workflows/build-exe.yml` 추가(artifact 업로드)
  - 런타임 리소스 경로 유틸 `app/utils/runtime_paths.py` 도입(`sys._MEIPASS` 대응)
  - OCR 경로 설정 코어 `app/core/ocr_runtime.py` 및 Settings 메뉴 `OCR (Tesseract) Path...` 추가
- 실행 이력 뷰어(MVP) 추가:
  - Help 메뉴 `Execution History`에서 실행 이력 다이얼로그 오픈
  - 좌측: 실행 목록(run_id, 상태, 총소요, 실패 수, 병목 스텝)
  - 우측: 선택 실행의 이벤트 타임라인(`step_name`, `duration_ms`, `error`)
  - 코어 파서: `app/core/run_history.py`, UI: `app/ui/history_viewer.py`
- 삭제 Lazy-Check 코어 추가: 참조 스텝 탐색(`find_references_in_blueprint`)과 삭제 시 자동 참조 보정(`delete_step_with_lazy_repair`) 제공.
- QA/헬스 체크: `run_health_check.py`, `auto_inspect.py`, 광범위한 pytest 시나리오.
- E2E 테스트 인프라: 풀 라이프사이클(편집→Undo/Redo→저장→불러오기→실행) 자동 검증 완료.
- 이미지 스텝: `loop_until_hide` 옵션으로 템플릿이 사라질 때까지 반복 클릭 지원, 값 변환 안전성 개선.
- 스케줄러 실패정책 UX 강화: `continue/stop/retry` 정책 + 재시도 옵션(`max_retries`, `retry_delay_ms`) + 실행/재시도/중단 상태 라벨 연동.
- 드래그-드롭 재정렬 Undo/Redo: `sync_order` + `ReorderStepsCommand` 경로 통합 및 회귀 테스트 보강.
- 액션 다이얼로그 안정화: `Cancel` 시 스텝이 저장되던 경로 차단, `NotImageDialog`의 중복 Run Macro UI 그룹 제거.
- 이미지 매칭 확장 보강: `High Quality + Color Match` 조합에서 옵션(`hq_color_bg_robust`) 활성 시 gray/CLAHE/edge fallback 패스를 추가해 배경 변화 대응 강화.
- 투명 PNG 전경 매칭: 알파 마스크 기반 템플릿 매칭/컬러게이트 적용(`alpha_mask_enable`)으로 배경 영향 완화.
- 불투명 PNG 전경 매칭: 알파 없는 템플릿에서도 자동 전경 마스크(`auto_fg_mask_enable`)를 생성해 배경 영향 완화.
- 자동 전경 마스크 튜닝: BG percentile/dynamic scale/min distance를 스텝별로 조절 가능.
- 자동 전경 마스크 프리셋: `Stable/Accurate/Aggressive` 빠른 적용 + 수동 조정 시 `Custom` 자동 전환.
- 자동 전경 프리셋 UX: 프리셋 설명 힌트 + 템플릿 기반 `Suggest` 추천 버튼 제공.
- 자동 전경 추천 가시성: Suggest 결과에 confidence(%)와 근거 지표(std/edge density) 표시.
- 자동 전경 추천 임계값 설정: Suggest 분류 기준(`std/edge low/high`)을 스텝별로 직접 조정하고 저장 가능.
- 실사용 스모크 게이트: `run_smoke_suite.py`(quick/full) + `SMOKE_TEST_CHECKLIST.md`로 자동/수동 점검 절차 표준화.
- 윈도우 셀렉터 회귀 복구: pywin32 미가용 환경에서도 창 목록 열거 폴백(`ctypes`) 지원, 빈 목록 안내/표시 가독성 개선(`[]` 제거).
- 시작 타겟 정책 정리: 앱 시작 시 Target 입력은 항상 빈 값으로 시작(이전 세션 타겟 자동 로드 비활성), 매크로 파일 로드 시 `meta.target_window`는 그대로 UI에 반영.
- 작업 규칙 토큰 최적화: `.cursorrules`를 경량화(중복 규칙 제거)하고 `Token Efficiency Protocol`을 기본 정책으로 반영. 외부 자문용 `CONSULT_TOKEN_TEMPLATE.md` 추가.
- 규칙 적용 보강: `AGENTS.md` 동기화, Precision 기계식 트리거(파일 수/StepData/직렬화/스레드/러너 분기) 추가, Session Start 게이트(현재 포커스 2줄 요약 + 모드 선언) 강화.
- 실행 가드 추가: `tests/test_rule_guard_steps_mutation.py`로 `MainWindow.steps` 직접 변이(`append/pop/insert/...`) 금지 자동 검증.
- 규칙 체계 2단 구조 전환: `AGENTS.md`는 30~60줄 실행 규약(정본), `.cursorrules`는 상세본(미러/운영 노트)으로 분리.
- 동기화 루프 방지: `AGENTS.md -> .cursorrules` 단방향 동기화 + `SYNC_BLOCK_START/END` 부분 미러 정책으로 고정.
- 동기화 검증 자동화: `tests/test_rule_docs_sync.py`로 정본/미러 동기화 블록 일치 여부를 강제.
- Multi-Agent 운영 프로토콜 도입:
  - 기본: `Executor -> Guardian` (2-Agent)
  - 승격: Precision 트리거 시 `Planner -> Executor -> Guardian` (3-Agent)
  - 규칙 파일 변경(`AGENTS.md/.cursorrules/규칙 가드 테스트`)은 단독 변경 세트 원칙.
- 복붙용 운영 문서: `MULTI_AGENT_PROTOCOL.md` 추가(Planner/Executor/Guardian 프롬프트 포함).
- Git 운영 체계 도입:
  - 로컬 Git 초기화 + 베이스라인 커밋 생성.
  - `.gitignore` 추가.
  - 헌법급 파일(`AGENTS.md`, `.cursorrules`, 규칙 가드 테스트 2종)에 대해 delete/recreate 금지, edit+diff 검토, 단독 변경 세트 원칙 명시.
- 멀티 역할 AI 실행 코어 추가:
  - `app/core/multi_role_ai.py` (역할 오케스트레이션, auto 모드 전환, 결과 요약/렌더링)
  - `tools/run_multi_role_ai.py` (CLI 실행 진입점)
  - `app/core/multi_role_ai_roles.example.json` (커스텀 역할 정의 예시)
  - `tests/test_multi_role_ai.py` (역할 체인/모드 전환/검증 단위 테스트)

## 파일 포맷
- JSON 저장: 메타데이터 포함 JSON(`meta`/`repeat`/`steps`), 레거시 리스트 JSON 역호환.
- `.macro` 저장: ZIP 패키지(`template.json` + `assets/*.png`) 구조.
- `.macro` 로드: 신규(`template.json`/`assets`) + 레거시(`scenario.json`/`images`) 동시 지원.
- 메타(`target_window`) 저장/로드 시 UI 자동 반영.

## 현재 단계
- **v1.2 - Stable Core + Packaging MVP**: 코어/E2E 안정화 + `.exe` 빌드 파이프라인 초안 안착.

## 최신 검증 기준
- 전체 테스트: `python -m pytest -q` => `366 passed, 1 skipped`
- 스모크(quick): `python run_smoke_suite.py --quick` => `PASS`
- 스모크(full): `python run_smoke_suite.py` => `PASS` + `SYSTEM HEALTHY`

## 알려진 이슈 / 낮은 우선순위
- NotImageDialog UI 리팩터는 안정성 우려로 보류.
- 패키징 고도화 과제:
  - Tesseract 바이너리 동봉 전략(현재는 경로 설정형 MVP)
  - 실제 사용자 환경(권한/백신/해상도) smoke 배포 검증
- 복잡 배경에서의 자동 전경 분리 고도화(알파 없는 템플릿 대상)와 특징점 매칭 튜닝은 추가 개선 여지로 유지.
- `Multi-Manager`는 `Start All`에서 runner 자동 생성/연결을 시도하지만, 스크립트 경로 미지정/로드 실패 세션은 `pending` 상태로 남을 수 있음.

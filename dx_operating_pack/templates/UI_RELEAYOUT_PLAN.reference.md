# UI 현대화 Stage 1 (MVP) 설계안

## 0) Session Gate
- Current Focus (2줄)
  - 현재 포커스는 Excel 데이터 오케스트레이션과 멀티세션 실행 안정성(치환/입력락/실행 경로 일관성) 유지다.
  - UI는 기능이 누적되어 필수 제어와 부가 옵션이 혼재되어 있고, 고급 시나리오 작성 시 인지 부하가 높다.
- Mode: `Precision`
  - 사유: 상단 툴바/실행 제어/상태 가시성 재배치는 `app/main.py` 중심 다중 파일 수정(5개+)과 회귀 위험이 크다.

## 1) 목표
`Setup -> Design -> Monitor` 흐름을 화면에 명확히 드러내고, 필수 제어를 항상 보이게 유지한다.

- Setup: 타겟 창, 실행 모드(일반/Excel), Excel 파일, 병렬도, Run/Stop
- Design: 스텝 편집/시나리오 구성
- Monitor: 진행률/상태/로그/실패 지점

## 2) 현재 구조 요약 (코드 기준)
`app/main.py`의 옵션 툴바는 이미 `QScrollArea` 기반이며 다음 요소가 1열에 혼재되어 있다.

- Excel 관련: `chkExcelDataMode`, `spExcelParallelism(P:)`, `edExcelDataPath`, `btnExcelDataPick`, `pbExcelProgress`, `lblExcelStatus`
- 실행 보조: `chkAutoEnterAfterText`
- 부가 옵션: `chkDry`, `chkAutoMin`, `chkCaptureFail`, `chkHumanMode`, `chkDebugOverlay`
- 타겟 제어: `edTargetTitle`, `btnSelectTarget`, `btnFindTarget`, `btnFixWindow`
- Run/Stop은 좌측 시나리오 버튼 영역과 액션(`act_run`, `act_stop`)에 존재하나, 툴바에서 핵심 제어로 즉시 인지되지는 않음.

## 3) Stage 1 레이아웃 설계 (변경 후)

### A. 핵심 제어(Core)와 부가 옵션(Advanced) 분리
- 상단을 2층 구조로 재배치:
  1. `Core Control Strip` (항상 노출)
  2. `Advanced Options Strip` (접기/펼치기)

#### 3.1 Core Control Strip (고정 노출)
- 그룹 1: Target
  - `Target:` + `edTargetTitle` + `btnSelectTarget` + `btnFindTarget`
- 그룹 2: Mode
  - `Execution Mode` 토글(일반/Excel) = `chkExcelDataMode` 중심
  - Excel ON일 때만 Excel 입력군 활성화
- 그룹 3: Excel Core
  - `edExcelDataPath`(elide), `btnExcelDataPick`, `spExcelParallelism(P:)`
- 그룹 4: Run Control
  - `Run`, `Stop` (툴바에도 명시 노출; 기존 버튼/액션과 동일 슬롯 공유)
- 그룹 5: Monitor Mini
  - `pbExcelProgress`, `lblExcelStatus` (숫자 강조)

#### 3.2 Advanced Options Strip (접힘 기본값)
- `Dry Run`, `Mini Mode`, `Capture Fail`, `Human Mode`, `Show Debug Overlay`, `Auto Enter`
- 기본은 축소 상태, 사용자가 `Advanced` 토글로 펼침

### B. Excel Mode 시각 강조
- `chkExcelDataMode == ON`일 때:
  - Core Strip 배경에 연한 강조색(예: 녹색 계열) 적용
  - 배지 텍스트 노출: `BATCH MODE ACTIVE`
  - 상태바 문구도 `Excel Batch Active`로 보강
- `OFF`일 때:
  - 강조 제거 + 기본 실행 모드 표시

### C. 정보 우선순위 시각화
- 경로 표시: `ElidedPathLineEdit` 유지 + 최소폭 정책 보강
- 숫자 가시성:
  - `P:`와 진행률 텍스트 크기/굵기 상향
  - 상태 텍스트(`Idle/Running/Failed`) 색상 규칙 고정

## 4) 배치도 (Before / After)

### Before (개념)
`[Excel][P][Path][Pick][Progress][Status][AutoEnter]|[Dry][Mini][Capture][Human][Debug][Target...]`

### After (개념)
- Row 1 (Core):  
  `[Target Group] [Mode Group] [Excel Core Group] [Run/Stop] [Mini Monitor]`
- Row 2 (Advanced, collapse):  
  `[Dry][Mini][Capture][Human][Debug][AutoEnter]`

## 5) 구현 범위(예상 파일 5개+)
- 필수
  - `app/main.py` (툴바 구조/그룹 재배치/모드 강조/상태 문구)
  - `app/ui/widgets.py` 또는 신규 위젯 파일 (Core/Advanced strip 추출 시)
  - `tests/test_excel_toolbar_responsive.py` (반응형/가시성 회귀)
  - `tests/test_ui_orchestration_integration.py` (Excel/일반 모드 공존 회귀)
  - `tests/test_action_dialog_flows.py` 또는 `tests/test_runner_logic.py` (Run/Stop 연결 경로 회귀)
- 권장
  - `now_spec.md`, `DEV_LOG.md`, `PROJECT_STATUS.md` (행동 변경 문서 동기화)

## 6) 리스크 정의 및 완화

### R1. 실행 경로 회귀 (일반/Excel 분기)
- 위험: Run 버튼/핫키/액션 연결이 분기 중복 또는 누락
- 완화: `_on_run_button_clicked` 단일 진입점 유지, 모든 UI Run 트리거를 이 경로로 연결

### R2. 스레드 안전성
- 위험: Monitor 상태 갱신 시 UI 직접 접근
- 완화: 기존 `pyqtSignal` 경로 유지, 백그라운드 스레드에서 UI 위젯 직접 접근 금지

### R3. 반응형 레이아웃 깨짐
- 위험: 창 축소 시 핵심 컨트롤 잘림/순서 뒤섞임
- 완화: Core 그룹은 `QSizePolicy.Fixed/Preferred` 우선 정책, Advanced만 축약/스크롤

### R4. 사용자 혼동 (UI 이동)
- 위험: 기존 위치 학습 사용자 이탈
- 완화: Stage 1에서는 기능 제거 없음, 라벨 유지 + 그룹화만 수행

## 7) 구현 순서 (PR 단위)

1. PR-1: Core/Advanced 그룹 컨테이너 분리 (기능 동일, 위치만 재배치)
2. PR-2: Excel Mode 강조 배지 + 상태바 강화
3. PR-3: Run/Stop 툴바 노출 정합 + 반응형 세부 튜닝
4. PR-4: 테스트/문서 동기화

## 8) 검증 계획

### Targeted Tests
- `python -m pytest -q tests/test_excel_toolbar_responsive.py`
- `python -m pytest -q tests/test_ui_orchestration_integration.py`
- `python -m pytest -q tests/test_runner_logic.py tests/test_session_manager.py`

### Full Suite (Precision 조건)
- `python -m pytest -q`

### 수동 점검 체크리스트
- 최소 창 크기에서도 `Target`, `Excel Mode`, `P`, `Run/Stop` 가시성 유지
- Excel ON/OFF 시 배지/강조 상태 즉시 변경
- Hotkey Run/Stop이 버튼 실행과 동일 경로 사용
- 일반 모드와 Excel 모드 모두 기존 동작과 역호환

## 9) 롤백 계획
- 작업 브랜치: `feature/ui-modernization-v1`
- 실패 시:
  1) 마지막 안전 커밋으로 리셋
  2) 문제 PR만 되돌리고 다음 PR로 분리 재시도
- Hard Gate(Guardian FAIL) 시 자동 차단 경로 유지

## 10) 완료 기준 (Stage 1)
- 필수 제어(타겟/모드/P/Run/Stop)가 창 크기 축소에서도 항상 즉시 인지 가능
- Excel 모드 활성 상태를 시각적으로 오인할 수 없음
- 기존 실행 로직(일반/Excel) 회귀 0건 + 테스트 게이트 통과

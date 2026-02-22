# 매크로 툴 사용 가이드

## UI 구조 (3분할 레이아웃)

```
┌─────────────┬─────────────────┬─────────────────┐
│   왼쪽      │      중앙       │     오른쪽      │
│ (Scenario)  │ (Preview/Log)   │ (Presets/Sched) │
│             │                 │ (Settings)      │
└─────────────┴─────────────────┴─────────────────┘
```

- 왼쪽: Scenario/Triggers 탭과 스텝 목록 중심 (`Multi-Manager`는 현재 부분구현, 아래 참고)
- 중앙: Preview/Log
- 오른쪽: Presets/Scheduler/Settings 탭

---

## 빠른 시작

### 예제 1: 녹화로 매크로 만들기
1. **Record** 버튼 클릭
2. 실제 동작(클릭/키 입력 등) 수행
3. **Record** 다시 클릭하여 중지
4. **Run**으로 실행 테스트
5. **Save**로 저장

### 예제 2: 이미지 클릭 매크로
1. **Add Image** 클릭 → 화면 영역 선택
2. Threshold/Timeout 등 설정 후 **OK**
3. **Run**으로 실행

### 예제 3: 시나리오 마법사로 빠르게 생성
1. 왼쪽 패널의 **시나리오 마법사** 클릭
2. 템플릿 목록에서 원하는 고급 활용 예시 선택
3. 필요한 값만 입력(추천/전체, 검색 지원)
4. 생성 미리보기/검증 결과 확인 후 **매크로에 추가**

---

## 스텝 추가/관리

### 주요 버튼 (왼쪽 패널)
- **Add Image**: 이미지 클릭 스텝
- **Add Action**: 키/마우스/대기/OCR/분기 등
- **시나리오 마법사**: 고급 활용 예시 템플릿 기반 자동 생성
- **Add Branch**: 이미지 분기
- **Add Comment**: 주석
- **Run / Stop / Record**

### 스텝 편집/관리
- **더블클릭** 또는 **우클릭 → Edit**
- **우클릭 → Duplicate/Delete**
- **드래그 앤 드롭**으로 순서 변경
- **F2** 또는 이름 클릭으로 인라인 이름 변경
- **Ctrl+Z / Ctrl+Y**로 Undo/Redo

---

## 시나리오 마법사

기존 수동 방식(`Add Image`, `Add Action`)은 그대로 두고, 별도 버튼으로 동작합니다.

### 핵심 흐름
1. **목록 필터**: `추천`/`전체` + 검색어
2. **템플릿 선택**: 난이도, 전제조건, 실패 포인트 확인
3. **필요값 입력**: 템플릿별 필수 필드만 입력
4. **생성 미리보기**: 실제 생성될 스텝 순서 확인
5. **검증 결과 확인**:
   - 오류(Error): 적용 불가
   - 경고(Warning): 확인 후 진행
6. **삽입 위치 선택**:
   - 선택 스텝 다음
   - 시나리오 끝

### 현재 제공 템플릿 (46종)
- 채팅/입력: `채팅 문장 반복 전송`, `짧은 메시지 빠르게 전송`, `채팅 문장 천천히 반복`, `문장 입력 후 단축키 실행`, `문장 한 번 입력하고 전송`, `클릭 후 텍스트 입력`, `클릭 후 키 입력`
- 키보드/단축키: `단축키 반복 실행`, `창 전환 반복`, `저장 단축키 주기 실행`, `키 길게 누르기 반복`, `스페이스 길게 누르기 반복`, `문장 입력 후 단축키 반복`, `대기 후 단축키 반복`
- 마우스: `한 위치 계속 클릭`, `한 위치 오른쪽 클릭 반복`, `한 위치 더블클릭 반복`, `두 위치 번갈아 클릭`, `아래로 스크롤 반복`, `위로 스크롤 반복`, `드래그 한 번 실행`
- 파일/서브매크로: `CSV 각 행으로 서브매크로 실행`, `CSV 내용 한 줄씩 입력 후 전송`, `CSV 내용 입력 후 탭 이동`, `서브매크로 반복 재실행`, `서브매크로 무한 반복`, `서브매크로 한 번 실행`, `매크로 두 개 이어서 실행`
- 화면/OCR/분기: `스크린샷 한 장 저장`, `스크린샷 주기 저장`, `OCR 숫자 기준으로 보호키 실행`, `OCR 값만 변수로 저장`, `OCR 확인 후 바로 보호키 분기`, `픽셀 색상 기준으로 보호키 실행`
- 리니지류 게임 실전: `사냥 대상 클릭 후 공격키`, `아이템 줍기 키 반복`, `탭 타겟 반복 전환`, `NPC 대화 넘기기 반복`, `기본 공격 길게 누르기 반복`, `버프 스킬 주기 갱신`, `체력 낮을 때 물약키`, `마나 낮을 때 물약키`, `체력 위험 시 귀환키`, `사냥터 두 지점 순찰 클릭`, `전투 콤보 서브매크로 반복`, `사냥 기록 주기 캡처`
- 템플릿 정의 파일: `app/core/scenario_wizard_templates.json`

### 운영 팁
- 마법사 생성 후에도 기존 편집기에서 자유롭게 수정 가능합니다.
- 경로 기반 템플릿은 파일 존재 여부 경고가 나올 수 있습니다(검증 차단은 아님).
- 무한 반복(반복 횟수 0) 템플릿은 강제 종료 핫키를 반드시 준비하세요.

---

## 실행 옵션

오른쪽 Settings 탭 또는 상단 옵션 바에서 조정:
- **Dry Run**: 입력 동작 없이 시뮬레이션
- **Mini Mode**: 실행 시 창 최소화
- **Capture Fail**: 실패 시 캡처 저장
- **Human Mode**: 사람처럼 이동/클릭
- **Debug Overlay**: 인식 위치 오버레이

### 타겟 창 고정
- 앱 시작 시 Target 값은 기본적으로 **비어 있음**(이전 세션 값 자동 복원 안 함)
- **Target** 입력 후 **Find**: 창 찾기/활성화
- **Fix/Shake**: 창 갱신/리프레시
- **...**: 창 선택기 열기
  - 창 선택기에서 프로세스명을 못 읽은 항목은 `[]` 없이 창 제목만 표시됩니다.
  - 목록이 비면 권한(일반/관리자) 일치 여부 확인 후 `Refresh`를 누르세요.

### 특정 스텝부터 실행
1. 스텝 우클릭
2. **Run from here** 선택
- **Run from here**는 새 실행으로 시작되므로 변수/루프/데이터 상태가 초기화됩니다.

---

## 반복 실행 (Settings 탭)
- **Repeat Count (0=Inf)**: 반복 횟수 (0이면 무한)
- **Cooldown**: 반복 간 대기
- **Max Duration**: 최대 실행 시간
- **Stop on Fail**: 실패 시 즉시 중단

---

## 녹화 설정

### Record Action Delays
- **ON**: 실제 동작 간 딜레이를 스텝에 반영
- **OFF**: 딜레이 없이 기록
 - 드래그는 `drag_path`로 기록되며, Human Mode에서도 **녹화된 경로/타이밍**을 따라 재생됩니다.

### Recording Settings (메뉴/Settings 탭)
녹화 이벤트 합치기/플러시 기준을 조정:
- Typing Gap
- Click Merge Time/Radius
- Scroll Flush Time, Scroll Scale

**Presets**
- **Performance / Normal**은 위 값만 바꿉니다.

---

## 성능 설정

### High Performance Playback
재생 시 내부 sleep/지연을 줄여 더 빠르게 동작합니다.

### High Performance Recording
녹화 버퍼/이동 필터를 조정해 더 고속으로 기록합니다.

### Performance Level 1~3
레벨이 올라갈수록 더 공격적인 성능 설정이 적용됩니다.

**참고**
- Recording Settings 창의 고성능/레벨은 **녹화 성능만** 조정합니다.
- 재생 성능은 Settings 탭에서 조정합니다.

---

## Add Action 타입 설명

아래는 현재 지원되는 **모든 Action Type**입니다.

### 먼저 이것만 기억
- `keyboard`, `mouse`, `screen_check`, `file_action`은 **통합 타입**입니다.
- `text`, `key`, `click_point`, `pixel_check`, `wait`, `compare_images`, `run_macro` 같은 타입은 **직접 타입**입니다.
- 처음엔 통합 타입을 쓰는 것이 실수/관리 측면에서 유리합니다.

### 타입별 기능 요약 (전체)

| Action Type | 기능 | 언제 쓰면 좋은가 |
|---|---|---|
| `keyboard` | 키 입력 통합 타입. 내부 모드(`text/key/key_down/key_up/key_hold`) 선택 가능 | 키 입력 방식을 한 타입에서 바꿔가며 쓰고 싶을 때 |
| `text` | 문자열 타이핑 입력 | 채팅/검색창/폼에 텍스트 입력할 때 |
| `key` | 단일 키(또는 조합키) 눌렀다 떼기 | 단축키 한 번 실행할 때 |
| `key_down` | 키 누르기(Down)만 수행 | 길게 누르기 동작을 분리 제어할 때 |
| `key_up` | 키 떼기(Up)만 수행 | `key_down`과 쌍으로 정밀 제어할 때 |
| `key_hold` | 지정 시간 동안 키 유지 후 해제 | 스킬 차징/롱프레스 입력 |
| `mouse` | 마우스 통합 타입. 내부 모드(`click_point/drag/scroll`) 선택 가능 | 클릭/드래그/스크롤을 하나의 타입으로 관리할 때 |
| `click_point` | 지정 좌표 클릭 | UI 고정 좌표 클릭 |
| `drag` | 시작/끝 좌표 드래그 | 드래그 이동, 슬라이더 조작 |
| `scroll` | 수평/수직 스크롤 반복 | 리스트/인벤토리/페이지 스크롤 |
| `wait` | 지정 시간(ms) 동안 대기 | 입력 간격 제어, UI 반응 대기 |
| `screen_check` | 화면 검사 통합 타입. 내부 모드(`pixel_check/ocr_check_text`) 선택 가능 | 픽셀 검사와 OCR 검사를 상황에 맞게 바꿀 때 |
| `pixel_check` | 특정 좌표의 색상 일치 검사(`tolerance` 포함) | 상태등/버튼색 등 단순 상태 판별 |
| `ocr_check_text` | OCR로 텍스트/숫자 읽고 기대값 비교 | 특정 문구/숫자 표시 여부 확인 |
| `ocr_store` | OCR 결과를 변수에 저장 | 이후 `jump_if` 조건 분기용 변수 만들 때 |
| `ocr_jump_if` | OCR 결과를 즉시 조건 비교 후 점프 | OCR 확인과 분기를 한 스텝에서 끝낼 때 |
| `jump_if` | 저장된 변수(`ocr_store` 등) 기반 조건 분기 | 로직 분기를 명시적으로 구성할 때 |
| `start_loop` | 반복 시작점(횟수 설정) | 구간 반복 시작 |
| `end_loop` | 반복 종료점(`start_loop` 참조) | 반복 구간의 끝 |
| `compare_images` | 두 이미지 파일을 비교(`mse/ssim/hash`)하고 조건 충족 시 점프 | 상태 스냅샷 변화 감지, 전후 화면 비교 |
| `screenshot_roi` | ROI 또는 전체 화면 캡처를 파일로 저장 | 디버깅/증적 스크린샷 수집 |
| `file_action` | 파일 작업 통합 타입(`load_data_file/run_macro`) | 데이터 로드/서브매크로 실행을 한 타입에서 전환할 때 |
| `load_data_file` | CSV 데이터 파일 로드 | 데이터 기반 반복/치환 입력 |
| `run_macro` | 다른 매크로(서브 스크립트) 실행 | 모듈형 매크로 호출 |
| `comment` | 실행 로직 없는 메모 스텝 | 시나리오 설명/구간 라벨링 |

### 레거시 타입
- `loop (legacy)`: 구버전 호환용 no-op 타입(신규 작성 비권장).
- `action (legacy)`: 구버전 alias. 현재는 다이얼로그에서 `keyboard`로 자동 매핑됩니다.

---

## OCR 사용법

### OCR Check (ocr_check_text)
1. **ROI Pick**로 숫자/문자 영역 지정
2. **Preprocess / Language** 조정
3. **Expected Text**:
   - 비우면 “아무 텍스트” 인식
   - 특정 문구를 넣으면 포함 여부 확인

- **Scale**: 작은 글씨는 2~4배 권장 (기본 2.0)
- **Invert Colors**: 어두운 배경 + 밝은 글씨일 때 인식 안정화
- **Whitelist**: 인식 허용 문자 제한(텍스트 OCR에만 적용)
- **Target Height**: 지정 높이로 리사이즈해 작은 글씨 인식 향상(설정 시에만 적용)
 - **Preprocess**: none=그레이스케일만, thresh=Otsu 이진화, blur=가우시안 블러 후 Otsu

- OCR Check는 성공/실패만 판단합니다. 분기가 필요하면 `ocr_jump_if`를 사용하세요.

- OCR Check는 **성공 시** `On Match Goto`로 이동합니다. 조건 분기는 `ocr_jump_if`를 사용하세요.
- 예: Expected Text=HP, On Match Goto=회복 스텝

### OCR Jump If (ocr_jump_if)
1. **ROI Pick**로 숫자/문자 영역 지정
2. **Preprocess / Language** 조정
3. **연산자/값/점프 대상** 설정 → 조건이 맞으면 즉시 해당 스텝으로 이동

- **Scale / Invert**는 OCR Check와 동일한 역할입니다.

### OCR Store (ocr_store)
1. **Variable Name** 입력 (예: `hp`)
2. ROI 지정
3. **Invert / High Contrast** 필요 시 사용
4. **Test Reading**으로 결과 확인

---

## 이미지 비교 (compare_images)
`Add Action`에서 `compare_images`를 선택하거나, 기존 매크로의 `compare_images` 스텝을 불러오면 다음 기준으로 동작합니다.
- **mse**: 값이 낮을수록 유사(0이면 완전 동일)
- **ssim**: 값이 높을수록 유사(1에 가까울수록 동일)
- **hash**: 해시 거리(0이면 완전 동일)

---

## HP 감지 예시 (OCR + Jump If)

1. **Add Action → ocr_store**
   - Variable Name: `hp`
   - HP 숫자 영역 ROI 지정
   - Test Reading으로 값 확인
2. **Add Action → jump_if**
   - 변수: `hp`
   - 연산자: `<` 또는 `<=`
   - 값: `30`
   - TRUE 대상: “포션 사용” 스텝 또는 “정지” 스텝

대안: Branch Step → Variable Logic 탭으로 동일 구성 가능.

---

## 고급 사용자 활용 예시 (실전 조합)

기능을 개별로 아는 것과, 실제 자동화 설계를 하는 것은 다릅니다.  
아래는 실사용에서 많이 쓰는 **고급 조합 패턴**입니다.

### 1) 다중 계정 일일 루틴 자동 순환 (Multi-Manager)
목표: 여러 클라이언트를 순서대로 돌며 동일 루틴 수행.

핵심 조합:
- `Multi-Manager`(세션 편집/회전 + Start All 시 runner 자동 연결)
- `run_macro`(루틴 모듈 분리)
- `Scheduler`(시간 예약)
- `ocr_store` + `jump_if`(조건 분기)

예시 흐름:
1. 세션 A/B/C 각각에 타겟 창과 시작 매크로 지정
2. 공통 메인 매크로에서 `run_macro`로 `준비`, `전투`, `정리` 모듈 호출
3. 중간에 `ocr_store(hp)` 후 `jump_if hp <= 30`이면 회복 분기
4. Scheduler로 정해진 시간마다 자동 시작

### 2) CSV 기반 대량 반복 입력 자동화
목표: 회원/상품/코드 목록을 파일에서 읽어 반복 입력.

핵심 조합:
- `load_data_file` 또는 `file_action(load_data_file)`
- `start_loop` / `end_loop`
- `keyboard`(text 모드)
- 동적 치환: `{컬럼명}`, `{seq}`, `{counter:name}`

예시 흐름:
1. `load_data_file`로 CSV 로드
2. `start_loop` 이후 입력 스텝에서 `{id}`, `{name}`, `{phone}` 등 사용
3. `end_loop`에서 다음 행으로 자동 진행
4. 행 소진 시 루프 자동 종료

### 3) OCR 기반 상태판단 + 행동 분기
목표: 수치/문구 상태에 따라 다른 행동 실행.

핵심 조합:
- `ocr_store`(값 저장)
- `jump_if`(저장값 분기)
- `ocr_jump_if`(읽기+분기 일체형)

예시 흐름:
1. `ocr_store`로 현재 자원/체력 읽기
2. `jump_if`로 임계값 비교 후 `회복`, `구매`, `귀환` 등 분기
3. 긴급 분기는 `ocr_jump_if`로 한 스텝 처리

### 4) 트리거 인터럽트(긴급 대응 매크로)
목표: 메인 작업 중 특정 이벤트 발생 시 즉시 대응 후 복귀.

핵심 조합:
- `Triggers`(조건 감시)
- 트리거 액션 `run_macro`
- 메인 매크로 일시중지/재개

예시 흐름:
1. 메인 루틴 실행 중 트리거가 특정 이미지 감지
2. 트리거 전용 대응 매크로(`run_macro`) 즉시 실행
3. 대응 종료 후 원래 메인 흐름으로 복귀

### 5) 팝업/오류 자동 복구 루프
목표: 예외 팝업, 확인창, 끊김 화면을 자동 처리.

핵심 조합:
- `screen_check(pixel_check)` 또는 `ocr_check_text`
- `click_point`(확인 버튼)
- `jump_if` 또는 `On Match Goto`
- `loop_until_hide`(이미지 사라질 때까지 반복)

예시 흐름:
1. 팝업 색상/문구 감지 스텝 배치
2. 감지 시 닫기 버튼 클릭
3. 사라질 때까지 재확인
4. 정상 루틴으로 복귀

### 6) 증적 수집형 자동화 (디버깅/감사)
목표: 실패 원인 추적, 운영 증적 확보.

핵심 조합:
- `screenshot_roi`
- `Capture Fail`
- 동적 파일명: `{seq}`, `{counter:name}`

예시 흐름:
1. 주요 분기 직전/직후 `screenshot_roi` 저장
2. 실패 시 자동 캡처(`Capture Fail`)로 마지막 상태 확보
3. 파일명을 시퀀스로 누적해 타임라인 분석

### 7) 사람 같은 입력 패턴으로 안정화
목표: 기계적인 입력 패턴을 줄이고 실제 환경 안정성 확보.

핵심 조합:
- `Human Mode`
- `keyboard`의 동적 문자열(`#`, `@`, `?`, `{seq}`)
- 녹화 기반 `drag_path` 재생

예시 흐름:
1. 클릭/드래그는 Human Mode로 실행
2. 반복 텍스트는 동적 토큰으로 단조 패턴 완화
3. 정밀 동작은 녹화 후 경로 그대로 재생

### 8) 모듈형 매크로 아키텍처
목표: 큰 매크로를 유지보수 가능한 작은 단위로 운영.

핵심 조합:
- `run_macro`(서브 스크립트)
- 공통 모듈 분리(로그인/이동/정리)
- 재귀 가드(깊이 제한) 고려한 설계

예시 흐름:
1. `00_bootstrap`, `10_farm`, `20_cleanup` 식으로 파일 분리
2. 메인에서 필요한 순서로 호출
3. 공통 로직 변경 시 해당 모듈만 수정

### 설계 팁 (고급)
1. 먼저 `Dry Run`으로 흐름 검증 후 실입력을 켜세요.
2. 조건 분기는 `ocr_store + jump_if`를 기본 패턴으로 두면 디버깅이 쉽습니다.
3. 좌표 기반 스텝만 쓰지 말고 이미지/OCR 검사를 중간중간 섞어 복원력을 높이세요.
4. 실사용 전에는 `run_smoke_suite.py --quick` + 수동 체크리스트를 항상 1회 수행하세요.

---

## Multi-Manager 현재 상태
- 탭 위치: 왼쪽 `Multi-Manager`
- 현재 가능한 것:
  - 세션 추가/삭제/복제
  - 세션별 Target/Script/Reset 설정 저장
  - 라운드로빈 전환 코어(`SessionManager`)
  - `Start All` 시 세션 스크립트에서 runner 자동 생성/연결
- 현재 제한:
  - 스크립트 경로가 비어 있거나 파일 로드 실패 시 해당 세션은 `pending` 상태
- 권장 운영:
  - 실사용 자동화는 `Scheduler + run_macro + Triggers` 중심으로 구성
  - `Multi-Manager`는 실험/개발 용도로 사용

---

## Presets / Scheduler / Triggers

### Presets (오른쪽 탭)
- `.macro` 목록에서 선택/더블클릭으로 로드
- **Refresh**로 목록 갱신

### Scheduler (오른쪽 탭)
1. **Add**로 매크로 추가
2. **Run Time** 설정
3. **Enable Scheduler** 체크

### Triggers (왼쪽 탭)
- 조건 이미지 감시 후 자동 동작
- 동작: 알림/중지/매크로 실행
- 트리거로 메인 매크로를 잠시 중단했다가 재개하는 경우, 변수/루프/데이터 상태는 유지됩니다.

---

## 저장/불러오기
- **Save / Load**는 상단 툴바 사용
- 확장자: `.macro`

### 경로 해석
- `run_macro` / `load_data_file` / `compare_images` / `screenshot_roi`는 **상대 경로**를 지원하며, 현재 매크로 파일 위치 기준으로 해석됩니다.

---

## 팁 / 문제 해결

- OCR이 잘 안 맞으면 ROI를 더 좁히고 전처리를 조정하세요.
- 이미지 인식이 불안정하면 Threshold/Match Quality를 조정하세요.
- Debug Overlay를 켜고 로그를 확인하면 원인 파악이 빠릅니다.

## 스모크 테스트(권장)

배포/실사용 전에는 아래 순서로 최소 점검을 권장합니다.
1. `python run_smoke_suite.py --quick`
2. `python run_smoke_suite.py`
3. `SMOKE_TEST_CHECKLIST.md` 기준으로 수동 시나리오 점검

자동 테스트 통과 후에도 해상도/DPI/권한 차이로 실환경 이슈가 날 수 있으니, 수동 시나리오를 반드시 1회 수행하세요.

### 캡처 실패(capture_on_fail)
- 실패 시 ROI를 지정하지 않으면 전체 화면을 캡처합니다.

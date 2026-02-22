# 매크로 툴 사용 가이드

## UI 구조 (3분할 레이아웃)

```
┌─────────────┬─────────────────┬─────────────────┐
│   왼쪽      │      중앙       │     오른쪽      │
│ (Scenario)  │ (Preview/Log)   │ (Presets/Sched) │
│             │                 │ (Settings)      │
└─────────────┴─────────────────┴─────────────────┘
```

- 왼쪽: Scenario/Triggers/Multi-Manager 탭, 스텝 목록과 버튼
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

---

## 스텝 추가/관리

### 주요 버튼 (왼쪽 패널)
- **Add Image**: 이미지 클릭 스텝
- **Add Action**: 키/마우스/대기/OCR/분기 등
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

## 실행 옵션

오른쪽 Settings 탭 또는 상단 옵션 바에서 조정:
- **Dry Run**: 입력 동작 없이 시뮬레이션
- **Mini Mode**: 실행 시 창 최소화
- **Capture Fail**: 실패 시 캡처 저장
- **Human Mode**: 사람처럼 이동/클릭
- **Debug Overlay**: 인식 위치 오버레이

### 타겟 창 고정
- **Target** 입력 후 **Find**: 창 찾기/활성화
- **Fix/Shake**: 창 갱신/리프레시
- **...**: 창 선택기 열기

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

주요 타입과 용도:
- **keyboard**: 키 입력 통합 (text/key/key_down/key_up/key_hold)
- **mouse**: 마우스 동작 통합 (click_point/drag/scroll)
- **screen_check**: 화면 검사 통합 (pixel_check/ocr_check_text)
- **start_loop / end_loop**: 반복 제어
- **screenshot_roi**: ROI 캡처 저장
- **ocr_check_text**: OCR로 텍스트/숫자 확인
- **ocr_jump_if**: OCR 결과로 바로 분기
- **ocr_store**: OCR 결과를 변수로 저장
- **file_action**: 파일/서브스크립트 통합 (load_data_file/run_macro)
- **jump_if**: 변수 조건 분기
- **run_macro**: 다른 매크로 호출
- **comment**: 주석
 - **loop (legacy)**: 구버전 호환용(신규 UI에서는 숨김, 기존 파일 로드시만 유지)

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
매크로 파일에 있는 `compare_images` 스텝은 다음 기준으로 동작합니다.
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

### 캡처 실패(capture_on_fail)
- 실패 시 ROI를 지정하지 않으면 전체 화면을 캡처합니다.

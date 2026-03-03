# Knowledge Base (Project Glossary)

## 운영 용어
- `Session Gate`: 작업 시작 전 상태 확인 + 모드 선언 절차.
- `Post-Task Gate`: 테스트/리스크/커밋 조건 검증 절차.
- `Constitutional Files`: 규칙 정합성이 강제되는 핵심 파일 집합.
- `Precision Mode`: 다중 파일/고위험 변경에서 계획/검증을 확장하는 모드.

## 아키텍처 용어
- `Command Pattern`: 상태 변경을 커맨드로 캡슐화해 Undo/Redo 안전성 보장.
- `StepData`: 실행 스텝 데이터 모델. 변경 시 직렬화/러너/테스트 동시 업데이트 필요.
- `Template Processor`: `{{placeholder}}` 치환 우선 처리 계층.
- `Global Input Lock`: 멀티 워커 환경에서 물리 입력 직렬화 락. `app/core/input_lock.py`의 `GlobalInputManager`.

## 멀티 에이전트 용어
- `Planner`: 설계/리스크/검증 계획 담당, 코드 수정 금지.
- `Executor`: 최소 diff 구현 + 필수 테스트 수행.
- `Guardian`: 읽기 전용 리뷰, PASS/FAIL 하드 게이트.

## 런타임 흐름 (MacroRunner)
- 스텝 실행 경로: `MacroRunner._run_step()` → `ActionType` 분기 → 각 `_action_*()` 메서드
- 텍스트 출력 경로: `TemplateProcessor.render()` → `pyautogui.write()` (ASCII만) / clipboard paste (비ASCII)
- Placeholder 치환: `{{var}}` 또는 `{var}` → `TemplateProcessor` → 미해결 시 fail-fast (raw 타이핑 절대 금지)
- 서브스크립트: `run_macro` 액션, 콜 스택 깊이 5, 변수 컨텍스트 공유
- 캡처 경로: `mss` 화면 캡처 → `ImageProcessor` (OCR/이미지 비교) → 결과 반환 → 스텝 분기

## GlobalInputLock 사용 패턴
- Worker에서 직접 마우스/키 입력 전에 반드시 `GlobalInputManager.acquire()` 호출
- timeout 발생 시 step failure로 전파됨 (무한 대기 금지)
- lock/acquire/release/timeout 이벤트는 JSONL 로그에 자동 기록
- 멀티 세션(`Multi-Manager`) 환경에서 세션 간 입력 충돌 방지용

## 자주 발생하는 패턴 실수 ⚠️
- **steps 직접 변경 금지**: `self.steps.append()` 등 직접 변경 → 반드시 `self._push_command(...)` 사용
- **Worker에서 UI 직접 접근 금지**: `QThread` 내부에서 `QLabel.setText()` 등 직접 호출 → `pyqtSignal` emit으로만
- **StepData 변경 시 3종 동시 업데이트**: `StepData` 모델 + `to_dict/from_dict` 직렬화 + `_run_step()` 러너 + 관련 테스트
- **TemplateProcessor 미경유 텍스트 출력**: `pyautogui.write(raw_text)` 직접 호출 → `{{placeholder}}`가 그대로 타이핑됨
- **다이얼로그에서 상태 직접 변경**: 다이얼로그는 데이터 반환만 담당, `MainWindow`에서 상태 적용

## TemplateProcessor 치환 우선순위
1. `{{session_var}}` — 세션 변수 (SessionManager 제공)
2. `{{excel_col}}` — Excel 행 데이터 컬럼 (ExcelDataLoader 제공)
3. `{{env_var}}` — 환경 변수 fallback
4. 미해결 placeholder → fail-fast (빈 문자열 치환 금지)

## 권장 운영 규칙
- "규칙 변경"은 기능 변경과 분리해 단독 변경 세트로 관리.
- "복구 가능한 변경"만 허용(스냅샷 커밋/롤백 경로 확보).
- 스냅샷(`docs_for_ai/CONTEXT_*.md`) 파일이 24시간 이상 오래됐으면 재생성: `python tools/generate_context_snapshot.py --scope core`

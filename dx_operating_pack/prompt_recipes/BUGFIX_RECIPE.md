# Bugfix Recipe

```text
Inputs:
- repro steps (1 line)
- expected vs actual

Process:
1) locate write path first
2) add regression test
3) patch minimal code
4) run targeted tests (+ full if risk)

Output:
- root cause
- fix location
- tests added/updated
- pytest summary
```

## 이 프로젝트 특화 체크항목

### Runner 버그
- `dx_operating_pack/docs_for_ai/CONTEXT_CORE.md`의 runner.py 인터페이스 먼저 확인
- `_action_*()` 메서드 중 어느 분기에서 실패하는지 `ActionType`으로 좁히기
- 스텝 데이터 필드가 올바르게 직렬화/역직렬화되는지 `StepData.from_dict()` 확인

### UI 버그
- `CONTEXT_UI.md` + hide-all then show-needed 패턴 우선 확인
- `QGridLayout.addWidget()` 경로가 정상인지 확인 (누락 시 위젯 미표시)
- Worker → UI 접근이 signal 없이 직접 접근하는 경우 → `pyqtSignal` 연결로 수정

### 직렬화 버그
- `StepData.to_dict()` / `from_dict()` 동시 확인 필수
- 구버전 `.macro` 파일과의 하위 호환성 확인 (새 필드는 `get()` + 기본값)

### 바인딩/Placeholder 버그
- `TemplateProcessor` 단위 테스트 먼저 추가 (`tests/test_template_processor.py`)
- `pyautogui.write()`에 raw `{{var}}`가 도달하는 경로가 없는지 추적

### 멀티-Manager 버그
- `SessionManager` 상태 전이 (`pending → running → error`) 추적
- `backoff` 재시도 임계치 초과 여부 확인 (`max_attempts`, `max_wait`)

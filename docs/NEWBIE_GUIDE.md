# NEWBIE GUIDE (신입 가이드)

이 문서는 이 프로젝트를 처음 여는 사람을 위한 "첫 10분 가이드"입니다.
전문 문서(`now_spec.md`, `PROJECT_STATUS.md`, `DEV_LOG.md`)는 그대로 두고,
여기서는 바로 작업을 시작하는 데 필요한 최소 정보만 제공합니다.

## 1) 이 프로젝트가 하는 일
- 윈도우 매크로/RPA 편집기와 실행 엔진입니다.
- UI(PyQt5) + 실행 엔진 + 테스트/게이트 + DX 운영 도구가 함께 있습니다.

## 2) 시작 순서 (처음 1회)
1. 저장소 루트에서 실행:
   - `python run.py`
2. 문서 우선순위:
   - 현재 상태: `PROJECT_STATUS.md`
   - 최신 동작 스펙: `now_spec.md`
   - 변경 이력: `DEV_LOG.md`
   - 자산 지도: `ASSET_MAP.md`

## 3) 작업 기본 루프 (항상 이 순서)
1. 시작 점검:
   - `python tools/task_start_guard.py`
2. 코드/문서 수정
3. 종료 게이트:
   - `python tools/task_finish.py --subject "<작업 요약>" --scope <feature|rule|cleanup|docs|test>`
4. 자산 점검(권장):
   - `python tools/project_audit.py`
5. 커밋:
   - `git commit -F .git/TASK_COMMIT_TEMPLATE.md`

## 4) 반드시 지킬 것
- `MainWindow.steps` 직접 수정 금지 (커맨드 패턴 사용).
- Worker 스레드에서 UI 직접 접근 금지 (`pyqtSignal` 경유).
- `backups/` 경로 수정 금지.
- 플레이스홀더 미치환 텍스트(`{{var}}`)를 실제 입력으로 타이핑 금지.
- 의미 있는 동작 변경 시 문서 3종 동기화:
  - `PROJECT_STATUS.md`, `now_spec.md`, `DEV_LOG.md`

## 5) 지금 어디를 보면 되는가
- 기능/엔진: `app/core/runner.py`
- 예외 체계: `app/core/exceptions.py`
- 메인 UI: `app/main.py`
- 스타일: `app/ui/styles.py`
- DX 도구: `tools/`
- 멀티 역할 AI 코어:
  - `app/core/multi_role_ai.py`
  - `tools/run_multi_role_ai.py`
  - `MULTI_AGENT_PROTOCOL.md`
- 테스트: `tests/`

## 6) 자주 막히는 지점
- 커밋이 막힘:
  - `.git/post_task_gate.json` stale 또는 누락 가능성 큼
  - 해결: `python tools/task_finish.py --subject "..." --scope ...` 재실행
- 테스트 자동 선택 0건:
  - 게이트 실패가 정상 동작일 수 있음
  - 해결: 관련 테스트를 명시해서 실행
- 문서 시간 차이 경고:
  - 문서 3종 중 일부만 수정했을 가능성

## 7) 신입용 한 줄 규칙
- "작업 전 `task_start_guard`, 작업 후 `task_finish`, 커밋 전 `project_audit`."

## 8) 정기 점검 대상 (운영 중 계속 개선)
- Global Input Lock (입력 경합/timeout 튜닝)
- Pending 세션 자동 복구 (backoff/승격 정책 점검)
- 데이터 바인딩 Fail-Fast (미치환 텍스트 차단 회귀 방지)
- 구조화 로그/이력 분석 (병목 추적 정확도 개선)
- `.macro` 로딩 보안 (경로 우회/포맷 확장 방어)

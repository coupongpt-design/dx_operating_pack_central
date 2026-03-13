# 프로젝트 소개

이 프로젝트는 Windows 데스크톱에서 동작하는 PyQt5 기반 매크로 편집/실행 도구다.
핵심 목적은 게임/앱 자동화를 위해 매크로를 만들고, 이미지 매칭/OCR/정확 재현형 녹화/스케줄/트리거/다중 세션 실행까지 한곳에서 다루는 것이다.

에이전트가 이 문서를 읽고 먼저 판단해야 할 핵심은 아래다.

## 1) 이 프로젝트는 어떤 종류의 프로젝트인가

- 제품 성격:
  - GUI 매크로 자동화 앱
  - 이미지 인식 + OCR + 입력 자동화 + 시나리오 편집기
- 운영 성격:
  - DX Pack, git governance, QA 플레이북까지 같이 관리하는 운영형 저장소
- 플랫폼 성격:
  - Windows 중심
  - PyQt5 데스크톱 UI
  - 화면 캡처/입력/윈도우 제어에 OS 의존성이 있다

즉, 이 저장소는 단순 UI 앱이 아니라 아래 2개가 같이 들어 있다.

1. 실제 제품 앱
2. 재사용 가능한 DX/QA 운영 시스템

## 2) 현재 구현된 핵심 시스템

- 매크로 편집/저장
  - StepData 기반 스텝 편집
  - JSON / `.macro` 저장·로드
  - Undo/Redo
- 실행 엔진
  - `MacroRunner`
  - 이미지 클릭/대기/드래그/분기
  - 키보드/마우스/텍스트 실행
  - `run_macro` 서브스크립트
- 인식 계층
  - OpenCV 이미지 매칭
  - OCR(Tesseract)
  - relative target image search
- 녹화/재현
  - `InputRecorder` 기반 정확 재현형 녹화
  - 클릭/드래그/스크롤/키 입력 기록
  - scroll 위치 보존 재생
- 런타임 제어
  - 글로벌 핫키
  - Scheduler
  - TriggerWatcher
  - Multi-Manager / SessionManager
- 작성 보조
  - Scenario Wizard
  - Conditional Wizard
  - Smart Capture
  - 좌표/오버레이/HUD
- 관측/QA
  - JSONL 실행 로그
  - 실행 이력 뷰어
  - `run_health_check.py`
  - `run_smoke_suite.py`
  - pytest 회귀 세트
- DX 운영
  - `task_finish`, `post_task_gate`, git hooks
  - DX Pack sync / feedback / central promotion
  - Multi-role AI + Gemini CLI semi-auto 보조

## 3) 작업할 때 중요하게 봐야 할 성질

- UI 프로젝트이지만, 실제 버그는 UI보다 런타임 상태 전이에서 자주 난다.
  - 포커스
  - 모달 복귀
  - 저장/로드
  - 해상도/좌표
  - 단축키 충돌
- `Record`는 현재 smart 변환형이 아니라 정확 재현형이다.
- `StepData`, serialization, runner 흐름은 서로 강하게 묶여 있다.
- DX Pack 관련 변경은 다른 프로젝트에도 퍼질 수 있는 재사용 자산으로 봐야 한다.

## 4) 에이전트가 특히 조심할 것

- `MainWindow.steps` 직접 변이 금지
- worker thread의 UI 직접 접근 금지
- `StepData` 변경 시
  - 모델
  - 저장/로드
  - runner
  - 테스트
  를 같이 봐야 함
- 텍스트 출력은 placeholder 치환 경로를 반드시 거쳐야 함
- 실사용 이슈는 테스트 PASS만으로 닫지 말고 사용자 여정 기준으로 봐야 함

## 5) 이 프로젝트를 이해하려면 다음 문서를 순서대로 보면 된다

1. `PROJECT_STATUS.md`
2. `AGENTS.md`
3. `docs_for_ai/CONTEXT_SNAPSHOT.md`

그리고 작업 종류에 따라 추가로 연다.

- UI 작업:
  - `dx_operating_pack/docs_for_ai/CONTEXT_UI.md`
- runner / StepData / 저장로드:
  - `dx_operating_pack/docs_for_ai/CONTEXT_CORE.md`
- 실사용 QA / 버그 재현:
  - `docs/dev/REAL_WORLD_QA.md`
  - `docs/dev/USER_JOURNEYS.md`
- DX Pack 설치 / sync / feedback:
  - `dx_operating_pack/AGENT_ONBOARDING.md`
  - `dx_operating_pack/docs/CROSS_PROJECT_QA_PLAYBOOK.md`
  - `dx_operating_pack/docs/CENTRAL_PACK_OPERATING_MODEL.md`

## 6) 빠른 판단 포인트

이 프로젝트에서 요청이 들어오면 먼저 아래 중 어디인지 나누면 된다.

- 제품 기능 변경
- UI/사용성 문제
- 런타임/실사용 버그
- runner/serialization/StepData 변경
- DX Pack / 거버넌스 / 중앙 PACK 운영
- QA 체계 / 문서화 / 인덱스 정리

이 분류만 맞아도 읽을 문서와 검증 경로를 빠르게 좁힐 수 있다.

## 7) 한 줄 요약

이 프로젝트는 "PyQt5 매크로 자동화 앱"이면서 동시에 "DX Pack과 QA 운영 체계를 실험·재배포하는 기준 저장소"다.

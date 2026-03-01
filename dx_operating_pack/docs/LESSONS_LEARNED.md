# Lessons Learned (AI Collaboration)

## 1) 테스트가 통과해도 실제 동작이 틀릴 수 있다
- 증상: 치환 로직이 모킹에 가려져 실사용 실패.
- 교정: 핵심 비즈니스 로직 몽키패치 금지, 최종 실행부만 모킹.

## 2) 규칙은 문장만으로는 누락된다
- 증상: 커밋/게이트 절차가 대화 중 누락.
- 교정: `task_start_guard`, `task_finish`, git hooks, CI guard로 강제.

## 3) 대형 변경은 역할 분리가 필요하다
- 증상: 설계/구현/검증이 한 흐름에 섞여 회귀 탐지 지연.
- 교정: Precision 시 `Planner -> Executor -> Guardian` 3단계 강제.

## 4) 문서/코드 동기화 불일치는 누적 부채가 된다
- 증상: 규칙 파일 불일치와 오래된 운영 가이드.
- 교정: sync guard 테스트와 템플릿 기반 문서 운영.

## 5) 입력 자동화는 동시성 보호가 핵심이다
- 증상: 멀티 워커에서 키보드/클립보드 간섭.
- 교정: Global Input Lock + timeout + 구조화 로그 추적.

## 6) 컨텍스트 스냅샷이 낡으면 AI가 오판한다
- 증상: `docs_for_ai/CONTEXT_CORE.md`가 2일 이상 오래되어 삭제된 메서드를 참조.
- 교정: 24시간 이상 오래된 스냅샷은 `python tools/generate_context_snapshot.py --scope core` 재생성.

## 7) 컴팩트 UI에서 레이아웃 충돌이 자주 발생한다
- 증상: Options Toolbar에서 3줄 Grid 중 일부 위젯이 배치되지 않아 보이지 않음.
- 교정: `QGridLayout.addWidget(widget, row, col, rowspan, colspan)` 경로 **반드시** 확인.

## 8) closeEvent 미구현 시 백그라운드 프로세스가 남는다
- 증상: 프로그램 종료 후 Python 프로세스가 좀비로 남아 다음 실행 시 충돌.
- 교정: `closeEvent` 재정의로 runner/recorder/watcher/scheduler 안전 종료 보장.

---
> **Draft 승격 규칙**: 세션 종료 시 `LESSONS_LEARNED_DRAFT.md`를 확인하여  
> 3회 이상 언급된 패턴이 있으면 위 번호 목록에 승격 반영 후 Draft에서 제거.



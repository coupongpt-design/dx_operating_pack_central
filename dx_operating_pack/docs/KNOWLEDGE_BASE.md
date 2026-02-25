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
- `Global Input Lock`: 멀티 워커 환경에서 물리 입력 직렬화 락.

## 멀티 에이전트 용어
- `Planner`: 설계/리스크/검증 계획 담당, 코드 수정 금지.
- `Executor`: 최소 diff 구현 + 필수 테스트 수행.
- `Guardian`: 읽기 전용 리뷰, PASS/FAIL 하드 게이트.

## 권장 운영 규칙
- "규칙 변경"은 기능 변경과 분리해 단독 변경 세트로 관리.
- "복구 가능한 변경"만 허용(스냅샷 커밋/롤백 경로 확보).


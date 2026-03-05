# Monorepo Stage 1 Map

## 목적
- 한 레포에서 `dk_system`, `macro`, `google_messages`를 분리 운영하기 위한 기준점 확보
- 기존 동작 안정성을 위해 Stage 1에서는 파일 이동 금지

## 현재 상태
- 분류 폴더 생성 완료:
  - `dk_system/`
  - `macro/`
  - `google_messages/`
- 각 폴더 `README.md`에 담당 범위와 Stage 2 원칙 정리
- Stage2 진행 현황:
  - `google_messages` 구현 파일 이관 완료(패키지화 + 루트 호환 래퍼 유지)
  - `macro`, `dk_system`은 아직 Stage1 상태

## 운영 원칙
1. Stage 1: 폴더/문서만 추가 (완료)
2. Stage 2: 파일을 분류 폴더로 점진 이동
3. 이동 시 매 단계마다 훅/게이트/테스트 통과 확인
4. 기존 규칙 문서 충돌 시 `AGENTS.md`를 정본으로 적용

## Stage 2 권장 순서
1. `google_messages` 모듈군 먼저 이동 (경계가 명확함)
2. `macro` 코어 파일 이동 + import 경로 정리
3. `dk_system` 운영 자산 이동(훅/가드/도구)

## 완료 기준
- 경로 이동 후에도 아래 검증이 통과해야 완료로 간주
  - `python tools/check_tool_integrity.py --project-root . --strict`
  - `python tools/task_start_guard.py`

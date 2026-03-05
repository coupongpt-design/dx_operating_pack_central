# Monorepo Stage 1 Map

## 목적
- 한 레포에서 `dk_system`, `macro`, `google_messages`를 분리 운영
- 기존 동작을 깨지 않도록 루트 호환 경로를 유지하면서 실제 구현을 하위 폴더로 이동

## 현재 상태
- 분류 폴더:
  - `dk_system/`
  - `macro/`
  - `google_messages/`
- Stage2 진행 현황:
  - `google_messages` 구현 파일 이관 완료(패키지화 + 루트 호환 래퍼 유지)
  - `macro` 구현 파일 이관 완료(패키지화 + 루트 호환 래퍼 유지)
  - `dk_system` 부분 이관 완료:
    - `.githooks/**` 실파일 -> `dk_system/.githooks/**`
    - `tools/*.py` 실파일 -> `dk_system/tools/*.py`
    - 루트 `.githooks/**`, `tools/*.py`는 호환 래퍼로 유지

## 운영 원칙
1. Stage 1: 폴더/문서만 추가 (완료)
2. Stage 2: 파일을 분류 폴더로 점진 이동
3. 이동 시 매 단계마다 훅/게이트/테스트 통과 확인
4. 기존 규칙 문서 충돌 시 `AGENTS.md`를 정본으로 적용

## Stage 2 권장 순서
1. `google_messages` 모듈군 이동
2. `macro` 코어 파일 이동
3. `dk_system` 운영 자산 이동(훅/가드/도구) + 루트 브리지 유지

## 완료 기준
- 경로 이동 후에도 아래 검증이 통과해야 완료로 간주
  - `python tools/check_tool_integrity.py --project-root . --strict`
  - `python tools/task_start_guard.py`

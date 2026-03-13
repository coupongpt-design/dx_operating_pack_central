# 문서 인덱스 (활성 기준)

이 문서는 "지금 읽어야 하는 문서"와 "보관/산출물 문서"를 구분하기 위한 활성 인덱스다.
문서 경로를 옮기지 않고, 세션 진입과 운영 판단에 필요한 기준만 빠르게 찾도록 정리한다.

## 1) 항상 읽는 문서
- `PROJECT_STATUS.md`
  - 현재 상태, 최근 변경, 검증 결과, 다음 포커스
- `AGENTS.md`
  - 세션 시작 규칙, 작업 모드, 테스트/게이트/커밋 규칙
- `docs_for_ai/CONTEXT_SNAPSHOT.md`
  - 코드베이스 전반 스냅샷, 핵심 인터페이스, 세션 부트스트랩 기준

## 2) 작업별 조건 문서
- UI/layout/overlay 작업
  - `dx_operating_pack/docs_for_ai/CONTEXT_UI.md`
- runner/StepData/serialization/테스트 작업
  - `dx_operating_pack/docs_for_ai/CONTEXT_CORE.md`
- 실사용 버그/QA/사용성 검토
  - `docs/dev/REAL_WORLD_QA.md`
  - `docs/dev/USER_JOURNEYS.md`
  - 필요 시 `docs/dev/BUG_LOOP_PROTOCOL.md`
- 문서/규칙/운영 체계 검토
  - `docs/ASSET_MAP.md`
  - `docs/DOC_INDEX.md`
- DX Pack governance/install/sync
  - `dx_operating_pack/AGENT_ONBOARDING.md`

## 3) 상태/사양/이력 문서
- `PROJECT_BRIEF.md`
  - 에이전트가 프로젝트 성격, 핵심 시스템, 주의점, 다음 읽을 문서를 빠르게 판단하기 위한 루트 소개 문서
- `now_spec.md`
  - 현재 동작 계약과 사양
- `DEV_LOG.md`
  - 세션별 변경 이력과 검증 메모
- `PROJECT_STATUS.md`
  - 현재 기준 상태와 최신 확인 결과
- `docs/SYSTEM_INVENTORY.md`
  - 현재 프로젝트에 구현된 시스템 전체를 문서 기준 + 코드 대조 기준으로 한 번에 정리한 인벤토리

## 4) 사용자 문서
- `README.md`
  - 프로젝트 개요와 시작점
- `docs/USER_GUIDE.md`
  - 일반 사용자용 사용 가이드
- `docs/NEWBIE_GUIDE.md`
  - 초보자 진입 가이드
- `요청에 따른 동작 정리.txt`
  - 사용자 요청 문구와 세션 동작 트리거 메모

## 5) 운영/QA 문서
- `dx_operating_pack/docs/CROSS_PROJECT_QA_PLAYBOOK.md`
  - DX Pack 설치/최신화만으로 같이 배포되는 공용 실사용 QA 운영 플레이북. 새 프로젝트 이식이나 QA 체계 재정비 때 읽는다.
- `docs/dev/REAL_WORLD_QA.md`
  - 이 프로젝트용 실사용 QA 기준. 실사용 버그, 릴리즈 전 스모크, 사용성/런타임 이슈 검토 때 읽는다.
- `docs/dev/USER_JOURNEYS.md`
  - 고정 점검할 대표 사용자 흐름 목록. 수동 스모크 또는 실사용 회귀 점검 때 읽는다.
- `docs/dev/BUG_LOOP_PROTOCOL.md`
  - 버그를 `재현 -> 회귀 테스트 -> 문서 반영`으로 닫는 절차. 버그 처리 시에만 읽는다.
- `docs/dev/SMOKE_TEST_CHECKLIST.md`
- `docs/dev/BUTTON_CHECK.md`
- `docs/dev/MULTI_AGENT_PROTOCOL.md`
- `docs/dev/CONSULT_TOKEN_TEMPLATE.md`
- `docs/dev/UI_RELEAYOUT_PLAN.md`

## 6) DX Pack 원본 문서
- `dx_operating_pack/README.md`
- `dx_operating_pack/AGENT_ONBOARDING.md`
- `dx_operating_pack/INSTALL_IN_NEW_PROJECT.md`
- `dx_operating_pack/MANIFEST.md`
- `dx_operating_pack/PACK_COVERAGE.md`
- `dx_operating_pack/docs/CROSS_PROJECT_QA_PLAYBOOK.md`
- `docs/dev/CROSS_PROJECT_QA_PLAYBOOK.md`
  - 기존 프로젝트 내부 참조용 브리지. canonical은 DX Pack 쪽 문서를 따른다.
- `dx_operating_pack/docs/CENTRAL_PACK_OPERATING_MODEL.md`
  - 여러 프로젝트의 로컬 PACK 수확물을 중앙 PACK으로 승격/재배포하는 운영 모델
- `dx_operating_pack/docs/**`
- `dx_operating_pack/docs_for_ai/**`
- `dx_operating_pack/prompt_recipes/**`

일반 제품 기능 작업에서는 기본으로 읽지 않고, PACK 설치/동기화/피드백 상신/중앙 승격 작업일 때만 연다.

이 영역은 프로젝트 앱 문서가 아니라 DX Pack 자체의 운영/배포/재사용 문서다.

## 7) Generated / Archived / Backup 문서
아래 경로는 기본 읽기 세트에 포함하지 않는다.

- 자동 생성 산출물
  - `docs/reports/project_audit_latest.md`
  - `dx_operating_pack/docs/LESSONS_LEARNED_DRAFT.md`
  - `dx_operating_pack/feedback/LATEST_INSIGHT.yaml`
- 보관/백업
  - `archive/**`
  - `backups/**`
  - `.dx_cache/**`
- Git 내부/작업 임시 산출물
  - `.git/*.md`
  - `.git/*.txt`
- 빌드/배포 산출물 내부 문서
  - `build/**`
  - `dist/**`

이 문서들은 참조나 복구, 산출물 확인 용도이지 canonical 문서가 아니다.

## 8) 정리 메모
- 현재 canonical 경로는 유지한다. 1차 정리에서는 문서 이동/이름변경을 하지 않는다.
- `PROJECT_STATUS.md`, `AGENTS.md`, `docs_for_ai/CONTEXT_SNAPSHOT.md`를 항상 기본 진입 세트로 본다.
- 의미 있는 동작 변경이 있으면 기본적으로 `DEV_LOG.md`, `PROJECT_STATUS.md`, `now_spec.md`를 함께 점검한다.
- `%BDIR%` 같은 비정상/잔재 경로는 1차에서 삭제하지 않고 "정체 확인 대상"으로만 본다.

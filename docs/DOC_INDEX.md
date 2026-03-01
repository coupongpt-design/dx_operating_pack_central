# 문서 인덱스 (최신 기준)

**최종 업데이트**: 2026-03-01 (폴더 정리 반영)

현재 프로젝트의 기준 문서는 아래 7개입니다.

1. `now_spec.md` — 현재 프로그램의 기술 스펙(기능/구조/검증 기준)
2. `PROJECT_STATUS.md` — 구현 상태, 완료 항목, 최신 검증 결과
3. `docs/USER_GUIDE.md` — 사용자 관점 사용법과 운영 팁
4. `docs/dev/SMOKE_TEST_CHECKLIST.md` — 실사용 전 수동 점검 시나리오와 Pass 기준
5. `docs/dev/BUTTON_CHECK.md` — 버튼/메뉴 연결 검증 정책(테스트 기반)
6. `DEV_LOG.md` — 세션별 변경 이력과 검증 기록
7. `docs/ASSET_MAP.md` — 코드/규칙/도구/문서/CI 자산 지도

## 보조 문서 (`docs/`)
- `docs/NEWBIE_GUIDE.md` — 신규 멤버 퀵 가이드
- `docs/dev/CONSULT_TOKEN_TEMPLATE.md` — 외부 자문 요청 토큰 절약 템플릿
- `docs/dev/UI_RELEAYOUT_PLAN.md` — UI 컴팩트 재배치 계획 (완료됨)
- `docs/dev/MULTI_AGENT_PROTOCOL.md` — 멀티 에이전트 운영 프로토콜
- `docs/reports/project_audit_latest.md` — 최신 프로젝트 감사 리포트

## AI 컨텍스트 문서 (`docs_for_ai/`, `dx_operating_pack/docs_for_ai/`)
- `CONTEXT_CORE.md` — core 모듈 인터페이스 스냅샷
- `CONTEXT_UI.md` — UI 인터페이스 스냅샷
- `CONTEXT_SNAPSHOT.md` — 전체 스냅샷

## 아카이브
- 과거 임시/개발용 문서: `archive/` 하위 보관
- 아카이브 문서는 참고용이며, 현재 스펙 기준으로 사용하지 않음

## 운영 규칙
- 문서 업데이트 시 7개 기준 문서 간 내용 불일치가 없도록 동기화한다.
- 백업 폴더(`backups/`) 문서는 수정/정리 대상에서 제외한다.
- 운영 감사 리포트: `python tools/project_audit.py`


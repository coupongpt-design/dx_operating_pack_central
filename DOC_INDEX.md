# 문서 인덱스 (최신 기준)

현재 프로젝트의 기준 문서는 아래 7개입니다.

1. `now_spec.md`
- 현재 프로그램의 기술 스펙(기능/구조/검증 기준).

2. `PROJECT_STATUS.md`
- 구현 상태, 완료 항목, 최신 검증 결과.

3. `USER_GUIDE.md`
- 사용자 관점 사용법과 운영 팁.

4. `SMOKE_TEST_CHECKLIST.md`
- 실사용 전 수동 점검 시나리오와 Pass 기준.

5. `BUTTON_CHECK.md`
- 버튼/메뉴 연결 검증 정책(테스트 기반).

6. `DEV_LOG.md`
- 세션별 변경 이력과 검증 기록.

7. `ASSET_MAP.md`
- 코드/규칙/도구/문서/CI 자산 지도(운영 관점 소스 오브 트루스).

## 아카이브
- 과거 단건 검토/개선 문서는 `archive/docs_legacy_20251124/`에 보관.
- 아카이브 문서는 참고용이며, 현재 스펙 기준으로 사용하지 않음.

## 보조 문서
- `CONSULT_TOKEN_TEMPLATE.md`
  - 외부 자문 요청 시 토큰 절약을 위한 질문 템플릿/체크리스트.

## 운영 규칙
- 문서 업데이트 시 위 7개 기준 문서 간 내용 불일치가 없도록 동기화한다.
- 백업 폴더(`backups/`) 문서는 수정/정리 대상에서 제외한다.
- 운영 감사 리포트는 `python tools/project_audit.py`로 생성한다.

## Start Here (New Contributors)
- `NEWBIE_GUIDE.md` : first-day quick guide for new members.

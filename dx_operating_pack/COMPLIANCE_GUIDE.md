# Compliance Guide

## 목적
- AI/사람 협업에서 품질/보안/성능 기준을 커밋 전에 일관되게 검증.

## 최소 준수 항목
1. 품질
- 관련 테스트 PASS 필수.
- 리스크 트리거 시 전체 `pytest -q` PASS 필수.
2. 보안
- `python tools/check_ai_security.py` 결과 무결성 확인.
- 비밀정보 하드코딩 금지.
3. 문서
- 의미 있는 동작 변경 시 `PROJECT_STATUS`, `DEV_LOG`, `now_spec` 동기화.
4. 운영
- 규칙 파일은 단독 변경 세트 원칙.

## 권장 자동화
- pre-commit: 규칙 가드 + 스코프 경고.
- CI: rule-guard/job 분리, 경로 필터링, 캐시 적용.


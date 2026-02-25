# Pack Coverage (v2)

## 외부 자문 반영 여부

1) 컨텍스트/지식 베이스
- 반영: `docs/adr/*`, `docs/KNOWLEDGE_BASE.md`, `docs/LESSONS_LEARNED.md`

2) LLM-Ready 자동화
- 반영: `tools/generate_context_snapshot.py`, `tools/context_compressor.py`, `tools/dependency_graph_gen.py`
- 반영: `docs_for_ai/*`

3) 품질/보안 가드
- 반영: `tools/check_ai_security.py`, `tools/secret_leak_detector.py`
- 반영: `COMPLIANCE_GUIDE.md`, `docs/COMPLIANCE_CHECKLIST.md`

4) 비용/토큰 최적화
- 반영: `tools/token_usage_analyzer.py`
- 반영: `prompt_recipes/*`, `.cursor/prompts/*`

5) 다중 프로젝트 동기화/설치
- 반영: `tools/setup_dx.py` (원클릭 설치)
- 반영: `tools/sync_dx_pack.py` (공용 팩 pull + 재설치)
- 반영: `MANIFEST_AI.yaml` (파일별 AI 사용 지침)

6) 계층 컨텍스트/레슨 캡처
- 반영: `docs_for_ai/SCOPE_GUIDE.md`
- 반영: `templates/folder_rules/*.template`
- 반영: `tools/capture_lesson_draft.py` (레슨 초안 자동화)

7) 운영 시스템 핵심
- 반영: rules/hooks/CI/gate tools/multi-agent/tests 전체

## 추가 반영
- 재사용 가능한 코어/UI 모듈 샘플: `reusable/core/*`, `reusable/ui/*`
- 외부 환경 설정 백업/마스킹: `optional/external/*`, `tools/export_external_profiles.py`

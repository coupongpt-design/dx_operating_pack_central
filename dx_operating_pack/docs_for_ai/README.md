# DOCS_FOR_AI

AI 컨텍스트 주입용 문서 모음입니다.

## 운영 원칙
- 긴 서술보다 인터페이스/의사코드 중심.
- 최신 상태를 반영한 스냅샷 문서 사용.

## 권장 생성 순서
1. `python tools/generate_context_snapshot.py --scope all --out dx_operating_pack/docs_for_ai/CONTEXT_SNAPSHOT.md`
2. `python tools/dependency_graph_gen.py --out dx_operating_pack/docs_for_ai/DEPENDENCY_GRAPH.md`
3. `python tools/generate_session_brief.py --out dx_operating_pack/docs_for_ai/SESSION_BRIEF.md`
4. 필요 파일에 대해 `python tools/context_compressor.py ...`

## 포함 문서
- `SYSTEM_PSEUDOCODE.md`
- `INTERFACES.md`
- (생성물) `CONTEXT_SNAPSHOT.md`, `DEPENDENCY_GRAPH.md`, `SESSION_BRIEF.md`


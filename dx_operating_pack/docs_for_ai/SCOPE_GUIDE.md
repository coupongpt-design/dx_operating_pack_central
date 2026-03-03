# Scope Guide for Context Loading

## 목적
- 토큰 소모를 줄이기 위해 도메인별 컨텍스트만 선택 로딩.

## 사용 예시
```bat
python tools/generate_context_snapshot.py --scope core --out dx_operating_pack/docs_for_ai/CONTEXT_CORE.md
python tools/generate_context_snapshot.py --scope ui --out dx_operating_pack/docs_for_ai/CONTEXT_UI.md
python tools/generate_context_snapshot.py --scope dx --out dx_operating_pack/docs_for_ai/CONTEXT_DX.md
python tools/generate_session_brief.py --out dx_operating_pack/docs_for_ai/SESSION_BRIEF.md
```

## 권장 시나리오
- core 버그: `--scope core`
- UI 레이아웃/오버레이: `--scope ui`
- 규칙/CI/게이트/워크플로우: `--scope dx`


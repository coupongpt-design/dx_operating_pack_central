# dk_system (Stage 1)

이 폴더는 DX 운영 시스템 전용 영역입니다.
현재는 안전하게 "구조만" 먼저 만들고, 실제 파일 이동은 Stage 2에서 진행합니다.

## 현재 실제 위치(아직 이동 안 함)
- `dx_operating_pack/**`
- `.githooks/**`
- `rules/**`
- `tools/**` (거버넌스/가드 계열)
- `AGENTS.md`
- `.cursorrules`

## Stage 2 이동 원칙
1. 기존 경로는 즉시 삭제하지 않고 `archive/` 백업 후 전환.
2. 훅/게이트/테스트가 모두 통과한 뒤 최종 경로 확정.
3. 운영 규칙 정본은 `AGENTS.md` 기준으로 유지.

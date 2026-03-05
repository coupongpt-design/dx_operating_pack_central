# dk_system (Stage 2)

이 폴더는 DX 운영 시스템 전용 영역입니다.
Stage 2에서 실제 운영 자산 일부를 이동했고, 루트 경로는 호환 래퍼로 유지합니다.

## Stage 2 적용 상태
- 실파일 이동:
  - `dk_system/.githooks/**` (hook 구현)
  - `dk_system/tools/*.py` (운영 도구 구현)
- 루트 호환 래퍼:
  - `.githooks/**` -> `dk_system/.githooks/**`
  - `tools/*.py` -> `dk_system/tools/*.py`
- 규칙 미러:
  - `dk_system/AGENTS.md`
  - `dk_system/.cursorrules`
  - `dk_system/rules/AGENTS.md`

## 아직 루트에 유지되는 항목
- `dx_operating_pack/**` (팩 본체; 테스트/경로 결합이 많아 후속 단계로 분리)
- 루트 정본 규칙:
  - `AGENTS.md`
  - `.cursorrules`
  - `rules/AGENTS.md`

## 운영 원칙
1. 루트 경로를 직접 호출하는 기존 자동화는 계속 동작해야 한다.
2. 실제 로직은 `dk_system` 하위로 점진 이동한다.
3. 이동 후에는 무결성/게이트 테스트를 통과해야 완료로 간주한다.

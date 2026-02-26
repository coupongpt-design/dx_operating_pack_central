# 🔍 Project Governance Audit Report (2026-02-26 12:37:56)

## 1) Verification Health
- 총 테스트 파일 수: 97개
- Gate 상태: PASS

## 2) Asset Integrity Matrix
| Group | Path | Status |
| :--- | :--- | :--- |
| Product | `app/core/runner.py` | ✅ |
| Product | `app/core/exceptions.py` | ✅ |
| Product | `app/main.py` | ✅ |
| Product | `app/ui/styles.py` | ✅ |
| Rule Guard | `AGENTS.md` | ✅ |
| Rule Guard | `.cursorrules` | ✅ |
| Rule Guard | `tools/git_hook_guards.py` | ✅ |
| Rule Guard | `tests/test_rule_docs_sync.py` | ✅ |
| Rule Guard | `tests/test_rule_guard_steps_mutation.py` | ✅ |
| Rule Guard | `.githooks/pre-commit` | ✅ |
| Rule Guard | `.githooks/commit-msg` | ✅ |
| DX Tools | `tools/task_start_guard.py` | ✅ |
| DX Tools | `tools/task_finish.py` | ✅ |
| DX Tools | `tools/test_selector.py` | ✅ |
| DX Tools | `tools/preflight_env.py` | ✅ |
| DX Tools | `tools/post_task_gate.py` | ✅ |
| DX Tools | `tools/project_audit.py` | ✅ |
| Verification | `tests` | ✅ |
| Verification | `pytest.ini` | ✅ |
| Verification | `test_core_logic.py` | ✅ |
| Resources | `images` | ✅ |
| Resources | `logs` | ✅ |
| Resources | `app/core/scenario_wizard_templates.json` | ✅ |
| Resources | `app/core/scenario_wizard_user_templates.json` | ✅ |
| Resources | `app/utils/runtime_paths.py` | ✅ |
| Infrastructure | `ASSET_MAP.md` | ✅ |
| Infrastructure | `now_spec.md` | ✅ |
| Infrastructure | `PROJECT_STATUS.md` | ✅ |
| Infrastructure | `DEV_LOG.md` | ✅ |
| Infrastructure | `DOC_INDEX.md` | ✅ |
| Infrastructure | `USER_GUIDE.md` | ✅ |
| Infrastructure | `.github/workflows/ci.yml` | ✅ |

## 3) Gate Freshness
- Gate file: ✅ `.git\post_task_gate.json`
- Last gate: `2026-02-26 12:12:22`
- TTL check (30m): ✅ fresh (age=1533s)

## 4) Resource Snapshot
- images 파일 수(대표 확장자): 0
- logs/*.jsonl 파일 수: 2

## 5) Docs Sync Health
| Path | Exists | Last Modified |
| :--- | :--- | :--- |
| `now_spec.md` | ✅ exists | 2026-02-26 12:37:31 |
| `PROJECT_STATUS.md` | ✅ exists | 2026-02-26 12:37:14 |
| `DEV_LOG.md` | ✅ exists | 2026-02-26 12:37:42 |
| `DOC_INDEX.md` | ✅ exists | 2026-02-26 11:33:43 |
| `ASSET_MAP.md` | ✅ exists | 2026-02-26 12:37:52 |

## 6) Maintenance Guide
- [ ] `task_finish.py`를 통한 문서 동기화 여부 확인
- [ ] 30분 초과 stale gate 재실행 여부 점검
- [ ] 누락 자산 발생 시 ASSET_MAP와 실제 경로 동시 갱신

## 7) Maintenance Checklist
- [x] Gate TTL(30m) fresh
- [ ] Doc mtimes reasonably aligned (<=1h gap)
- [x] Required assets present

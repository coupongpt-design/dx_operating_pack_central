# AGENTS.md (Canonical Agent Charter)

## 0) Priority
1. System/developer/runtime rules.
2. Explicit user instructions.
3. This file (`AGENTS.md`).
4. `.cursorrules` (detailed mirror/notes).

## 1) Session Gate (Required)
1. Read `PROJECT_STATUS.md` first.
2. Summarize current focus in 2 lines.
3. Declare mode (`Compact` or `Precision`) before edits.

## 2) Mode Policy
- Default: `Compact`.
- Enter `Precision` if any trigger is true:
  - touched files >= 5 in one task
  - `StepData` field add/rename/remove
  - serialization/load-save path touched
  - thread/signal/worker orchestration touched
  - runner flow control (`goto/repeat/branch`) touched
  - repro unclear or regression scope unknown
- Stay in `Precision` until implementation + validation complete.

## 3) Multi-Agent Workflow
- Default workflow (2-Agent): `Executor -> Guardian`.
- Escalated workflow (3-Agent): `Planner -> Executor -> Guardian`.
- Escalation rule:
  - Use 3-Agent when `Precision` trigger is active.
- Role constraints:
  - `Planner`: plan/risk/verification/rollback only (no code edits).
  - `Executor`: implement minimal diff + run required tests.
  - `Guardian`: read-only review, PASS/FAIL with exact fix instructions.
- Governance rule:
  - Rule-file changes (`AGENTS.md`, `.cursorrules`, rule-guard tests) must be isolated in dedicated change sets.

## 4) Non-Negotiable Engineering Rules
1. Worker threads never touch UI directly; use `pyqtSignal`.
2. `MainWindow` owns `steps` and `UndoStack`.
3. No direct `self.steps` mutation for CRUD/reorder; use `self._push_command(...)`.
4. Branch/jump targets prefer `step_id`; fallback safely on missing target.

## 5) Data/Runtime Integrity
1. `StepData` changes require model + serialization + runner + tests together.
2. New defaults must remain backward-safe for old macros.
3. No partial edits (`...`, stubbed/incomplete logic) in production paths.

## 6) Quality Gate
1. Core logic changes: run focused tests immediately.
2. Risky/cross-cutting changes: run `python -m pytest -q`.
3. Runtime-sensitive changes: run `python run_health_check.py` when applicable.
4. Keep `tests/test_rule_guard_steps_mutation.py` green.
5. Keep `tests/test_rule_docs_sync.py` green.

## 7) Reporting Discipline
1. Delta-only reporting (changed files, behavior delta, test delta).
2. Use short progress updates and concise finals by default.
3. Avoid dumping long raw command output unless explicitly requested.

## 8) Documentation Sync
For meaningful behavior changes, sync:
- `DEV_LOG.md`
- `PROJECT_STATUS.md`
- `now_spec.md`

## 9) Environment
- Workspace root: `d:\down\autocording\매크로모듈화`
- Keep backup artifacts under `backups/` untouched.

## 10) Git Governance
1. Track all changes under Git; use diff-based review before commit.
2. Constitutional files:
   - `AGENTS.md`
   - `.cursorrules`
   - `tests/test_rule_docs_sync.py`
   - `tests/test_rule_guard_steps_mutation.py`
3. Constitutional file policy:
   - No delete/recreate.
   - Edit-in-place + diff review only.
   - Keep changes isolated in dedicated change sets.
4. Before risky refactors (`runner/signal/StepData`), create a snapshot commit.
5. End-of-session check: clean `git status`, intended `git diff`, required tests green.
6. Post-Task Commit Gate (mandatory):
   - Run related targeted tests first.
   - If any risk trigger exists, run full `python -m pytest -q`.
   - Review `git diff` and confirm no unintended changes.
   - Commit only when tests pass and diff is clean.
   - If any condition fails, do not commit.
   - Commit message must include:
     - `Tests:`
     - `- targeted: PASS / FAIL`
     - `- full suite: <exact pytest -q summary line if executed>`

## 11) Synced Normative Block (for `.cursorrules`)
<!-- SYNC_BLOCK_START -->
Priority: system/dev/runtime > user > AGENTS.md > .cursorrules
Session Gate: read PROJECT_STATUS.md -> 2-line current-focus summary -> declare mode
Mode: compact by default; precision on high-risk triggers; keep precision through validation
Precision triggers: files>=5, StepData change, serialization change, thread/signal change, runner flow change, unclear repro/scope
Multi-Agent flow: default Executor->Guardian; precision trigger -> Planner->Executor->Guardian
Role constraints: Planner no code edits; Guardian read-only PASS/FAIL gate
Governance: rule-file changes (AGENTS/.cursorrules/rule-guard tests) in dedicated change set
Constitutional files: AGENTS.md, .cursorrules, tests/test_rule_docs_sync.py, tests/test_rule_guard_steps_mutation.py
Constitutional policy: no delete/recreate; edit+diff only; isolated change set
Risk snapshot: create pre-refactor commit for runner/signal/StepData
Session close: status clean + intended diff + required tests green
Post-task gate: targeted tests first; run full pytest on risk trigger; commit only if tests pass and diff is clean
Commit message tests block: include targeted PASS/FAIL and full-suite exact pytest summary line when executed
Thread/UI safety: worker threads never touch UI directly; use pyqtSignal
State ownership: MainWindow owns steps/UndoStack; dialogs return data only
Command rule: no direct self.steps CRUD/reorder; use _push_command(...)
Data integrity: StepData changes require model+serialization+runner+tests; defaults backward-safe
Quality gate: focused tests for core; full pytest for risky changes; health_check for runtime-sensitive
Mutation guard: keep tests/test_rule_guard_steps_mutation.py passing
Sync guard: keep tests/test_rule_docs_sync.py passing
Docs sync: DEV_LOG.md + PROJECT_STATUS.md + now_spec.md on meaningful behavior changes
Environment: do not modify backups/
Sync policy: AGENTS.md canonical; .cursorrules mirrors this block only; direction AGENTS -> .cursorrules
<!-- SYNC_BLOCK_END -->

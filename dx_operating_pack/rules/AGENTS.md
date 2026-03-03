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
4. Strict data binding for text actions:
   - Before any text output, action runners must pass text through shared placeholder replacement (`TemplateProcessor` / equivalent centralized path).
   - `pyautogui.write()` / `pyautogui.typewrite()` must never receive unresolved placeholders (`{{var}}`, `{var}`).
5. If unresolved placeholders remain at runtime, fail fast (error path) instead of typing raw placeholders.

## 6) Quality Gate
1. Core logic changes: run focused tests immediately.
2. Risky/cross-cutting changes: run `python -m pytest -q`.
3. Runtime-sensitive changes: run `python run_health_check.py` when applicable.
4. Keep `tests/test_rule_guard_steps_mutation.py` green.
5. Keep `tests/test_rule_docs_sync.py` green.
6. Integration tests must not monkeypatch internal business-logic functions for data binding paths.
   - Mock only external side effects (`pyautogui`, sleep, I/O edge adapters).
   - Verify end-to-end trace: input data value -> final runtime output value.

## 7) Reporting Discipline
1. Delta-only reporting (changed files, behavior delta, test delta).
2. Use short progress updates and concise finals by default.
3. Avoid dumping long raw command output unless explicitly requested.
4. Markdown handoff integrity (mandatory when requested):
   - If user asks for copy/paste markdown delivery, put all required handoff content inside one outer markdown block.
   - Do not place required diff/snippets/results outside that block.
   - Before sending, verify fences are not broken by nested backticks.

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
     - `Summary:` (what/why in 1-3 lines)
     - `Changes:` (key files or behavior delta)
   - `Tests:`
   - `- targeted: PASS / FAIL`
   - `- full suite: <exact pytest -q summary line if executed>`
   - `Risks/Follow-up:` (or `none`)
7. Hook installation (mandatory per clone/environment):
   - Run `python tools/install_git_hooks.py` once.
   - Keep `git config core.hooksPath` set to `.githooks`.
8. Hook enforcement:
   - `commit-msg` rejects commits missing required sections or tests lines.
   - `commit-msg` rejects tests lines that do not match `.git/post_task_gate.json` summaries.
   - `pre-commit` rejects constitutional file delete/rename/copy.
   - `pre-commit` rejects staged runtime artifacts (`__pycache__/`, `*.pyc`, `logs/run_events_*.jsonl`).
   - Exception: artifact cleanup commit may stage deletions of those artifact paths.
   - `pre-commit` rejects any staged change under `backups/`.
   - `pre-commit` rejects mixed change sets where constitutional files are staged with non-constitutional files.
   - `pre-commit` requires fresh post-task gate proof file (`.git/post_task_gate.json`) matching current `HEAD` and staged hash.
9. Post-task gate proof:
   - Before commit, run:
     - `python tools/post_task_gate.py --targeted auto`
     - or `python tools/post_task_gate.py --targeted "<targeted pytest command>"`
   - Gate script writes `.git/post_task_gate.json`.
   - If risk trigger is active, gate script must run full `python -m pytest -q` and mark PASS.
10. Standardized finish command:
   - Preferred: `python tools/task_finish.py --subject "<commit subject>"`
   - Script flow: auto targeted selection -> risk-based full suite -> gate proof -> commit template generation.
11. Scope limit guard:
   - `pre-commit` blocks over-wide staged scope (files/lines threshold) and requires atomic split commits.
12. Push gate:
   - `pre-push` runs:
     - `python -m pytest -q tests/test_rule_docs_sync.py tests/test_rule_guard_steps_mutation.py tests/test_git_hook_guards.py tests/test_test_selector.py tests/test_task_finish.py tests/test_post_task_gate.py tests/test_ci_governance_guard.py`
13. CI governance gate (server-side, `--no-verify` backstop):
   - CI must run `python tools/ci_governance_guard.py`.
   - CI validates commit-message schema and commit-level file policy in pushed/PR commit range.

## 11) Waste-Reduction Protocol (Mandatory)
1. Search Budget:
   - Max 4 `rg` queries per task.
   - Max 2 file opens; no full-file dumps.
   - If exceeded, stop and return:
     - top 2 hypotheses
     - 1 missing critical info
     - next minimal query only
2. No Duplicate Queries:
   - Do not repeat same keyword+file search.
   - List planned queries once before execution.
   - Refine only when new evidence appears.
3. Write-First Search Order:
   - WRITES -> STATE TRANSITIONS -> CALLERS -> UI labels last.
4. No Full File Dumps:
   - `type`/`cat` entire file prohibited.
   - Use context windows only (`-A/-B`).
5. Output Contract (Delta-only):
   - Return 2-5 relevant snippets (`file:line`)
   - Provide 3-line definition summary
   - Propose exact change locations + targeted tests

## 12) Synced Normative Block (for `.cursorrules`)
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
Commit message detail block: include Summary + Changes + Tests + Risks/Follow-up (or none)
Hook install: run python tools/install_git_hooks.py; keep core.hooksPath=.githooks
Hook enforcement: commit-msg requires commit sections/tests lines and gate-summary match; pre-commit blocks constitutional delete/rename/copy, backups/ changes, mixed constitutional+nonconstitutional staging, staged artifacts (__pycache__, *.pyc, logs/run_events_*.jsonl), and missing/stale post-task gate proof
Hook cleanup exception: artifact cleanup commit may delete tracked artifact paths
Post-task gate proof: run python tools/post_task_gate.py --targeted auto (or explicit command) before commit; proof must match current HEAD + staged hash; on high-risk paths (thread/signal/runner/StepData/serialization/BaseCommand/UndoStack) full pytest PASS is mandatory
Standard finish command: prefer python tools/task_finish.py --subject "<commit subject>" to run gate + template generation
Scope limit guard: pre-commit blocks oversized staged scope and forces atomic split commits
Push gate: pre-push runs rule guard tests (docs sync + steps mutation + hook guard + selector/task_finish/post_task/ci-governance)
CI governance gate: server-side run tools/ci_governance_guard.py to validate commit messages and file policy across commit range
Waste budget: max 4 rg queries/task; max 2 file opens; if exceeded stop with top2 hypotheses + 1 missing info + next minimal query
No duplicate queries: no repeated keyword+file search; plan queries once; refine only with new evidence
Search order: WRITES -> STATE TRANSITIONS -> CALLERS -> UI labels last
No full dumps: no type/cat full files; use context windows only
Output contract: 2-5 snippets + 3-line definition + exact change locations + targeted tests
Markdown handoff integrity: when markdown-only delivery is requested, include all required handoff content in one outer block; keep required content outside that block at zero; verify fence integrity before send
Thread/UI safety: worker threads never touch UI directly; use pyqtSignal
State ownership: MainWindow owns steps/UndoStack; dialogs return data only
Command rule: no direct self.steps CRUD/reorder; use _push_command(...)
Data integrity: StepData changes require model+serialization+runner+tests; defaults backward-safe
Strict data binding: action runners must use centralized template replacement before text output; unresolved placeholders must never be typed
Quality gate: focused tests for core; full pytest for risky changes; health_check for runtime-sensitive
Data-binding test rule: no monkeypatch of internal binding logic in integration tests; verify end-to-end value trace to final output
Mutation guard: keep tests/test_rule_guard_steps_mutation.py passing
Sync guard: keep tests/test_rule_docs_sync.py passing
Docs sync: DEV_LOG.md + PROJECT_STATUS.md + now_spec.md on meaningful behavior changes
Environment: do not modify backups/
Sync policy: AGENTS.md canonical; .cursorrules mirrors this block only; direction AGENTS -> .cursorrules
<!-- SYNC_BLOCK_END -->

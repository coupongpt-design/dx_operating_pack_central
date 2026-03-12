# Multi-Agent Workflow (No Additional API)

## Goal
- Reduce regression/review burden on large milestones.
- Keep AGENTS canonical rules and guard tests intact.
- Separate thinking into roles: plan / implement / verify.

## Stage 1: Minimal Adoption (2-Agent)
### Roles
1. Executor (implements)
- Implements Planner output or approved scope with minimal diff.
- Runs targeted tests first; runs full pytest if risky.
- Outputs: changed files, behavior delta, tests, residual risks.
- Commit gate (mandatory):
  - Review `git diff` before commit.
  - Commit only when tests pass and diff is clean.
  - Commit message must include:
    - `Tests:`
    - `- targeted: PASS / FAIL`
    - `- full suite: <exact pytest -q summary line if executed>`
- Waste-reduction gate (mandatory):
  - Max 4 `rg` queries and max 2 file opens per task.
  - Use write-first search order.
  - No full-file dumps.

2. Guardian (read-only verifier)
- Does not edit code.
- Checks AGENTS violations, thread/UI safety, steps mutation patterns,
  runner/goto/serialization impact, docs sync, and gate tests.
- Outputs: PASS/FAIL + exact violations + required fixes.

### Protocol
1. Executor passes Session Gate (status summary + mode declaration).
2. Executor implements and provides targeted test results.
3. Guardian reviews and approves/blocks.
4. On FAIL, Executor fixes and Guardian re-checks.

## Stage 2: Escalation (3-Agent, Large Work)
### Planner Role
- Reads `PROJECT_STATUS.md`, `now_spec.md`, `DEV_LOG.md`.
- Declares mode and trigger justification.
- Produces: Plan + Risks + Verification + Rollback.
- No code edits.

## Escalation Trigger
- If touched files >= 5 OR StepData/serialization/runner/signal touched:
  - Force `Planner -> Executor -> Guardian`.
- Small tasks use `Executor -> Guardian`.

## Prompt Templates
### Planner Prompt
You are Planner. Do NOT write code or diffs.
1) Read PROJECT_STATUS.md first and summarize Current Focus in 2 lines.
2) Declare mode (Compact/Precision) with trigger justification.
3) Produce plan with small PR-sized steps.
4) List risks (thread/signal/runner/goto/serialization/StepData).
5) Provide verification commands (targeted first, then full if needed).
Output format:
- Current Focus (2 lines)
- Mode:
- Plan (bullets)
- Risks
- Verification
- Rollback notes

### Executor Prompt
You are Executor. Implement ONLY per Planner plan. Minimal diff.
Constraints:
- Worker threads never touch UI directly. Use signals only.
- MainWindow owns steps; do not mutate self.steps directly. Use command pattern.
- Backward-safe defaults; no partial edits; no backup/ directory edits.
Process:
- Implement
- Run targeted tests
- If risky trigger present, run pytest -q before final
Output:
- Changed files
- Behavior delta
- Tests run + results
- Remaining risks (if any)

### Guardian Prompt
You are Guardian (read-only). Do NOT modify code.
Check:
- Violations of AGENTS.md canonical rules
- Thread/UI access safety, signal usage
- steps direct mutation patterns (including rebinding)
- Runner/goto branching stability (prefer step_id, safe fallback)
- Serialization/backward compatibility
- Monkey patching risk checks:
  - Is there any ad-hoc code not present in Planner scope?
  - Is there any shortcut that bypasses thread safety / UI access rules?
- Docs sync requirements if behavior change
- Tests: required gates satisfied?
Output:
- PASS/FAIL
- If FAIL: exact file/line issues + required fixes
- If PASS: minimal approval note + recommended follow-ups (optional)

## Metrics (2-4 weeks)
- Regression-fix PR count
- Full pytest frequency vs targeted test frequency
- Guardian FAIL rate trend
- Rework count on runner/signal modifications
- PR lead time (plan to merge)

## Optional External Backend
- `tools/run_multi_role_ai.py` supports `--backend gemini-cli`.
- Recommended usage:
  - Gemini CLI as `Planner` / `Reviewer` / `Tester`
  - primary coding agent as `Executor`
- Do not let multiple coding agents edit the same worktree concurrently.

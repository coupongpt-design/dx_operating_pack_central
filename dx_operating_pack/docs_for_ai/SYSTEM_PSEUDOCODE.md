# System Pseudocode (LLM-Ready)

```text
on_task_start:
  run task_start_guard
  read PROJECT_STATUS
  decide mode (compact|precision)

on_code_change:
  apply minimal diff
  run targeted tests from test_selector
  if risk_trigger: run full pytest

on_task_finish:
  run post_task_gate
  ensure docs sync if behavior changed
  prepare commit template with scope/tests block
```

```text
multi_agent_flow:
  if precision_trigger:
    Planner(plan,risk,verification,rollback)
    Executor(implement + tests)
    Guardian(read-only pass/fail)
  else:
    Executor -> Guardian
```


# Refactor Recipe

```text
Goal:
- <리팩터 목적>

Constraints:
- behavior parity 유지
- risky module touched 시 full pytest 필수
- output: changed files + key diff hunks + pytest summary

Steps:
1) PLAN: scope/risk/rollback 명시
2) IMPLEMENT: minimal diff
3) VERIFY: targeted -> full(if risk)
4) REPORT: delta-only
```


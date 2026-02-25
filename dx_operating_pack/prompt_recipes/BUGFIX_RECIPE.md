# Bugfix Recipe

```text
Inputs:
- repro steps (1 line)
- expected vs actual

Process:
1) locate write path first
2) add regression test
3) patch minimal code
4) run targeted tests (+ full if risk)

Output:
- root cause
- fix location
- tests added/updated
- pytest summary
```


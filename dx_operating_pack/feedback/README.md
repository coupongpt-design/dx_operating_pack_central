# Feedback Loop

이 폴더는 DX Operating Pack 지식 환류(Feedback Loop) 전용 영역입니다.

- `LATEST_INSIGHT.yaml`
  - 최근 task에서 자동 추출된 인사이트 스냅샷.
  - `tools/capture_lesson_draft.py --from-staged` 실행 시 갱신됩니다.
- `outbox/`
  - `tools/push_dx_feedback.py`가 생성한 상신 번들 저장소.
- `inbox/`
  - 중앙 DX Repo에서 수집/승격 대상 번들을 보관하는 경로(옵션).

권장 루프:
1. `python tools/post_task_gate.py --targeted auto`
2. `python tools/push_dx_feedback.py --base HEAD~1 --head HEAD --remote-url <CENTRAL_REPO_URL>`
3. 중앙 레포에서 `python tools/promote_dx_feedback.py --apply`

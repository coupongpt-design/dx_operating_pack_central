# DX Operating Pack v2.1 (Stable)

DX Operating Pack은 규칙/가드/테스트/동기화를 표준화해, 새 프로젝트에서도 동일한 개발 운영 체계를 빠르게 재현하기 위한 운영 시스템입니다.

## 1) 신규 프로젝트 퀵스타트 (Bootstrap One-liner)
사전 조건:
- 대상 폴더에서 먼저 `git init` 수행
- Git 설치 필요 (`git --version`)

원라인:
- `curl -fsSL <RAW_SETUP_DX_URL> -o setup_dx.py && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`
- `wget -qO setup_dx.py <RAW_SETUP_DX_URL> && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`

참고:
- `setup_dx.py`는 시작 시 Git 설치 여부와 Git 저장소 여부(`git rev-parse --is-inside-work-tree`)를 자동 점검합니다.
- 조건 미충족 시 가이드 메시지를 출력하고 종료합니다.

## 2) 중앙 레포 기반 설치/업데이트
설치(최초):
- `python dx_operating_pack/tools/setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`

업데이트(지속 운영):
- `python dx_operating_pack/tools/sync_dx_pack.py --remote-url <CENTRAL_REPO_URL_OR_PATH> --project-root . --mode copy --overwrite`

## 3) Safe Sync 데이터 보호 정책
`sync_dx_pack.py --overwrite` 실행 시에도 아래 로컬 파일은 보호됩니다.

보호 대상:
- `DEV_LOG.md`
- `PROJECT_STATUS.md`
- `now_spec.md`
- `**/*.local.*`

보호 방식:
1. 동기화 직전 보호 파일 별도 백업
2. 팩 업데이트 수행
3. 보호 파일 자동 복원(`finally` 경로 보장)

무결성:
- v2.1 검증에서 SHA256 비교로 복원 전후 파일 동일성이 확인되었습니다.

추가 안전장치:
- 팩 전체 백업: `.dx_cache/backups/pack_<timestamp>/dx_operating_pack`

## 4) 운영 주의사항 (Guardrails)
1400라인 제한:
- 단일 커밋에서 변경 라인이 과도하면 가드에 의해 차단됩니다.
- 대형 변경은 원자 단위(Atomic)로 분할 커밋하십시오.

Pre-flight/Troubleshooting:
- Git 미설치/미초기화 시 스크립트가 즉시 중단하고 안내를 출력합니다.
- Private 레포 인증 실패 시 SSH 키/PAT 설정 가이드와 `git ls-remote <repo-url>` 점검 절차를 출력합니다.

필수 태스크 흐름:
1. 시작 전: `python tools/task_start_guard.py`
2. 작업 종료 전: `python tools/post_task_gate.py`
3. 필요 시: `python tools/check_ai_security.py`

## 5) For AI Agent
에이전트는 작업 시작 직후 `MANIFEST_AI.yaml`을 먼저 읽어야 합니다.

효과:
- 사용 가능한 도구/목적/실행 조건을 즉시 파악
- 추측 기반 도구 선택 감소
- 토큰 낭비 및 잘못된 수정 경로 감소

## 6) 문서 인덱스
- 상세 설치 절차: `INSTALL_IN_NEW_PROJECT.md`
- 에이전트 온보딩 규칙: `AGENT_ONBOARDING.md`

## 7) 지식 환류(Feedback Loop)
작업 지식을 일회성으로 버리지 않고 DX Pack으로 상신하려면 아래 루프를 사용합니다.

1. 게이트 실행 시 인사이트 자동 추출
   - `python tools/post_task_gate.py --targeted auto`
   - 성공 시 `tools/capture_lesson_draft.py --from-staged`가 호출되어:
     - `docs/LESSONS_LEARNED_DRAFT.md` 업데이트
     - `feedback/LATEST_INSIGHT.yaml` 생성/갱신

2. 피드백 번들 생성/상신
   - 로컬 번들 생성:
     - `python tools/push_dx_feedback.py --base HEAD~1 --head HEAD`
   - 중앙 레포 inbox 반영(+push):
     - `python tools/push_dx_feedback.py --base HEAD~1 --head HEAD --remote-url <CENTRAL_REPO_URL> --push`

3. 중앙 승격/확산(central repo)
   - dry-run:
     - `python tools/promote_dx_feedback.py`
   - apply:
     - `python tools/promote_dx_feedback.py --apply`
   - 적용 시 `feedback/inbox/*` 번들의 reusable 변경이 반영되고 `feedback/processed/`로 이동됩니다.
   - 운영 원칙 정리:
     - `docs/CENTRAL_PACK_OPERATING_MODEL.md`
   - 참고:
     - 이 문서는 PACK 운영용이며, 일반 제품 기능 작업의 기본 읽기 문서는 아닙니다.

4. 산출물 위치
   - `feedback/outbox/<timestamp>_<head>/feedback_manifest.json`
   - `feedback/outbox/.../LATEST_INSIGHT.yaml`
   - `feedback/outbox/.../LESSONS_LEARNED.md`
   - `feedback/outbox/.../reusable_changes/*`

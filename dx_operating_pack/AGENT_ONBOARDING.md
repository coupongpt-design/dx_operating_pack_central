# AGENT_ONBOARDING

## 목적
- 새 프로젝트에서 DX Pack을 빠르게 적용하고, 동기화 시 로컬 설정 손실을 방지한다.

## 1분 온보딩
1. 프로젝트 루트에서 Git 초기화 확인:
   - `git --version`
   - `git rev-parse --is-inside-work-tree`
2. 원격 중앙 팩으로 설치:
   - `python dx_operating_pack/tools/setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`
3. 훅 설치:
   - `python tools/install_git_hooks.py`

## 환경 사전조건(스크립트가 자동 검증)
- `setup_dx.py` / `sync_dx_pack.py` 시작 시 자동 체크:
  - Git 설치 여부 (`git --version`)
  - 대상 프로젝트의 Git 초기화 여부 (`git rev-parse --is-inside-work-tree`)
- 미충족 시 명확한 에러를 출력하고 즉시 종료한다.

## Private 중앙 레포 인증 실패 시
- clone/pull 실패 로그 다음 안내를 따른다:
  - SSH: 공개키 등록 후 `git@...` URL 사용
  - HTTPS + PAT: Personal Access Token + credential manager 설정
  - 수동 확인: `git ls-remote <repo-url>`

## 동기화 안전장치(`sync_dx_pack.py`)
- Sync 직전 `dx_operating_pack` 전체를 `dx_operating_pack_bak`으로 자동 백업한다.
- 로컬 보호 파일은 덮어쓰기 이후 자동 복원한다.
  - `**/*.local.*`
  - `DEV_LOG.md`
  - `PROJECT_STATUS.md`
  - `now_spec.md`

## 권장 동기화 명령
- `python dx_operating_pack/tools/sync_dx_pack.py --remote-url <CENTRAL_REPO_URL_OR_PATH> --project-root . --mode copy --overwrite`

## 운영 팁
- 대규모 변경 전: 스냅샷 커밋 후 동기화 실행.
- 동기화 후: `python tools/task_start_guard.py` -> `python tools/task_finish.py --subject "<msg>" --scope rule`.

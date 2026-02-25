# INSTALL_IN_NEW_PROJECT (v2.1)

이 문서는 빈 프로젝트에 DX Operating Pack v2.1을 설치하고, 중앙 레포 기반으로 안정적으로 운영하는 절차를 설명합니다.

## 최종 퀵스타트 명령어
```bat
git init && curl -fsSL <RAW_SETUP_DX_URL> -o setup_dx.py && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite
```

```bat
git init && wget -qO setup_dx.py <RAW_SETUP_DX_URL> && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite
```

## 0) 사전 조건
- Git 설치 확인: `git --version`
- 프로젝트 루트에서 Git 초기화: `git init`

주의:
- `setup_dx.py`, `sync_dx_pack.py`는 시작 시 위 조건을 자동 점검합니다.
- 미충족 시 가이드 메시지를 출력하고 즉시 종료합니다.

## 1) 빈 프로젝트에서 최초 설치 (Bootstrap)
설치 스크립트가 아직 없는 상태에서 아래 한 줄로 시작합니다.

```bat
curl -fsSL <RAW_SETUP_DX_URL> -o setup_dx.py && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite
```

```bat
wget -qO setup_dx.py <RAW_SETUP_DX_URL> && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite
```

## 2) 중앙 레포 기반 설치/동기화
최초 설치:

```bat
python dx_operating_pack\tools\setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite
```

지속 동기화:

```bat
python dx_operating_pack\tools\sync_dx_pack.py --remote-url <CENTRAL_REPO_URL_OR_PATH> --project-root . --mode copy --overwrite
```

## 3) Safe Sync 보호 정책
`sync_dx_pack.py --overwrite` 실행 시에도 아래 파일은 보호됩니다.

- `DEV_LOG.md`
- `PROJECT_STATUS.md`
- `now_spec.md`
- `**/*.local.*`

보호 로직:
1. 보호 파일 사전 백업
2. 업데이트 수행
3. 보호 파일 자동 복원(`finally`)

추가 백업:
- 업데이트 직전 팩 전체 백업 생성:
  - `.dx_cache/backups/pack_<timestamp>/dx_operating_pack`

무결성:
- v2.1 검증에서 SHA256 해시 비교로 보호 파일 복원 동일성이 확인되었습니다.

## 4) 인증 실패(Private Repo) 대응
clone/pull 실패 시 점검:
- SSH: 공개키 등록 후 `git@...` URL 사용
- HTTPS: PAT + credential manager 설정
- 접근 테스트: `git ls-remote <repo-url>`

## 5) 운영 가드레일
1400라인 제한:
- 단일 커밋 변경량이 과하면 가드가 차단합니다.
- 대규모 변경은 원자 단위 분할 커밋을 사용하십시오.

필수 태스크 흐름:

```bat
python tools/task_start_guard.py
python tools/post_task_gate.py
```

권장:

```bat
python tools/check_ai_security.py
```

## 6) AI Agent 시작 규칙
에이전트는 작업 시작 즉시 `MANIFEST_AI.yaml`을 읽어야 합니다.

이유:
- 도구 목적/사용 시점/실행 위치를 즉시 파악
- 잘못된 도구 선택과 불필요한 탐색 감소
- 협업 응답 품질 및 속도 향상

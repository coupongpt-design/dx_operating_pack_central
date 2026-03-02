# AGENT_ONBOARDING

DX Operating Pack v2의 에이전트 운영 매뉴얼입니다.  
이 문서는 "설치 -> 작업 -> 검증 -> 동기화"를 하나의 표준 루프로 통합해, 에이전트가 규칙을 일관되게 적용하도록 설계되었습니다.

## 최종 퀵스타트 명령어
```bat
git init && curl -fsSL <RAW_SETUP_DX_URL> -o setup_dx.py && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite
```

```bat
git init && wget -qO setup_dx.py <RAW_SETUP_DX_URL> && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite
```

## 1) 온보딩 (초기 1회)
1. 저장소 루트에서 필수 환경 확인:
   - `git --version`
   - `git rev-parse --is-inside-work-tree`
2. DX Pack 설치/적용:
   - `python dx_operating_pack/tools/setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`
   - 설치 직후 `tools/check_tool_integrity.py`가 자동 실행되어 루트 `tools/` 위임 상태를 점검합니다.
3. 훅 설치:
   - `python tools/install_git_hooks.py`
4. 규칙/도구 맵 로드:
   - `AGENTS.md`(정본) -> `rules/AGENTS.md`(브리지, 존재 시) -> `.cursorrules` -> `dx_operating_pack/MANIFEST_AI.yaml` 순서로 확인

참고:
- `setup_dx.py`는 시작 시 Git 설치 여부와 대상 루트의 git init 상태를 자동 검사합니다.
- 조건 미충족 시 명확한 오류 메시지를 출력하고 즉시 종료합니다.

## 2) 표준 작업 사이클 (Guardrail Cycle)
1. 시작 게이트:
   - `python tools/task_start_guard.py`
2. 컨텍스트 스냅샷(권장):
   - `python tools/generate_context_snapshot.py --scope all|core|ui`
3. 구현 원칙:
   - 재사용 우선: `reusable/core`, `reusable/ui` 먼저 탐색
   - 원자 단위 변경 유지(대형 변경은 분할)
4. 종료 게이트:
   - `python tools/post_task_gate.py`
   - `python tools/check_ai_security.py`
   - 자동 상신이 필요하면 `python tools/task_finish.py --subject "<msg>" --scope <scope> --auto-push` 사용
5. 커밋 전:
   - 테스트/게이트/문서 동기화 상태 확인 후 커밋
6. 지식 환류:
   - `python tools/push_dx_feedback.py --base HEAD~1 --head HEAD`
   - 중앙 반영 시: `--remote-url <CENTRAL_REPO_URL> --push`
   - 중앙 운영자라면: `python tools/promote_dx_feedback.py --apply`
   - 참고: `capture_lesson_draft.py`는 `logs/ai_sessions/` 최신 JSON/Markdown 로그에서 Decision/Reason/Warning 신호를 추출해 `feedback/LATEST_INSIGHT.yaml`에 반영합니다.

## 3) 동기화/업데이트 운영
권장 명령:
- `python dx_operating_pack/tools/sync_dx_pack.py --remote-url <CENTRAL_REPO_URL_OR_PATH> --project-root . --mode copy --overwrite`

동기화 안전장치:
- Sync 직전 팩 전체를 `.dx_cache/backups/pack_<timestamp>/dx_operating_pack`로 자동 백업
- 로컬 보호 파일은 백업 후 복원:
  - `**/*.local.*`
  - `DEV_LOG.md`
  - `PROJECT_STATUS.md`
  - `now_spec.md`

## 4) Private 레포 인증 실패 대응
원격 clone/pull 실패 시 아래를 점검:
- SSH 방식: 공개키 등록 후 `git@...` URL 사용
- HTTPS 방식: PAT 발급 + credential manager 설정
- 접근 확인: `git ls-remote <repo-url>`

## 5) 제약사항 (필수 준수)
- 추측 금지:
  - 모호한 로직은 `docs/KNOWLEDGE_BASE.md` 확인 후 부족하면 사용자에게 질의
- 반복 실수 방지:
  - `docs/LESSONS_LEARNED.md` 우선 조회
- 보안:
  - `.local.*` 및 민감정보 커밋/외부 공유 금지
  - 공유 시 `*.example.*` 템플릿 사용

## 6) 자가 검증 (설치 직후/대규모 변경 후)
- 검증 A: 규칙 정합
  - 루트 `.cursorrules`와 규칙 소스 정합 확인
- 검증 B: 훅 차단
  - 임시 파일 커밋 시도 시 pre-commit/commit-msg가 차단하는지 확인
- 검증 C: 도구 인식
  - `MANIFEST_AI.yaml`에 있는 도구 1개 이상 실행해 결과 확인

## 7) 부트스트랩 원라인
- `curl -fsSL <RAW_SETUP_DX_URL> -o setup_dx.py && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`
- `wget -qO setup_dx.py <RAW_SETUP_DX_URL> && python setup_dx.py --remote <CENTRAL_REPO_URL_OR_PATH> --target-root . --mode copy --overwrite`

## 8) 완료 선언 기준
아래가 모두 충족되면 첫 작업에 착수합니다.
- setup 실행 여부 확인
- 가드/훅 정상 동작 확인
- 규칙/도구 맵 로드 완료 확인
- Feedback Loop 동작 확인(`feedback/LATEST_INSIGHT.yaml` 생성 확인)

## 9) Sandbox Policy (파괴적 검증 정책)
- `--overwrite`, 강제 동기화, 대량 삭제가 동반되는 검증은 메인 저장소에서 직접 수행하지 않습니다.
- 파괴적 검증은 별도 임시 샌드박스 폴더(예: `D:\\tmp\\dx-test`)에서만 수행합니다.
- 메인 저장소에서는 비파괴 검증(정적 점검/게이트/타깃 테스트)만 수행합니다.

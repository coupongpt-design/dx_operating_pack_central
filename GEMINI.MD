# 에이전트 운영 규칙 (GEMINI.MD)

## 실행 정책

### 항상 실행 (Always Run)
- 이 프로젝트는 **항상 실행 모드**로 운영됩니다.
- 에이전트는 `run_command` 호출 시 **`SafeToAutoRun=true`를 기본으로 설정**합니다.
- 사용자에게 "실행할까요?" 같은 확인을 구하지 않습니다.
- 파일 수정 후 즉시 관련 명령(테스트, 빌드 등)을 자동 실행합니다.
- **예외**: 외부 서비스 push, 패키지 설치, 파일 삭제 등 불가역 작업은 별도 판단.

### 파일 변경 정책
- 파일이 변경되었을 때 "수락할까요?" 등의 확인을 구하지 않습니다.
- 항상 수락(Accept All)으로 간주하고 다음 작업을 즉시 진행합니다.

### 작업 완료 후 대기
- 큰 작업 단위(커밋, 기능 구현 완료 등)가 끝나면 결과를 간략히 알리고 **다음 지시를 기다립니다**.
- 사용자 허락 없이 임의로 다음 백로그 작업을 시작하지 않습니다.

## 커밋 규칙
- 커밋 전 `DEV_LOG.md`, `PROJECT_STATUS.md`, `now_spec.md` 3개 문서를 반드시 업데이트합니다.
- `python tools/task_finish.py --subject "..." --scope ... --confirm-doc-sync` 경로를 표준으로 사용합니다.
- gate 통과 후: `git add` → `git commit -F .git/TASK_COMMIT_TEMPLATE.md`

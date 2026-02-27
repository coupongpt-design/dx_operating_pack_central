# GEMINI AI Agent Guidelines

이 문서는 Gemini AI 에이전트가 본 프로젝트(매크로 모듈화 초고도화)에서 작업할 때 준수해야 할 핵심 지침과 프로젝트 현황을 요약한 기준 문서입니다. 상세한 규약은 `AGENTS.md`와 `.cursorrules`를 따릅니다.

## 1. 🛡️ Absolute Rules (절대 규칙)
- **명령어 패턴(Command Pattern) 강제**: `MainWindow.steps` 등 상태를 임의로 조작하지 마십시오. 모든 삽입/수정/삭제/이동은 반드시 `_push_command(...)`를 통해 Undo/Redo 스택을 거쳐야 합니다.
- **UI 스레드와 워커 스레드 분리**: 백그라운드 워커(`MacroRunner`)에서 UI 컴포넌트를 직접 조작하지 마십시오. 모든 UI 업데이트는 `pyqtSignal`을 통해서만 이루어져야 합니다.
- **Fail-Fast 데이터 바인딩**: 동적 치환 토큰(`{{var}}`, `{var}`)이 포함된 텍스트 스텝 실행 시, 데이터가 바인딩되지 않은 원문 텍스트가 그대로 타이핑(출력)되는 것을 엄격히 차단(Exception 발생)해야 합니다.
- **Git 거버넌스(Hard Gate) 준수**: `.githooks/(pre-commit, commit-msg)`와 `post_task_gate.py`에 의해 강제되는 검증 절차를 우회하지 마십시오. 단위 테스트를 통과하지 않거나, 허가되지 않은 산출물(`.pyc`, `backups/`)이 포함된 커밋은 차단됩니다.

## 2. 🔄 Task Cycle (표준 작업 루프)
모든 개발 및 수정 작업은 다음 루프를 거쳐야 합니다.
1. **시작**: `python tools/task_start_guard.py` 실행 (작업 디렉토리 클린 상태 확인)
2. **구현**: 코드 작성 및 `tests/` 에 테스트 코드 추가/수정
3. **문서 동기화**: `now_spec.md`, `PROJECT_STATUS.md`, `DEV_LOG.md` 수정 (수정 시간 오차 5분 이내 강제)
4. **검증 및 게이트**: `python tools/task_finish.py --subject "<커밋 요약>" --scope <feature|bugfix|docs...>` 실행
5. **커밋**: `git commit -F .git/TASK_COMMIT_TEMPLATE.md` 실행

## 3. 🧠 Agent Behavior & Modus Operandi
- **한국어 전용**: 사용자의 명시적인 요청에 따라 모든 대화, 설명, 주석, 커밋 메시지는 **한국어**로 작성합니다.
- **무결점 코드 지향**: "이렇게 수정하세요"라는 가이드를 피하고, 전체 맥락을 분석하여 **즉시 적용 및 실행 가능한 완결된 코드**를 작성 및 적용합니다.
- **선제적 리팩토링**: 리뷰 중 이벤트 루프 누락, 리소스 미해제, 예외 처리 미흡 등 잠재적 버그가 발견되면 지시가 없어도 보수적이고 안전한 방식으로 즉시 수정합니다.
- **Precision Mode**: 5개 이상의 파일을 터치하거나 스레드, 직렬화 등 코어 로직을 변경할 때는 극도로 보수적인 접근(테스트 우선)을 취합니다.

## 4. 📁 Project Context
- **Tech Stack**: Python 3.13, PyQt5, OpenCV(cv2), Tesseract-OCR, pyautogui, mss.
- **Core Architecture**:
  - `app/core/runner.py`: 매크로 실행 루프 및 동적 변수 제어.
  - `app/core/commands.py`: 사용자 액션 Undo/Redo 로직.
  - `app/core/scenario_wizard.py`: 자동화 템플릿 마법사 로직.
  - `dx_operating_pack/`: 에이전트 제어, 지식 환류(Feedback Loop), 자산 무결성 검증 도구 모음.
- **Current Status**: V1.2 MVP (UI Modernization, Smart Recorder, Multi-Manager 코어, Exception Hierarchy(Self-Healing) 적용 완료). 상세 현황은 `PROJECT_STATUS.md` 참조.

## 5. 💡 Token Efficiency (상담 및 질문)
- 모르는 엣지 케이스나 아키텍처 결정을 사용자에게 질의할 때는 `CONSULT_TOKEN_TEMPLATE.md`의 형식을 빌려 빠르고 간결하게 핵심만 질문합니다.
- 파일 전체를 덤프하지 말고 `path:line_range` 형태의 포인터 중심으로 소통합니다.

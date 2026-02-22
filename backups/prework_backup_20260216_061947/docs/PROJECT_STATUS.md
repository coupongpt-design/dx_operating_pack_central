# 프로젝트 상태

## 코어 모듈
- **MacroRunner**: 스텝 실행(OCR, 분기, 서브스크립트, 휴먼 모드 입력), 콜 스택 및 타겟 창 활성화 관리.
- **ImageProcessor**: OCR 전처리(확대/임계/반전) 및 숫자 추출.
- **HumanMouse**: 베지에/이지ング 마우스 움직임, 클릭/드래그 래핑(failsafe 준수).
- **UndoStack/Commands**: Add/Remove/Edit/Move에 대한 커맨드 패턴과 Undo/Redo.
- **WindowManager**: 창 찾기/활성화/강제 리프레시(1px shake); pywin32 없으면 안전히 무시.

## 완료된 주요 기능 [Completed]
- OCR & 이미지 매칭 + 디버그 오버레이.
- 조건 분기(`jump_if`) 스텝 ID 우선 점프; **고급 조건 빌더**: Jump If UI에 변수 자동완성(OCR_STORE 스캔 + `loop_index`/`loop_count`).
- 서브스크립트(`run_macro`) 지원: 콜 스택, 공유 변수 컨텍스트, 재귀 가드(깊이 5).
- Undo/Redo 완전 연결: `MainWindow` CRUD/이동/복제 모두 `_push_command` + UndoStack, Ctrl+Z/Ctrl+Y.
- 드래그-드롭 재정렬도 `ReorderStepsCommand`로 Undo/Redo 기록.
- 녹화 완료 스텝 추가/브랜치 변환/인라인 이름 변경도 커맨드 패턴 경유로 통일.
- 녹화기 최적화: 거리+시간 필터, 드래그 경로 리샘플링, 메트릭 UI 표시.
- 창 관리: 대상 창 입력 + Find/Fix/Selector UI, 실행 전 자동 포커스/리프레시(창 미발견 시 경고 후 진행).
- QA/헬스 체크: `run_health_check.py`, `auto_inspect.py`, 광범위한 pytest 시나리오.
- E2E 테스트 인프라: 풀 라이프사이클(편집→Undo/Redo→저장→불러오기→실행) 자동 검증 완료.
- 이미지 스텝: `loop_until_hide` 옵션으로 템플릿이 사라질 때까지 반복 클릭 지원, 값 변환 안전성 개선.
- 이미지 매칭 고정밀 프리셋(`match_quality`): 멀티 패스 전처리 + 스케일/회전 조합 검색 + ORB 옵션 UI 추가.
- Settings 탭에서 타겟 창 입력 제거, 툴바 입력으로 단일화.
- comment 스텝 텍스트(`comment`) 저장/로드 보존 경로 반영.
- OCR Check/Jump If에 Scale/Invert 조정 UI 추가.
- file_action/load_data_file/compare/screenshot 경로가 매크로 파일 기준 상대 경로로 해석됨.
- capture_on_fail이 ROI 미설정 시 전체 화면 캡처로 동작.
- OCR Check 텍스트 경로에 `ocr_whitelist`/`ocr_target_height` 옵션이 조건부 적용됨.
- 런타임 시작 실패 복구 보강: `run_macro` 실패 시 UI/최소화 상태 자동 복원.
- 스케줄러 실행 실패 경로 보강: runner 미생성 시 `notify_macro_finished(False)`로 큐 정체 방지.
- 트리거 단독 실행 실패 예외 처리 보강: 오류 로그 후 안전 정리.
- 트리거 시작 로그 노이즈 제어: 기본 숨김, `IMAGEMACRO_TRIGGER_START_LOG=1`로 출력 가능.
- CI 파이프라인 추가: `.github/workflows/ci.yml`에서 `pytest -q` + `run_health_check.py` 자동 실행.
- 기능 검증 테스트 강화:
  - E2E 오케스트레이션 테스트(`tests/test_e2e_runtime_orchestration.py`)
  - 스케줄러 코어 테스트(`tests/test_scheduler_core.py`)
  - 트리거 엔진 코어 테스트(`tests/test_trigger_engine_core.py`)

## 파일 포맷
- 메타데이터가 포함된 JSON(`meta`/`repeat`/`steps`), 레거시 리스트 JSON과 `.macro` 역호환.
- 메타에 타겟 창 제목 저장; 로드 시 UI 자동 반영.

## 현재 단계
- **v1.2 - Stable Core+QA**: 런타임 예외 경로 복구, 코어/E2E 테스트 확장, CI 자동검증 연동 완료.
- 최신 로컬 검증 기준: `231 passed, 1 skipped` + `run_health_check.py = SYSTEM HEALTHY`.

## 알려진 이슈 / 낮은 우선순위
- NotImageDialog UI 리팩터는 안정성 우려로 보류.
- 패키징(.exe) 보류(활발한 개발 모드 유지).
- 버튼 배경 변화 대응(자동 마스크/피처 매칭) 개선은 보류 상태.

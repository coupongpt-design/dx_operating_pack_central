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
- 녹화기 최적화: 거리+시간 필터, 드래그 경로 리샘플링, 메트릭 UI 표시.
- 창 관리: 대상 창 입력 + Find/Fix/Selector UI, 실행 전 자동 포커스/리프레시(창 미발견 시 경고 후 진행).
- QA/헬스 체크: `run_health_check.py`, `auto_inspect.py`, 광범위한 pytest 시나리오.
- E2E 테스트 인프라: 풀 라이프사이클(편집→Undo/Redo→저장→불러오기→실행) 자동 검증 완료.
- 이미지 스텝: `loop_until_hide` 옵션으로 템플릿이 사라질 때까지 반복 클릭 지원, 값 변환 안전성 개선.

## 파일 포맷
- 메타데이터가 포함된 JSON(`meta`/`repeat`/`steps`), 레거시 리스트 JSON과 `.macro` 역호환.
- 메타에 타겟 창 제목 저장; 로드 시 UI 자동 반영.

## 현재 단계
- **v1.1 - Stable Core**: E2E 통합 검증 완료, 다중 클라이언트 기능 확장 준비. 패키징(.exe)은 보류 상태.

## 알려진 이슈 / 낮은 우선순위
- 드래그-드롭 재정렬은 여전히 직접 리스트 조작(Undo 기록 필요).
- NotImageDialog UI 리팩터는 안정성 우려로 보류.
- 패키징(.exe) 보류(활발한 개발 모드 유지).
- 버튼 배경 변화 대응(자동 마스크/피처 매칭) 개선은 보류 상태.

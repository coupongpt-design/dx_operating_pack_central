# 프로젝트 상태

## 코어 모듈
- **MacroRunner**: 스텝 실행(OCR, 분기, 서브스크립트, 휴먼 모드 입력), 콜 스택 및 타겟 창 활성화 관리.
- **ImageProcessor**: OCR 전처리(확대/임계/반전) 및 숫자 추출.
- **HumanMouse**: 베지에/이지ング 마우스 움직임, 클릭/드래그 래핑(failsafe 준수).
- **UndoStack/Commands**: Add/Remove/Edit/Move에 대한 커맨드 패턴과 Undo/Redo.
- **WindowManager**: 창 찾기/활성화/강제 리프레시(1px shake); pywin32 없으면 안전히 무시.
- **SessionManager**: 다중 세션 라운드로빈/일일 리셋 코어(ManagerTab와 연동).

## 완료된 주요 기능 [Completed]
- OCR & 이미지 매칭 + 디버그 오버레이.
- 조건 분기(`jump_if`) 스텝 ID 우선 점프; **고급 조건 빌더**: Jump If UI에 변수 자동완성(OCR_STORE 스캔 + `loop_index`/`loop_count`).
- 서브스크립트(`run_macro`) 지원: 콜 스택, 공유 변수 컨텍스트, 재귀 가드(깊이 5).
- Undo/Redo 완전 연결: `MainWindow` CRUD/이동/복제 모두 `_push_command` + UndoStack, Ctrl+Z/Ctrl+Y.
- 녹화기 최적화: 거리+시간 필터, 드래그 경로 리샘플링, 메트릭 UI 표시.
- 창 관리: 대상 창 입력 + Find/Fix/Selector UI, 실행 전 자동 포커스/리프레시(창 미발견 시 경고 후 진행).
- 시나리오 마법사: 기존 수동 편집과 분리된 별도 버튼/다이얼로그, `추천/전체/검색` 템플릿 선택 + 필수 입력 + 생성 미리보기/검증 + 삽입 위치 선택(선택 다음/끝) 지원. 템플릿 카탈로그 46종(채팅/키보드/마우스/파일/OCR 분기 + 리니지류 실전 템플릿) 운영.
- 사용자 템플릿 관리(B안): 기본 템플릿 읽기 전용 + 팝업 `복제 저장`/`사용자 편집`/`사용자 삭제` 지원. 편집 범위는 제목/요약/태그/기본값으로 제한.
- custom_flow 기반 확장 준비: `scenario_wizard_flow` 코어(validator + step id remap + atomic save) 도입 완료.
- 삭제 Lazy-Check 코어 추가: 참조 스텝 탐색(`find_references_in_blueprint`)과 삭제 시 자동 참조 보정(`delete_step_with_lazy_repair`) 제공.
- QA/헬스 체크: `run_health_check.py`, `auto_inspect.py`, 광범위한 pytest 시나리오.
- E2E 테스트 인프라: 풀 라이프사이클(편집→Undo/Redo→저장→불러오기→실행) 자동 검증 완료.
- 이미지 스텝: `loop_until_hide` 옵션으로 템플릿이 사라질 때까지 반복 클릭 지원, 값 변환 안전성 개선.
- 스케줄러 실패정책 UX 강화: `continue/stop/retry` 정책 + 재시도 옵션(`max_retries`, `retry_delay_ms`) + 실행/재시도/중단 상태 라벨 연동.
- 드래그-드롭 재정렬 Undo/Redo: `sync_order` + `ReorderStepsCommand` 경로 통합 및 회귀 테스트 보강.
- 액션 다이얼로그 안정화: `Cancel` 시 스텝이 저장되던 경로 차단, `NotImageDialog`의 중복 Run Macro UI 그룹 제거.
- 이미지 매칭 확장 보강: `High Quality + Color Match` 조합에서 옵션(`hq_color_bg_robust`) 활성 시 gray/CLAHE/edge fallback 패스를 추가해 배경 변화 대응 강화.
- 투명 PNG 전경 매칭: 알파 마스크 기반 템플릿 매칭/컬러게이트 적용(`alpha_mask_enable`)으로 배경 영향 완화.
- 불투명 PNG 전경 매칭: 알파 없는 템플릿에서도 자동 전경 마스크(`auto_fg_mask_enable`)를 생성해 배경 영향 완화.
- 자동 전경 마스크 튜닝: BG percentile/dynamic scale/min distance를 스텝별로 조절 가능.
- 자동 전경 마스크 프리셋: `Stable/Accurate/Aggressive` 빠른 적용 + 수동 조정 시 `Custom` 자동 전환.
- 자동 전경 프리셋 UX: 프리셋 설명 힌트 + 템플릿 기반 `Suggest` 추천 버튼 제공.
- 자동 전경 추천 가시성: Suggest 결과에 confidence(%)와 근거 지표(std/edge density) 표시.
- 자동 전경 추천 임계값 설정: Suggest 분류 기준(`std/edge low/high`)을 스텝별로 직접 조정하고 저장 가능.
- 실사용 스모크 게이트: `run_smoke_suite.py`(quick/full) + `SMOKE_TEST_CHECKLIST.md`로 자동/수동 점검 절차 표준화.
- 윈도우 셀렉터 회귀 복구: pywin32 미가용 환경에서도 창 목록 열거 폴백(`ctypes`) 지원, 빈 목록 안내/표시 가독성 개선(`[]` 제거).
- 시작 타겟 정책 정리: 앱 시작 시 Target 입력은 항상 빈 값으로 시작(이전 세션 타겟 자동 로드 비활성), 매크로 파일 로드 시 `meta.target_window`는 그대로 UI에 반영.

## 파일 포맷
- 메타데이터가 포함된 JSON(`meta`/`repeat`/`steps`), 레거시 리스트 JSON과 `.macro` 역호환.
- 메타에 타겟 창 제목 저장; 로드 시 UI 자동 반영.

## 현재 단계
- **v1.1 - Stable Core**: E2E 통합 검증 완료, 다중 클라이언트 기능 확장 준비. 패키징(.exe)은 보류 상태.

## 최신 검증 기준
- 전체 테스트: `python -m pytest -q` => `314 passed, 1 skipped`
- 스모크(quick): `python run_smoke_suite.py --quick` => `PASS`
- 스모크(full): `python run_smoke_suite.py` => `PASS` + `SYSTEM HEALTHY`

## 알려진 이슈 / 낮은 우선순위
- NotImageDialog UI 리팩터는 안정성 우려로 보류.
- 패키징(.exe) 보류(활발한 개발 모드 유지).
- 복잡 배경에서의 자동 전경 분리 고도화(알파 없는 템플릿 대상)와 특징점 매칭 튜닝은 추가 개선 여지로 유지.
- `Multi-Manager`는 `Start All`에서 runner 자동 생성/연결을 시도하지만, 스크립트 경로 미지정/로드 실패 세션은 `pending` 상태로 남을 수 있음.

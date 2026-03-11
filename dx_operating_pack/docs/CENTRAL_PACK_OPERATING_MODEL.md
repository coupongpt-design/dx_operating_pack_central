# Central Pack Operating Model

## 목적

여러 프로젝트가 각각 `dx_operating_pack`를 가지고 있을 때, 로컬 수확물과 중앙 PACK을 어떻게 합치고 다시 배포할지에 대한 표준 운영 모델이다.

이 문서의 핵심은 다음 한 줄이다.

- 프로젝트들은 PACK 전체를 직접 합치지 않고, 수확물만 중앙으로 올린 뒤 중앙에서 승격하고 다시 내려받는다.

## 1) 역할 분리

### 중앙 PACK

중앙 PACK은 `single source of truth`다.

여기에는 아래만 남긴다.

- 여러 프로젝트에 재사용 가능한 도구
- 공통 운영 규칙
- 일반화 가능한 QA/버그 루프 문서
- 재사용 가능한 reusable changes
- 중앙에서 승격된 lesson/insight

### 프로젝트 로컬 PACK

각 프로젝트의 `dx_operating_pack`는 로컬 작업본이다.

여기에는 아래가 섞일 수 있다.

- 프로젝트 특화 lesson
- 프로젝트 특화 workaround
- 아직 일반화되지 않은 draft
- 로컬 로그에서 수확한 insight

중요:

- 로컬 PACK은 중앙 PACK의 사본이면서도, 동시에 프로젝트별 실험 구역이다.
- 따라서 로컬 PACK끼리 git merge로 직접 합치지 않는다.

## 2) 기본 운영 흐름

표준 흐름은 아래 4단계다.

1. 각 프로젝트에서 로컬 수확물 생성
2. 수확물을 feedback bundle로 상신
3. 중앙 PACK에서 triage 후 승격
4. 중앙 PACK을 각 프로젝트로 sync

즉,

- upstream은 중앙 PACK 하나
- 각 프로젝트는 consumer이자 feedback producer

## 3) 프로젝트별 수확/상신 규칙

각 프로젝트에서는 아래 흐름으로 운영한다.

1. 작업 완료 후 gate 통과
2. `capture_lesson_draft`가 draft/insight 생성
3. `push_dx_feedback.py`로 outbox bundle 생성
4. 필요 시 중앙 repo `feedback/inbox/<project>/...`로 push

로컬에서 생기는 대표 산출물:

- `dx_operating_pack/docs/LESSONS_LEARNED_DRAFT.md`
- `dx_operating_pack/feedback/LATEST_INSIGHT.yaml`
- `dx_operating_pack/feedback/outbox/...`

이 산출물은 곧바로 중앙 canonical이 아니다.
중앙 승격 전까지는 로컬 project-context가 섞인 draft로 본다.

## 4) 중앙 승격 규칙

중앙 repo에서는 inbox에 모인 번들을 바로 PACK 본체에 섞지 않는다.

반드시 triage 후 승격한다.

승격 순서:

1. bundle 확인
2. project-specific / reusable 분리
3. reusable change 검토
4. lesson/insight를 공통 규칙으로 일반화
5. `promote_dx_feedback.py --apply`로 반영
6. processed 이동

중앙 승격의 목적은 "모든 수확물을 보존"이 아니라 "재사용 가치가 있는 것만 PACK 표준으로 끌어올리기"다.

## 5) 승격 기준

다음 조건을 만족하면 중앙 PACK 승격 후보로 본다.

- 두 개 이상 프로젝트에서 비슷한 문제가 반복됨
- 특정 제품/도메인에 묶이지 않음
- 규칙, 문서, 체크리스트, 도구 형태로 일반화 가능함
- 다른 프로젝트에 넣어도 부작용이 작음

반대로 아래는 로컬에 남기는 편이 맞다.

- 특정 게임/앱/도메인에 강하게 묶인 workaround
- 그 프로젝트 구조를 전제하는 예외 처리
- 아직 검증되지 않은 draft
- 일회성 회고 메모

## 6) 하지 말아야 할 것

다음은 금지에 가깝게 본다.

- 프로젝트 A의 `dx_operating_pack`와 프로젝트 B의 `dx_operating_pack`를 직접 merge
- 로컬 `LATEST_INSIGHT.yaml`을 중앙 정본처럼 취급
- project-specific workaround를 검증 없이 중앙 PACK에 승격
- 중앙 PACK과 로컬 PACK 양쪽에서 같은 파일을 독립적으로 진화시킨 뒤 수동 병합

## 7) 권장 저장 구조

### 각 프로젝트

- `dx_operating_pack/docs/LESSONS_LEARNED_DRAFT.md`
- `dx_operating_pack/feedback/LATEST_INSIGHT.yaml`
- `dx_operating_pack/feedback/outbox/...`

### 중앙 PACK repo

- `feedback/inbox/<project>/...`
- `feedback/processed/...`
- 승격된 PACK 본문 문서/도구/규칙

## 8) 실무 운영 규칙

1. 중앙 PACK만 canonical이다.
2. 프로젝트 로컬 PACK은 overwrite sync를 받아도 되는 작업본으로 본다.
3. 프로젝트 간 학습 공유는 PACK 전체 복사가 아니라 feedback bundle 상신으로 한다.
4. 승격은 중앙에서만 한다.
5. 재배포는 중앙 PACK -> 각 프로젝트 sync 한 방향으로 한다.

## 9) 한 줄 운영 결론

여러 프로젝트의 `dx_operating_pack`를 하나로 합치는 방법은 "PACK끼리 직접 합치기"가 아니라, "각 프로젝트 수확물을 중앙 PACK으로 승격하고 다시 sync하기"다.

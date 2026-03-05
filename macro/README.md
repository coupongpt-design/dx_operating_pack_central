# macro (Stage 2)

이 폴더는 매크로 실행기/시나리오 편집기 영역입니다.
핵심 매크로 구현 파일이 이 폴더로 이관되었습니다.

## 현재 구현 파일
- `macro/main_refactored.py`
- `macro/run_health_check.py`
- `macro/run_runtime_smoke.py`
- `macro/dashboard.py`
- `macro/config.py`
- `macro/utils.py`
- `macro/browser_manager.py`
- `macro/browser_pool.py`
- `macro/data_handler.py`
- `macro/data_analyzer.py`
- `macro/job_tracker.py`
- `macro/notifier.py`
- `macro/pdf_generator.py`
- `macro/version.py`
- `macro/__init__.py`

## 호환성
- 루트 경로 파일(`main_refactored.py`, `run_health_check.py`, `config.py` 등)은 하위 `macro.*` 모듈을 재노출하는 호환 래퍼로 유지됩니다.
- 기존 import/실행 명령을 깨지 않고 점진 이관이 가능하도록 설계되었습니다.

## 연관 테스트(대표)
- `tests/test_main_*.py`
- `tests/test_run_health_check_*.py`

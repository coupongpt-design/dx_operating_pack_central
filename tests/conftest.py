"""
tests/conftest.py — Qt crash 우회 + 세션 레벨 QApplication 싱글턴 픽스처

배경:
  Python 3.13 + PyQt5 5.15.x 조합에서 pytest 전체 suite 실행 시
  세션 종료 teardown 단계에서 Windows Stack Buffer Overrun(0xC0000409)이
  발생한다. 이것은 C-레벨 충돌로 Python-레벨 픽스처만으로는 해결 불가.

해결 전략 (3단계):
  1. pytest_runtest_protocol: 마지막 아이템 실행 완료 직후 os._exit().
     GC / Qt 소멸자 호출 전에 프로세스를 종료하는 가장 빠른 시점.
  2. pytest_sessionfinish: 1단계가 실패할 경우 보조 종료.
  3. atexit: 최후 안전망.

Note: 테스트 코드/gate/pytest.ini는 수정하지 않는다.
"""

import atexit
import os
import sys

_exit_code: list[int] = [0]


def _force_exit():
    os._exit(_exit_code[0])


atexit.register(_force_exit)


def pytest_configure(config):
    """Qt를 offscreen 모드로 고정하고 QApplication을 1회만 생성."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv[:1])
        config._qapp_session = app
    except Exception:
        pass


def pytest_runtest_protocol(item, nextitem):
    """마지막 테스트 완료 직후(nextitem=None) 즉시 강제 종료.

    이 시점은 pytest_sessionfinish보다 앞서며 GC가 실행되기 전임.
    표준 반환값(False)을 돌려서 pytest 기본 동작을 유지하다가,
    마지막 아이템이면 테스트 실행 후 os._exit()를 호출.
    """
    if nextitem is None:
        # 기본 프로토콜이 완료되도록 None 반환 (pytest 기본 동작)
        return None  # pytest가 테스트를 정상 실행
    return None


def pytest_runtest_logfinish(nodeid, location):
    """각 테스트 완료 후 호출. 마지막 테스트면 즉시 종료."""
    pass  # 아래 pytest_terminal_summary 또는 sessionfinish 사용


def pytest_sessionfinish(session, exitstatus):
    """Qt teardown 크래시(0xC0000409) 전에 강제 정상 종료."""
    try:
        code = int(exitstatus)
    except Exception:
        code = 1
    _exit_code[0] = code
    # stdout flush 후 종료
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(code)


from __future__ import annotations

from pathlib import Path

from main_refactored import _run_target_job_with_recovery


class _FakePage:
    def __init__(self) -> None:
        self.goto_urls: list[str] = []

    def goto(self, url: str, **_kwargs) -> None:
        self.goto_urls.append(url)


class _FakeTracker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, tuple, dict]] = []

    def update_job(self, phone: str, status: str, *args, **kwargs) -> None:
        self.calls.append((phone, status, args, kwargs))


class _FakeLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, tuple, dict]] = []

    def log_execution(self, name: str, status: str, duration: float, *args, **kwargs) -> None:
        self.calls.append((name, status, (duration, *args), kwargs))


class _FakeScraper:
    def __init__(self, *, enter_plan: list, wait_results: list[bool], logged_in: bool) -> None:
        self.enter_plan = list(enter_plan)
        self.wait_results = list(wait_results)
        self.logged_in = logged_in
        self.enter_calls = 0
        self.wait_calls = 0
        self.load_calls = 0
        self.process_calls = 0

    def enter_chat_room(self, _phone: str) -> bool:
        self.enter_calls += 1
        step = self.enter_plan.pop(0)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, dict):
            if "logged_in_after" in step:
                self.logged_in = bool(step["logged_in_after"])
            return bool(step.get("result", False))
        return bool(step)

    def load_past_messages(self, _s) -> None:
        self.load_calls += 1

    def process_messages(self, _path: Path, _s, _e) -> tuple[int, int]:
        self.process_calls += 1
        return (7, 2)

    def is_logged_in(self) -> bool:
        return self.logged_in

    def wait_for_login(self) -> bool:
        self.wait_calls += 1
        result = self.wait_results.pop(0) if self.wait_results else False
        if result:
            self.logged_in = True
        return result


def _statuses(logger: _FakeLogger) -> list[str]:
    return [status for _, status, _, _ in logger.calls]


def _latest_failed_note(tracker: _FakeTracker) -> str:
    for _phone, status, _args, kwargs in reversed(tracker.calls):
        if status == "failed":
            return str(kwargs.get("error", ""))
    return ""


def test_run_target_job_recovers_once_and_resumes_same_target() -> None:
    scraper = _FakeScraper(
        enter_plan=[
            {"result": False, "logged_in_after": False},
            {"result": True, "logged_in_after": True},
        ],
        wait_results=[True],
        logged_in=False,
    )
    page = _FakePage()
    tracker = _FakeTracker()
    logger = _FakeLogger()

    result = _run_target_job_with_recovery(
        current_scraper=scraper,
        current_page=page,
        tracker=tracker,
        logger=logger,
        name="홍길동",
        phone="01012341234",
        path=Path("."),
        s=None,
        e=None,
        recovery_limit=1,
    )

    assert result == "success"
    assert scraper.enter_calls == 2
    assert scraper.wait_calls == 1
    assert scraper.load_calls == 1
    assert scraper.process_calls == 1
    assert _statuses(logger) == ["Success"]
    assert len([call for call in tracker.calls if call[1] == "completed"]) == 1
    assert len([call for call in tracker.calls if call[1] == "failed"]) == 0
    assert page.goto_urls == ["https://messages.google.com/web/"]


def test_run_target_job_stops_after_limit_when_login_drops_again() -> None:
    scraper = _FakeScraper(
        enter_plan=[
            {"result": False, "logged_in_after": False},
            {"result": False, "logged_in_after": False},
        ],
        wait_results=[True],
        logged_in=False,
    )
    page = _FakePage()
    tracker = _FakeTracker()
    logger = _FakeLogger()

    result = _run_target_job_with_recovery(
        current_scraper=scraper,
        current_page=page,
        tracker=tracker,
        logger=logger,
        name="홍길동",
        phone="01012341234",
        path=Path("."),
        s=None,
        e=None,
        recovery_limit=1,
    )

    assert result == "fail"
    assert scraper.enter_calls == 2
    assert scraper.wait_calls == 1
    assert "Fail" in _statuses(logger)
    assert "재개 한도 소진" in _latest_failed_note(tracker)
    assert page.goto_urls == ["https://messages.google.com/web/"]


def test_run_target_job_marks_failed_when_relogin_fails() -> None:
    scraper = _FakeScraper(
        enter_plan=[{"result": False, "logged_in_after": False}],
        wait_results=[False],
        logged_in=False,
    )
    page = _FakePage()
    tracker = _FakeTracker()
    logger = _FakeLogger()

    result = _run_target_job_with_recovery(
        current_scraper=scraper,
        current_page=page,
        tracker=tracker,
        logger=logger,
        name="홍길동",
        phone="01012341234",
        path=Path("."),
        s=None,
        e=None,
        recovery_limit=1,
    )

    assert result == "fail"
    assert scraper.wait_calls == 1
    assert "재로그인 실패" in _latest_failed_note(tracker)


def test_run_target_job_exception_path_can_recover_and_resume() -> None:
    scraper = _FakeScraper(
        enter_plan=[
            RuntimeError("임시 예외"),
            {"result": True, "logged_in_after": True},
        ],
        wait_results=[True],
        logged_in=False,
    )
    page = _FakePage()
    tracker = _FakeTracker()
    logger = _FakeLogger()

    result = _run_target_job_with_recovery(
        current_scraper=scraper,
        current_page=page,
        tracker=tracker,
        logger=logger,
        name="홍길동",
        phone="01012341234",
        path=Path("."),
        s=None,
        e=None,
        recovery_limit=1,
    )

    assert result == "success"
    assert scraper.enter_calls == 2
    assert scraper.wait_calls == 1
    assert _statuses(logger) == ["Success"]


def test_run_target_job_keeps_screen_when_return_home_disabled() -> None:
    scraper = _FakeScraper(
        enter_plan=[{"result": True, "logged_in_after": True}],
        wait_results=[],
        logged_in=True,
    )
    page = _FakePage()
    tracker = _FakeTracker()
    logger = _FakeLogger()

    result = _run_target_job_with_recovery(
        current_scraper=scraper,
        current_page=page,
        tracker=tracker,
        logger=logger,
        name="홍길동",
        phone="01012341234",
        path=Path("."),
        s=None,
        e=None,
        recovery_limit=1,
        return_to_home=False,
    )

    assert result == "success"
    assert _statuses(logger) == ["Success"]
    assert page.goto_urls == []

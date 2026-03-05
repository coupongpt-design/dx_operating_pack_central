from __future__ import annotations

from main_refactored import _attempt_same_target_recovery


class _DummyScraper:
    def __init__(self, *, logged_in: bool, relogin_ok: bool) -> None:
        self._logged_in = logged_in
        self._relogin_ok = relogin_ok
        self.wait_calls = 0

    def is_logged_in(self) -> bool:
        return self._logged_in

    def wait_for_login(self) -> bool:
        self.wait_calls += 1
        if self._relogin_ok:
            self._logged_in = True
            return True
        return False


def test_attempt_same_target_recovery_retries_once_on_login_drop() -> None:
    scraper = _DummyScraper(logged_in=False, relogin_ok=True)
    used, should_retry, status = _attempt_same_target_recovery(
        scraper,
        recovery_used=0,
        recovery_limit=1,
        reason="unit",
    )
    assert used == 1
    assert should_retry is True
    assert status == "relogin_success"
    assert scraper.wait_calls == 1


def test_attempt_same_target_recovery_stops_when_limit_reached() -> None:
    scraper = _DummyScraper(logged_in=False, relogin_ok=True)
    used, should_retry, status = _attempt_same_target_recovery(
        scraper,
        recovery_used=1,
        recovery_limit=1,
        reason="unit",
    )
    assert used == 1
    assert should_retry is False
    assert status == "limit_reached"
    assert scraper.wait_calls == 0


def test_attempt_same_target_recovery_reports_relogin_failed() -> None:
    scraper = _DummyScraper(logged_in=False, relogin_ok=False)
    used, should_retry, status = _attempt_same_target_recovery(
        scraper,
        recovery_used=0,
        recovery_limit=1,
        reason="unit",
    )
    assert used == 0
    assert should_retry is False
    assert status == "relogin_failed"
    assert scraper.wait_calls == 1


def test_attempt_same_target_recovery_noop_when_still_logged_in() -> None:
    scraper = _DummyScraper(logged_in=True, relogin_ok=True)
    used, should_retry, status = _attempt_same_target_recovery(
        scraper,
        recovery_used=0,
        recovery_limit=1,
        reason="unit",
    )
    assert used == 0
    assert should_retry is False
    assert status == "still_logged_in"
    assert scraper.wait_calls == 0


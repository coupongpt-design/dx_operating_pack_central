from __future__ import annotations

import run_runtime_smoke as smoke


class _FakeLocator:
    def __init__(self, *, visible: bool = False, raise_on_visible: bool = False) -> None:
        self._visible = visible
        self._raise_on_visible = raise_on_visible

    @property
    def first(self):
        return self

    def is_visible(self) -> bool:
        if self._raise_on_visible:
            raise RuntimeError("locator failure")
        return self._visible


class _FakePage:
    def __init__(self, selector_map: dict[str, object]) -> None:
        self._selector_map = selector_map

    def locator(self, selector: str):
        value = self._selector_map.get(selector, False)
        if value == "error":
            return _FakeLocator(raise_on_visible=True)
        return _FakeLocator(visible=bool(value))


class _FakeShellPage:
    def __init__(self, *, url: str, evaluate_result: bool) -> None:
        self.url = url
        self._evaluate_result = evaluate_result

    def evaluate(self, _script: str) -> bool:
        return self._evaluate_result


def test_classify_state_prioritizes_qr() -> None:
    state = smoke._classify_state({"qr": True, "login_success": True, "start_chat": True})
    assert state == "qr_visible"


def test_collect_visibility_handles_locator_error(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke,
        "_probe_selectors",
        lambda: {"qr": "qr_sel", "login_success": "ok_sel", "start_chat": "chat_sel"},
    )
    page = _FakePage({"qr_sel": "error", "ok_sel": True, "chat_sel": False})
    visible = smoke._collect_visibility(page)
    assert visible == {"qr": False, "login_success": True, "start_chat": False}


def test_has_messages_shell_requires_messages_domain() -> None:
    page = _FakeShellPage(url="https://example.com", evaluate_result=True)
    assert smoke._has_messages_shell(page) is False


def test_has_messages_shell_true_when_dom_marker_exists() -> None:
    page = _FakeShellPage(url="https://messages.google.com/web/", evaluate_result=True)
    assert smoke._has_messages_shell(page) is True


def test_run_smoke_returns_3_when_playwright_missing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(smoke, "_get_sync_playwright", lambda: None)
    code = smoke.run_smoke(timeout_sec=1.0, headless=True)
    assert code == 3
    assert "playwright is not installed" in capsys.readouterr().out


def test_run_smoke_passes_with_shell_loaded_fallback(monkeypatch) -> None:
    class _FakePageForRun:
        url = "https://messages.google.com/web/"

        def goto(self, *_args, **_kwargs) -> None:
            return None

        def wait_for_timeout(self, _ms: int) -> None:
            return None

    class _FakeContext:
        def __init__(self) -> None:
            self._page = _FakePageForRun()

        def new_page(self):
            return self._page

        def close(self) -> None:
            return None

    class _FakeBrowser:
        def new_context(self, **_kwargs):
            return _FakeContext()

        def close(self) -> None:
            return None

    class _FakePlaywright:
        @property
        def chromium(self):
            return self

        def launch(self, **_kwargs):
            return _FakeBrowser()

    class _FakeSyncPlaywrightContext:
        def __enter__(self):
            return _FakePlaywright()

        def __exit__(self, _exc_type, _exc, _tb) -> bool:
            return False

    monkeypatch.setattr(smoke, "_get_sync_playwright", lambda: (lambda: _FakeSyncPlaywrightContext()))
    monkeypatch.setattr(
        smoke,
        "_collect_visibility",
        lambda _page: {"qr": False, "login_success": False, "start_chat": False},
    )
    monkeypatch.setattr(smoke, "_has_messages_shell", lambda _page: True)

    code = smoke.run_smoke(timeout_sec=2.0, headless=True)
    assert code == 0


def test_main_parses_headed_and_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_smoke(*, timeout_sec: float, headless: bool) -> int:
        captured["timeout_sec"] = timeout_sec
        captured["headless"] = headless
        return 0

    monkeypatch.setattr(smoke, "run_smoke", _fake_run_smoke)
    code = smoke.main(["--timeout-sec", "11.5", "--headed"])
    assert code == 0
    assert captured == {"timeout_sec": 11.5, "headless": False}

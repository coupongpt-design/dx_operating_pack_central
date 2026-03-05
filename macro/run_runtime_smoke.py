from __future__ import annotations

import argparse
import sys
import time

from .config import SELECTORS


def _probe_selectors() -> dict[str, str]:
    start_chat_selectors = SELECTORS.get("START_CHAT_BTNS") or []
    return {
        "qr": SELECTORS.get("QR_CODE_INDICATOR", ""),
        "login_success": SELECTORS.get("LOGIN_SUCCESS_INDICATOR", ""),
        "start_chat": start_chat_selectors[0] if start_chat_selectors else "",
    }


def _classify_state(visible: dict[str, bool]) -> str:
    if visible.get("qr", False):
        return "qr_visible"
    if visible.get("login_success", False):
        return "logged_in_ui"
    if visible.get("start_chat", False):
        return "start_chat_visible"
    return "unknown"


def _collect_visibility(page) -> dict[str, bool]:
    visible: dict[str, bool] = {}
    for key, selector in _probe_selectors().items():
        if not selector:
            visible[key] = False
            continue
        try:
            visible[key] = bool(page.locator(selector).first.is_visible())
        except Exception:
            visible[key] = False
    return visible


def _has_messages_shell(page) -> bool:
    try:
        if "messages.google.com" not in str(getattr(page, "url", "")):
            return False
        return bool(
            page.evaluate(
                """
() => {
  const customLoaded = Array.from(document.querySelectorAll("*")).some((el) => {
    const tag = el.tagName.toLowerCase();
    return tag.startsWith("mw-") || tag.startsWith("mws-");
  });
  if (customLoaded) return true;
  const title = String(document.title || "");
  return /message|메시지/i.test(title);
}
"""
            )
        )
    except Exception:
        return False


def _get_sync_playwright():
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except Exception:
        return None


def run_smoke(*, timeout_sec: float, headless: bool) -> int:
    sync_playwright = _get_sync_playwright()
    if sync_playwright is None:
        print("[RuntimeSmoke] FAIL playwright is not installed")
        return 3

    timeout_ms = int(max(1.0, timeout_sec) * 1000)
    print("[RuntimeSmoke] starting browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 850})
        page = context.new_page()
        try:
            print("[RuntimeSmoke] opening Google Messages web...")
            page.goto(
                "https://messages.google.com/web/",
                timeout=timeout_ms,
                wait_until="domcontentloaded",
            )

            deadline = time.time() + timeout_sec
            last_visible = {"qr": False, "login_success": False, "start_chat": False}
            while time.time() < deadline:
                last_visible = _collect_visibility(page)
                state = _classify_state(last_visible)
                if state != "unknown":
                    print(f"[RuntimeSmoke] PASS state={state} url={page.url}")
                    return 0
                if _has_messages_shell(page):
                    print(f"[RuntimeSmoke] PASS state=shell_loaded url={page.url}")
                    return 0
                page.wait_for_timeout(500)

            print(
                "[RuntimeSmoke] FAIL no known UI marker "
                f"(qr/login/start_chat) within {timeout_sec:.1f}s; last={last_visible}"
            )
            return 2
        except Exception as exc:
            print(f"[RuntimeSmoke] FAIL exception: {exc}")
            return 1
        finally:
            context.close()
            browser.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Messages runtime smoke check")
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=25.0,
        help="max wait time for UI markers",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="run with visible browser window",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(list(argv or []))
    return run_smoke(timeout_sec=ns.timeout_sec, headless=not ns.headed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

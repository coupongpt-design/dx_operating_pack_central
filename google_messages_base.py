from __future__ import annotations

import logging
import time

from playwright.sync_api import Page

from config import CONFIG, SELECTORS


class GoogleMessagesBaseMixin:
    page: Page

    def __init__(self, page: Page):
        self.page = page

    def _find_search_input(self):
        for sel in SELECTORS["SEARCH_INPUT"]:
            try:
                locator = self.page.locator(sel).first
                if locator.is_visible():
                    return locator
            except Exception:
                continue
        return None

    def _sanitize_debug_text(self, text: str, limit: int = 200) -> str:
        clean = " ".join(str(text).split())
        if len(clean) > limit:
            return clean[:limit] + "...(truncated)"
        return clean

    def _debug_date_log(self, label: str, **data):
        if not CONFIG.get("DEBUG_DATE_PARSE"):
            return
        cleaned = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, str):
                cleaned[key] = self._sanitize_debug_text(value)
            elif isinstance(value, list):
                cleaned[key] = [self._sanitize_debug_text(v) for v in value if v][:10]
            else:
                cleaned[key] = value
        logging.info("[DATE_DEBUG] %s | %s", label, cleaned)

    def _is_page_closed(self) -> bool:
        try:
            return self.page.is_closed()
        except Exception:
            return True

    def _safe_is_visible(self, selector: str) -> bool:
        if self._is_page_closed():
            return False
        try:
            return self.page.locator(selector).first.is_visible()
        except Exception:
            return False

    def wait_for_dom_stability(self, timeout: int = 5000):
        """DOM 변화가 멈출 때까지 대기"""
        start_time = time.time()
        last_len = 0
        stable_cnt = 0
        while (time.time() - start_time) * 1000 < timeout:
            try:
                curr_len = self.page.evaluate("document.body.innerHTML.length")
                if curr_len == last_len:
                    stable_cnt += 1
                    if stable_cnt >= 3:
                        return True
                else:
                    stable_cnt = 0
                last_len = curr_len
                time.sleep(0.5)
            except Exception as exc:
                logging.debug("DOM 안정화 대기 중단: %s", exc)
                break
        return False

    def scroll_down_slowly(self):
        """천천히 아래로 스크롤 (로딩 유도)"""
        try:
            if self._is_page_closed():
                return
            current_scroll = 0
            while current_scroll <= 5000:
                self.page.mouse.wheel(0, 500)
                self.page.keyboard.press("ArrowDown")
                self.page.keyboard.press("ArrowDown")
                time.sleep(0.5)
                current_scroll += 500
        except Exception as exc:
            logging.debug("스크롤 다운 중 무시 가능한 예외: %s", exc)

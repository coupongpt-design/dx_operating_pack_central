from __future__ import annotations

import logging
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config import CONFIG, SELECTORS


class GoogleMessagesAuthMixin:
    def _has_chat_entry_ui(self) -> bool:
        if self._safe_is_visible(SELECTORS["LOGIN_SUCCESS_INDICATOR"]):
            return True
        return any(self._safe_is_visible(sel) for sel in SELECTORS["START_CHAT_BTNS"])

    def wait_for_login(self):
        """로그인 대기 및 초기화"""
        if self._is_page_closed():
            logging.error("페이지가 닫혀 로그인 대기를 중단합니다.")
            return False
        if "messages.google.com" not in self.page.url:
            logging.info("URL이 올바르지 않아 재이동합니다.")
            try:
                self.page.goto("https://messages.google.com/web/")
            except Exception as exc:
                logging.debug("재이동 중 무시 가능한 예외: %s", exc)

        logging.info("=" * 50)
        logging.info("로그인 상태 확인 중... (UI 안정화 대기)")
        logging.info("=" * 50)

        try:
            start_wait = time.time()
            last_progress_bucket = -1
            while time.time() - start_wait < CONFIG["TIMEOUT_LONG"] / 1000:
                try:
                    found = self.page.evaluate(
                        """() => {
                        const list = document.querySelector('mws-messages-list');
                        const qr = document.querySelector('mw-qr-code, .qr-code-wrapper');
                        const btn = document.querySelector("div[role='button'], a[href='/web/conversations/new']");
                        return list || qr || (btn && btn.innerText.includes('채팅 시작'));
                    }"""
                    )
                    if found:
                        break
                except Exception as exc:
                    logging.debug("로그인 지표 탐색 중 무시 가능한 예외: %s", exc)

                elapsed = int(time.time() - start_wait)
                current_bucket = elapsed // 5
                if current_bucket > last_progress_bucket:
                    logging.info("...로딩 중 (%d초 경과)", elapsed)
                    last_progress_bucket = current_bucket
                time.sleep(2)
        except PlaywrightTimeoutError:
            logging.warning("[WARN] 로딩 시간 초과. 진행을 시도합니다.")

        if self._safe_is_visible(SELECTORS["QR_CODE_INDICATOR"]):
            logging.info("[알림] 화면의 QR 코드를 스캔해주세요.")
            try:
                start_scan_wait = time.time()
                login_success = False
                while time.time() - start_scan_wait < 300:
                    if self._has_chat_entry_ui():
                        login_success = True
                        break
                    time.sleep(1)

                if login_success:
                    logging.info("[OK] QR 스캔 및 로그인 완료!")
                else:
                    logging.error("[FAIL] QR 스캔 시간 초과 (화면 전환 안됨).")
                    return False
            except Exception as e:
                logging.error(f"[FAIL] QR 스캔 대기 중 에러: {e}")
                return False

        if self._has_chat_entry_ui():
            logging.info("[OK] 로그인 감지됨. UI 초기화 대기 중...")
            try:
                self.page.wait_for_selector(
                    SELECTORS["START_CHAT_BTNS"][0], state="visible", timeout=10000
                )
            except PlaywrightTimeoutError:
                logging.debug("시작 채팅 버튼 가시화 대기 타임아웃: 계속 진행합니다.")

            # 로그인 직후 즉시 동작 시 QR 재노출되는 경우를 줄이기 위해
            # 짧은 안정화 윈도우에서 상태를 연속 확인한다.
            stable_hits = 0
            for _ in range(8):
                if self._safe_is_visible(SELECTORS["QR_CODE_INDICATOR"]):
                    stable_hits = 0
                    time.sleep(0.5)
                    continue
                if self._has_chat_entry_ui():
                    stable_hits += 1
                    if stable_hits >= 3:
                        break
                else:
                    stable_hits = 0
                time.sleep(0.5)

            if stable_hits < 3:
                logging.warning("[WARN] 로그인 UI 안정화 확인에 실패했습니다.")
                return False

            logging.info("[START] 브라우저 준비 완료!")
            return True

        return False

    def is_logged_in(self) -> bool:
        """현재 로그인 상태 여부 확인"""
        try:
            if self._is_page_closed():
                return False
            if "messages.google.com" not in self.page.url:
                return False
            if self.page.locator(SELECTORS["QR_CODE_INDICATOR"]).is_visible():
                return False
            if self.page.locator(SELECTORS["LOGIN_SUCCESS_INDICATOR"]).is_visible():
                return True
            # fallback: 시작 채팅 버튼은 보조 지표로만 사용
            if self.page.locator(SELECTORS["START_CHAT_BTNS"][0]).first.is_visible():
                return True
        except Exception:
            pass
        return False

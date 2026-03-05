from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import dateparser
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from macro.config import SELECTORS


class GoogleMessagesChatMixin:
    def _is_chat_opened(self) -> bool:
        """현재 채팅방 진입 여부 확인"""
        if self._is_page_closed():
            return False
        url_ok = "conversations" in self.page.url and "conversations/new" not in self.page.url
        input_visible = False
        try:
            if (
                self._safe_is_visible("textarea")
                or self._safe_is_visible(".input-box")
                or self._safe_is_visible("[contenteditable='true']")
            ):
                input_visible = True
        except Exception as exc:
            logging.debug("채팅방 입력창 가시성 확인 중 예외: %s", exc)
        return url_ok or input_visible

    def _recover_search_input(self, *, allow_navigation: bool):
        """
        채팅 검색 입력창 복구.

        재시도 중에는 불필요한 전체 페이지 이동을 피하고,
        마지막 수단일 때만 conversations/new로 이동한다.
        """
        if self._is_page_closed():
            return None

        input_box = self._find_search_input()
        if input_box:
            return input_box

        for sel in SELECTORS["START_CHAT_BTNS"]:
            if not self._safe_is_visible(sel):
                continue
            try:
                self.page.locator(sel).first.click()
                self.page.wait_for_timeout(600)
            except Exception as exc:
                logging.debug("채팅 시작 버튼 재열기 실패(%s): %s", sel, exc)
                continue
            input_box = self._find_search_input()
            if input_box:
                return input_box

        if not allow_navigation:
            return None

        try:
            self.page.goto("https://messages.google.com/web/conversations/new")
            self.page.wait_for_timeout(1200)
        except Exception as exc:
            logging.debug("conversations/new 이동 복구 실패: %s", exc)
            return None

        if self._safe_is_visible(SELECTORS["QR_CODE_INDICATOR"]):
            logging.warning("채팅방 복구 중 QR 화면 감지됨. 로그인 재확인이 필요합니다.")
            return None
        return self._find_search_input()

    def enter_chat_room(self, phone: str) -> bool:
        """전화번호로 채팅방 진입 (재시도 로직 포함)"""
        try:
            if self._is_page_closed():
                logging.error("페이지가 닫혀 채팅방 진입을 중단합니다.")
                return False

            input_box = self._recover_search_input(allow_navigation=True)
            if not input_box:
                logging.error("❌ 검색 입력창을 찾을 수 없습니다.")
                return False

            for attempt in range(1, 4):
                logging.info(f"   🚪 채팅방 진입 시도 ({attempt}/3)...")
                if self._is_page_closed():
                    logging.error("페이지가 닫혀 채팅방 진입을 중단합니다.")
                    return False

                if self._safe_is_visible(SELECTORS["QR_CODE_INDICATOR"]):
                    logging.warning("재시도 중 QR 화면 감지. 로그인 상태를 재확인합니다.")
                    wait_for_login = getattr(self, "wait_for_login", None)
                    if callable(wait_for_login):
                        if not wait_for_login():
                            logging.error("재로그인 확인 실패로 채팅방 진입을 중단합니다.")
                            return False
                        input_box = self._recover_search_input(allow_navigation=True)
                        if not input_box:
                            logging.error("재로그인 후 검색 입력창 복구 실패.")
                            return False
                    else:
                        logging.error("로그인 복구 메서드가 없어 채팅방 진입을 중단합니다.")
                        return False

                if not input_box or not input_box.is_visible():
                    input_box = self._recover_search_input(allow_navigation=False)
                    if not input_box and attempt == 1:
                        # 첫 회차에만 강한 복구(전체 이동) 허용
                        input_box = self._recover_search_input(allow_navigation=True)
                    if not input_box:
                        logging.warning("검색 입력창 재탐색 실패. 현재 화면에서 재시도합니다.")
                        continue

                input_box.fill("")
                self.page.wait_for_timeout(200)
                input_box.fill(phone)
                self.page.wait_for_timeout(1500)

                # 안정 버전에서 검증된 순서:
                # 1차 ArrowDown+Enter -> 2차 Enter -> 3차 좌표 클릭
                if attempt == 1:
                    input_box.press("ArrowDown")
                    self.page.wait_for_timeout(500)
                    input_box.press("Enter")
                elif attempt == 2:
                    input_box.press("Enter")
                elif attempt == 3:
                    try:
                        box = self.page.locator("[role='listbox']").bounding_box()
                        if box:
                            self.page.mouse.click(box["x"] + 20, box["y"] + 30)
                        else:
                            ib_box = input_box.bounding_box()
                            if ib_box:
                                self.page.mouse.click(
                                    ib_box["x"] + 20,
                                    ib_box["y"] + ib_box["height"] + 20,
                                )
                    except Exception as exc:
                        logging.debug("3차 좌표 기반 클릭 전략 실패: %s", exc)

                self.page.wait_for_timeout(2000)
                if self._is_chat_opened():
                    logging.info("   ✅ 채팅방 입장 성공!")
                    try:
                        self.page.wait_for_selector(
                            SELECTORS["MSG_WRAPPER"], state="visible", timeout=5000
                        )
                    except PlaywrightTimeoutError:
                        logging.debug("메시지 래퍼 가시화 대기 타임아웃: 계속 진행합니다.")
                    return True

                logging.warning(f"   ⚠️ {attempt}차 진입 실패. 재시도...")
                try:
                    # 재시도 전 soft reset: 검색 레이어만 닫고 동일 세션을 유지
                    input_box.press("Escape")
                except Exception:
                    pass
                self.page.wait_for_timeout(700)
                input_box = self._recover_search_input(allow_navigation=False)
                if not input_box and attempt == 1:
                    input_box = self._recover_search_input(allow_navigation=True)

            logging.error(f"❌ {phone} 채팅방 진입 최종 실패.")
            return False
        except Exception as exc:
            logging.error("진입 중 에러: %s", exc)
            return False

    def load_past_messages(self, target_start_date: Optional[datetime]):
        """과거 메시지 로딩 (스크롤 업)"""
        target_str = target_start_date.strftime("%Y-%m-%d") if target_start_date else "제한 없음"
        logging.info(f"📜 과거 내역 로딩 시작... (목표: {target_str})")
        if self._is_page_closed():
            logging.error("페이지가 닫혀 과거 내역 로딩을 중단합니다.")
            return

        msg_list_box = self.page.locator(SELECTORS["MSG_LIST"]).first
        if not msg_list_box.is_visible():
            return

        no_change_count = 0
        prev_msg_count = 0

        for attempt in range(300):
            try:
                curr_msg_count = self.page.locator(SELECTORS["MSG_WRAPPER"]).count()
            except Exception as exc:
                logging.debug("메시지 개수 집계 실패(%d회차): %s", attempt + 1, exc)
                curr_msg_count = 0

            if curr_msg_count > 0 and curr_msg_count == prev_msg_count:
                no_change_count += 1
                if no_change_count >= 5:
                    logging.info("   ✅ 더 이상 로딩 안됨 (Top 도달).")
                    break
            else:
                no_change_count = 0
                prev_msg_count = curr_msg_count

            if target_start_date and attempt % 3 == 0:
                try:
                    first_ts = self.page.locator(SELECTORS["TOMBSTONE_DATE"]).first
                    if first_ts.is_visible():
                        parsed_top_date = dateparser.parse(first_ts.inner_text(), languages=["ko"])
                        if parsed_top_date and parsed_top_date <= target_start_date:
                            logging.info(f"   ✅ 목표 날짜({target_str}) 도달 완료.")
                            break
                except Exception as exc:
                    logging.debug("상단 날짜 체크 실패(%d회차): %s", attempt + 1, exc)

            try:
                msg_list_box.hover()
                self.page.mouse.wheel(0, -5000)
                self.page.wait_for_timeout(1500)
            except Exception as exc:
                logging.debug("스크롤 업 중단(%d회차): %s", attempt + 1, exc)
                break

        self.page.keyboard.press("ArrowDown")

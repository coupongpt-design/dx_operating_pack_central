import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

if PLAYWRIGHT_AVAILABLE:
    from config import SELECTORS
    from google_messages import GoogleMessagesPage


class FakeLocator:
    def __init__(self, visible=False, items=None):
        self._visible = visible
        self._items = items or []

    @property
    def first(self):
        return self

    def is_visible(self):
        return self._visible

    def click(self):
        return None

    def all(self):
        return self._items


class StablePage:
    def __init__(self, values):
        self._values = list(values)

    def evaluate(self, script):
        if not self._values:
            return 0
        return self._values.pop(0)

    def is_closed(self):
        return False


class FakePage:
    def __init__(self, url="https://messages.google.com/web/", visibility_map=None, items=None):
        self.url = url
        self._visibility_map = visibility_map or {}
        self._items = items or []

    def locator(self, selector):
        if PLAYWRIGHT_AVAILABLE and selector == SELECTORS["ALL_MSG_ITEMS"]:
            return FakeLocator(items=self._items)
        return FakeLocator(visible=self._visibility_map.get(selector, False))

    def is_closed(self):
        return False


class _DummyMouse:
    def click(self, x, y):
        return None

    def wheel(self, x, y):
        return None


class _DummyKeyboard:
    def press(self, key):
        return None


class _ChatInputLocator(FakeLocator):
    def __init__(self, page):
        super().__init__(visible=True)
        self._page = page

    def fill(self, text):
        self._page.last_filled = text

    def press(self, key):
        self._page.pressed_keys.append(key)
        if key == "Enter":
            self._page.enter_count += 1
            if self._page.enter_count >= self._page.open_after_enter_count:
                self._page.chat_open = True
                self._page.url = "https://messages.google.com/web/conversations/room-1"

    def bounding_box(self):
        return {"x": 10, "y": 10, "width": 100, "height": 20}


class _ChatListboxLocator(FakeLocator):
    def __init__(self):
        super().__init__(visible=True)

    def bounding_box(self):
        return {"x": 20, "y": 20, "width": 120, "height": 40}


class ChatFlowPage:
    def __init__(self, qr_sequence, open_after_enter_count=2):
        self.url = "https://messages.google.com/web/conversations/new"
        self._qr_sequence = list(qr_sequence)
        self.open_after_enter_count = open_after_enter_count
        self.chat_open = False
        self.enter_count = 0
        self.pressed_keys = []
        self.last_filled = ""
        self.goto_urls = []
        self.mouse = _DummyMouse()
        self.keyboard = _DummyKeyboard()

    def _next_qr_visible(self):
        if self._qr_sequence:
            return self._qr_sequence.pop(0)
        return False

    def locator(self, selector):
        if selector == SELECTORS["QR_CODE_INDICATOR"]:
            return FakeLocator(visible=self._next_qr_visible())
        if selector in SELECTORS["START_CHAT_BTNS"]:
            return FakeLocator(visible=True)
        if selector in SELECTORS["SEARCH_INPUT"]:
            return _ChatInputLocator(self)
        if selector == "[role='listbox']":
            return _ChatListboxLocator()
        if selector == SELECTORS["MSG_WRAPPER"]:
            return FakeLocator(visible=self.chat_open)
        if selector in ("textarea", ".input-box", "[contenteditable='true']"):
            return FakeLocator(visible=self.chat_open)
        return FakeLocator(visible=False)

    def wait_for_timeout(self, ms):
        return None

    def wait_for_selector(self, selector, state="visible", timeout=0):
        return None

    def goto(self, url):
        self.goto_urls.append(url)
        self.url = url

    def is_closed(self):
        return False


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright not installed")
class TestGoogleMessagesMisc(unittest.TestCase):
    def test_wait_for_dom_stability(self):
        page = StablePage([10, 10, 10, 10])
        scraper = GoogleMessagesPage(page)
        with mock.patch("google_messages.time.sleep", return_value=None):
            self.assertTrue(scraper.wait_for_dom_stability(timeout=1000))

    def test_is_chat_opened_by_url(self):
        page = FakePage(url="https://messages.google.com/web/conversations/123")
        scraper = GoogleMessagesPage(page)
        self.assertTrue(scraper._is_chat_opened())

    def test_is_chat_opened_by_input_visibility(self):
        page = FakePage(visibility_map={"textarea": True})
        scraper = GoogleMessagesPage(page)
        self.assertTrue(scraper._is_chat_opened())

    def test_process_messages_empty_returns_zero(self):
        page = FakePage(items=[])
        scraper = GoogleMessagesPage(page)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            GoogleMessagesPage, "scroll_down_slowly", return_value=None
        ), mock.patch.object(GoogleMessagesPage, "wait_for_dom_stability", return_value=None):
            result = scraper.process_messages(Path(tmp), None, None)
        self.assertEqual(result, (0, 0))

    def test_enter_chat_room_retry_avoids_forced_navigation(self):
        page = mock.Mock()
        page.url = "https://messages.google.com/web/conversations/new"
        page.is_closed.return_value = False
        page.wait_for_timeout.return_value = None
        page.wait_for_selector.return_value = None
        page.goto = mock.Mock()

        start_btn = mock.Mock()
        start_btn.first = start_btn
        start_btn.click.return_value = None

        listbox = mock.Mock()
        listbox.bounding_box.return_value = None

        def _locator(selector):
            if selector in SELECTORS["START_CHAT_BTNS"]:
                return start_btn
            if selector == "[role='listbox']":
                return listbox
            dummy = mock.Mock()
            dummy.first = dummy
            return dummy

        page.locator.side_effect = _locator

        input_box = mock.Mock()
        input_box.is_visible.return_value = True

        scraper = GoogleMessagesPage(page)
        with mock.patch.object(
            scraper,
            "_safe_is_visible",
            side_effect=lambda sel: sel == SELECTORS["START_CHAT_BTNS"][0],
        ), mock.patch.object(scraper, "_find_search_input", return_value=input_box), mock.patch.object(
            scraper, "_is_chat_opened", side_effect=[False, True]
        ):
            ok = scraper.enter_chat_room("01012341234")

        self.assertTrue(ok)
        page.goto.assert_not_called()

    def test_enter_chat_room_uses_stable_attempt_order(self):
        page = mock.Mock()
        page.url = "https://messages.google.com/web/conversations/new"
        page.is_closed.return_value = False
        page.wait_for_timeout.return_value = None
        page.wait_for_selector.return_value = None
        page.goto = mock.Mock()

        start_btn = mock.Mock()
        start_btn.first = start_btn
        start_btn.click.return_value = None

        def _locator(selector):
            if selector in SELECTORS["START_CHAT_BTNS"]:
                return start_btn
            dummy = mock.Mock()
            dummy.first = dummy
            return dummy

        page.locator.side_effect = _locator

        input_box = mock.Mock()
        input_box.is_visible.return_value = True

        scraper = GoogleMessagesPage(page)
        with mock.patch.object(
            scraper,
            "_safe_is_visible",
            side_effect=lambda sel: sel == SELECTORS["START_CHAT_BTNS"][0],
        ), mock.patch.object(scraper, "_find_search_input", return_value=input_box), mock.patch.object(
            scraper, "_is_chat_opened", return_value=True
        ):
            ok = scraper.enter_chat_room("01012341234")

        self.assertTrue(ok)
        self.assertGreaterEqual(input_box.press.call_count, 2)
        self.assertEqual(input_box.press.call_args_list[0].args[0], "ArrowDown")
        self.assertEqual(input_box.press.call_args_list[1].args[0], "Enter")

    def test_enter_chat_room_recovers_after_qr_reappears(self):
        page = ChatFlowPage(qr_sequence=[False, True, False, False], open_after_enter_count=2)
        scraper = GoogleMessagesPage(page)

        with mock.patch.object(scraper, "wait_for_login", return_value=True) as wait_login:
            ok = scraper.enter_chat_room("01012341234")

        self.assertTrue(ok)
        wait_login.assert_called_once()
        self.assertEqual(page.goto_urls, [])
        self.assertGreaterEqual(page.enter_count, 2)

    def test_enter_chat_room_stops_when_relogin_fails(self):
        page = ChatFlowPage(qr_sequence=[False, True, True], open_after_enter_count=99)
        scraper = GoogleMessagesPage(page)

        with mock.patch.object(scraper, "wait_for_login", return_value=False) as wait_login:
            ok = scraper.enter_chat_room("01012341234")

        self.assertFalse(ok)
        wait_login.assert_called_once()
        self.assertLessEqual(page.enter_count, 1)

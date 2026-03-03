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

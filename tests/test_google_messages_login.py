import importlib.util
import unittest

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

if PLAYWRIGHT_AVAILABLE:
    from config import SELECTORS
    from google_messages import GoogleMessagesPage


class FakeLocator:
    def __init__(self, visible):
        self._visible = visible

    @property
    def first(self):
        return self

    def is_visible(self):
        return self._visible


class FakePage:
    def __init__(self, visibility_map):
        self.visibility_map = visibility_map

    def locator(self, selector):
        return FakeLocator(self.visibility_map.get(selector, False))

    def is_closed(self):
        return False


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright not installed")
class TestGoogleMessagesLogin(unittest.TestCase):
    def test_is_logged_in_false_when_qr_visible(self):
        page = FakePage({SELECTORS["QR_CODE_INDICATOR"]: True})
        scraper = GoogleMessagesPage(page)
        self.assertFalse(scraper.is_logged_in())

    def test_is_logged_in_true_when_success_indicator_visible(self):
        page = FakePage({SELECTORS["LOGIN_SUCCESS_INDICATOR"]: True})
        scraper = GoogleMessagesPage(page)
        self.assertTrue(scraper.is_logged_in())

    def test_is_logged_in_true_when_start_chat_visible(self):
        visibility = {SELECTORS["START_CHAT_BTNS"][0]: True}
        page = FakePage(visibility)
        scraper = GoogleMessagesPage(page)
        self.assertTrue(scraper.is_logged_in())

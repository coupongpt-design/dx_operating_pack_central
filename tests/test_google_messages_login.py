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
    def __init__(self, visibility_map, url="https://messages.google.com/web/"):
        self.visibility_map = visibility_map
        self.url = url

    def locator(self, selector):
        return FakeLocator(self.visibility_map.get(selector, False))

    def is_closed(self):
        return False

    def evaluate(self, script):
        return True

    def wait_for_selector(self, selector, state="visible", timeout=0):
        return None

    def goto(self, url):
        self.url = url


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

    def test_is_logged_in_false_when_not_messages_domain(self):
        page = FakePage({SELECTORS["LOGIN_SUCCESS_INDICATOR"]: True}, url="https://example.com/")
        scraper = GoogleMessagesPage(page)
        self.assertFalse(scraper.is_logged_in())

    def test_wait_for_login_succeeds_with_stable_ui(self):
        page = FakePage(
            {
                SELECTORS["QR_CODE_INDICATOR"]: False,
                SELECTORS["LOGIN_SUCCESS_INDICATOR"]: True,
                SELECTORS["START_CHAT_BTNS"][0]: True,
            }
        )
        scraper = GoogleMessagesPage(page)
        with unittest.mock.patch("google_messages_auth.time.sleep", return_value=None):
            self.assertTrue(scraper.wait_for_login())

    def test_wait_for_login_fails_when_qr_flickers(self):
        page = FakePage(
            {
                SELECTORS["QR_CODE_INDICATOR"]: False,
                SELECTORS["LOGIN_SUCCESS_INDICATOR"]: True,
            }
        )
        scraper = GoogleMessagesPage(page)

        counter = {"qr": 0}

        def _safe_is_visible(selector):
            if selector == SELECTORS["QR_CODE_INDICATOR"]:
                counter["qr"] += 1
                return counter["qr"] % 2 == 0
            if selector == SELECTORS["LOGIN_SUCCESS_INDICATOR"]:
                return True
            return False

        with unittest.mock.patch.object(
            scraper, "_safe_is_visible", side_effect=_safe_is_visible
        ), unittest.mock.patch.object(scraper, "_has_chat_entry_ui", return_value=True), unittest.mock.patch(
            "google_messages_auth.time.sleep", return_value=None
        ):
            self.assertFalse(scraper.wait_for_login())

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config import CONFIG

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

if PLAYWRIGHT_AVAILABLE:
    from browser_manager import BrowserManager


class ConfigOverride:
    def __init__(self, **updates):
        self.updates = updates
        self.originals = {}

    def __enter__(self):
        for key, value in self.updates.items():
            self.originals[key] = CONFIG.get(key)
            CONFIG[key] = value
        return self

    def __exit__(self, exc_type, exc, tb):
        for key, value in self.originals.items():
            CONFIG[key] = value


class FakePage:
    pass


class FakeContext:
    def __init__(self, pages=None):
        self.pages = pages or []
        self.closed = False

    def new_page(self):
        page = FakePage()
        self.pages.append(page)
        return page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, context):
        self.context = context
        self.calls = []

    def launch_persistent_context(self, **kwargs):
        self.calls.append(kwargs)
        return self.context


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium
        self.stopped = False

    def stop(self):
        self.stopped = True


class FakeSyncPlaywright:
    def __init__(self, playwright):
        self._playwright = playwright

    def start(self):
        return self._playwright


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright not installed")
class TestBrowserManagerStartStop(unittest.TestCase):
    def test_start_returns_page_and_stop_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "profile"
            base_dir.mkdir()

            context = FakeContext(pages=[FakePage()])
            chromium = FakeChromium(context)
            playwright = FakePlaywright(chromium)
            sync = FakeSyncPlaywright(playwright)

            with ConfigOverride(USER_DATA_DIR=base_dir), mock.patch(
                "browser_manager.sync_playwright", return_value=sync
            ):
                manager = BrowserManager()
                page = manager.start()

                self.assertIs(page, context.pages[0])
                self.assertFalse(context.closed)

                manager.stop()
                self.assertTrue(context.closed)
                self.assertTrue(playwright.stopped)

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config import CONFIG

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

if PLAYWRIGHT_AVAILABLE:
    from browser_pool import BrowserPool


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
    def __init__(self):
        self.pages = []
        self.closed = False

    def new_page(self):
        page = FakePage()
        self.pages.append(page)
        return page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self):
        self.calls = []
        self.contexts = []

    def launch_persistent_context(self, **kwargs):
        self.calls.append(kwargs)
        context = FakeContext()
        self.contexts.append(context)
        return context


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
class TestBrowserPoolStartStop(unittest.TestCase):
    def test_start_creates_contexts_and_stop_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = tmp_path / "profile"
            base_dir.mkdir()
            (base_dir / "State").write_text("x", encoding="utf-8")

            chromium = FakeChromium()
            playwright = FakePlaywright(chromium)
            sync = FakeSyncPlaywright(playwright)

            with ConfigOverride(USER_DATA_DIR=base_dir):
                pool = BrowserPool(pool_size=2)
                with mock.patch("browser_pool.sync_playwright", return_value=sync), mock.patch.object(
                    BrowserPool, "_ensure_base_login", return_value=True
                ), mock.patch.object(
                    BrowserPool,
                    "_get_pool_profile_dir",
                    side_effect=lambda index: tmp_path / f"pool_{index}",
                ):
                    ok = pool.start()

                self.assertTrue(ok)
                self.assertEqual(len(pool.contexts), 2)
                self.assertEqual(chromium.calls[0].get("headless"), False)
                self.assertEqual(chromium.calls[1].get("headless"), True)

                pool.stop()
                self.assertTrue(playwright.stopped)
                self.assertTrue(all(ctx.closed for ctx in chromium.contexts))

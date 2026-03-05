import importlib.util
import tempfile
import unittest
from pathlib import Path

from macro.config import CONFIG

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

if PLAYWRIGHT_AVAILABLE:
    from macro.browser_manager import BrowserManager


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


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright not installed")
class TestBrowserManagerCleanup(unittest.TestCase):
    def test_cleanup_profile_removes_pool_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "profile"
            pool_dir = Path(tmp) / "profile_1"
            other_dir = Path(tmp) / "profile_backup"
            base_dir.mkdir()
            pool_dir.mkdir()
            other_dir.mkdir()

            with ConfigOverride(USER_DATA_DIR=base_dir):
                mgr = BrowserManager()
                mgr.cleanup_profile()

            self.assertFalse(base_dir.exists())
            self.assertFalse(pool_dir.exists())
            self.assertTrue(other_dir.exists())

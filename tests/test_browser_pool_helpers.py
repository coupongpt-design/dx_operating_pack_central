import importlib.util
import tempfile
import unittest
from pathlib import Path

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright not installed")
class TestBrowserPoolHelpers(unittest.TestCase):
    def test_clone_profile_removes_locks(self):
        from macro.browser_pool import BrowserPool

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src_profile"
            dst = tmp_path / "dst_profile"
            src.mkdir()
            (src / "State").write_text("x", encoding="utf-8")
            (src / "SingletonLock").write_text("lock", encoding="utf-8")

            pool = BrowserPool(pool_size=2)
            pool._clone_profile(src, dst)

            self.assertTrue((dst / "State").exists())
            self.assertFalse((dst / "SingletonLock").exists())

    def test_get_pool_profile_dir_name(self):
        from macro.browser_pool import BrowserPool

        pool = BrowserPool(pool_size=2)
        path = pool._get_pool_profile_dir(1)
        self.assertTrue(path.name.startswith(pool.pool_profile_prefix))

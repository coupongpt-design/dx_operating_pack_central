import shutil
import tempfile
import time
import unittest
from pathlib import Path

from macro.job_tracker import JobTracker


class TestJobTracker(unittest.TestCase):
    def test_job_lifecycle(self):
        tmp = tempfile.mkdtemp()
        try:
            db_path = Path(tmp) / "job_tracker.db"
            tracker = JobTracker(db_path=db_path)

            tracker.start_job("Alice", "0101234")
            self.assertEqual(tracker.get_job_status("0101234"), "processing")

            tracker.update_job("0101234", "completed", msg_count=5, img_count=2, duration=1.2)
            self.assertEqual(tracker.get_job_status("0101234"), "completed")

            stats = tracker.get_statistics()
            self.assertEqual(stats["completed"], 1)
            self.assertEqual(stats["total_messages"], 5)

            deleted = tracker.delete_job("0101234")
            self.assertTrue(deleted)
            self.assertIsNone(tracker.get_job_status("0101234"))
        finally:
            try:
                del tracker
            except Exception:
                pass
            time.sleep(0.1)
            shutil.rmtree(tmp, ignore_errors=True)

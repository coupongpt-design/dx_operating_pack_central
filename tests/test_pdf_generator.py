import importlib.util
import tempfile
import unittest
from pathlib import Path

REPORTLAB_AVAILABLE = importlib.util.find_spec("reportlab") is not None

if REPORTLAB_AVAILABLE:
    from pdf_generator import create_summary_report


@unittest.skipUnless(REPORTLAB_AVAILABLE, "reportlab not installed")
class TestPdfGenerator(unittest.TestCase):
    def test_create_summary_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = {"total_customers": 1, "total_messages": 2, "total_attachments": 0, "avg_messages_per_customer": 2}
            keywords = {"예약": 1}
            customers = [{"name": "A_010", "total_messages": 2, "my_messages": 1, "attachments": 0}]

            pdf_path = create_summary_report(out_dir, summary, keywords, customers)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 0)

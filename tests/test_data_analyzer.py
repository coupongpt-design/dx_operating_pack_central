import importlib.util
import tempfile
import unittest
from pathlib import Path

from macro.config import CONFIG

PANDAS_AVAILABLE = importlib.util.find_spec("pandas") is not None

if PANDAS_AVAILABLE:
    import pandas as pd
    from macro.data_analyzer import DataAnalyzer


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


@unittest.skipUnless(PANDAS_AVAILABLE, "pandas not installed")
class TestDataAnalyzer(unittest.TestCase):
    def test_analysis_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            customer_a = base_dir / "A_010"
            customer_b = base_dir / "B_011"
            customer_a.mkdir()
            customer_b.mkdir()

            rows_a = [
                {"날짜": "2024-01-01 10:00", "보낸 사람": "나", "내용": "예약 확인", "첨부파일": "x"},
                {"날짜": "2024-01-01 11:00", "보낸 사람": "상대방", "내용": "취소 문의", "첨부파일": ""},
            ]
            rows_b = [
                {"날짜": "2024-01-02 12:00", "보낸 사람": "나", "내용": "안내", "첨부파일": ""},
            ]

            pd.DataFrame(rows_a).to_excel(customer_a / "chat_log.xlsx", index=False)
            pd.DataFrame(rows_b).to_excel(customer_b / "chat_log.xlsx", index=False)

            with ConfigOverride(BASE_DOWNLOAD_DIR=base_dir, HIGHLIGHT_KEYWORDS=["예약", "취소"]):
                analyzer = DataAnalyzer(base_dir=base_dir)
                files = analyzer.get_all_chat_files()
                summary = analyzer.get_summary_statistics()
                keywords = analyzer.analyze_keywords()
                customers = analyzer.analyze_customers()
                timeline = analyzer.analyze_timeline()

            self.assertEqual(len(files), 2)
            self.assertEqual(summary["total_customers"], 2)
            self.assertEqual(summary["total_messages"], 3)
            self.assertIn("예약", keywords)
            self.assertIn("취소", keywords)
            self.assertGreaterEqual(len(customers), 1)
            self.assertEqual(len(timeline), 24)

import csv
import logging
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from macro.config import CONFIG
from macro.utils import ExecutionLogger, parse_date_smart, setup_logging


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


class TestParseDateSmart(unittest.TestCase):
    def test_parse_blank_returns_none(self):
        self.assertIsNone(parse_date_smart(""))
        self.assertIsNone(parse_date_smart(None))

    def test_parse_date_string(self):
        dt = parse_date_smart("2024-01-02")
        self.assertIsInstance(dt, datetime)
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 2)

    def test_parse_end_date_sets_end_of_day(self):
        dt = parse_date_smart("2024-01-02", is_end_date=True)
        self.assertEqual(dt.hour, 23)
        self.assertEqual(dt.minute, 59)
        self.assertEqual(dt.second, 59)


class TestExecutionLogger(unittest.TestCase):
    def test_execution_logger_creates_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            with ConfigOverride(LOG_DIR=log_dir):
                logger = ExecutionLogger()
                self.assertTrue(logger.csv_path.exists())

                logger.log_execution("Alice", "Success", 1.5, 2, 3, note="ok")
                with open(logger.csv_path, newline="", encoding="utf-8-sig") as f:
                    rows = list(csv.reader(f))

                self.assertGreaterEqual(len(rows), 2)
                self.assertIn("Alice", rows[-1])


class TestSetupLogging(unittest.TestCase):
    def test_setup_logging_creates_log_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            log_file = log_dir / "scraper.log"
            with ConfigOverride(LOG_DIR=log_dir, LOG_FILE=str(log_file)):
                setup_logging()
                logging.info("test log")
                self.assertTrue(log_dir.exists())
                root_logger = logging.getLogger()
                for handler in list(root_logger.handlers):
                    handler.close()
                    root_logger.removeHandler(handler)
                logging.shutdown()

import tempfile
import unittest
from pathlib import Path

from macro.config import CONFIG
from macro.utils import ExecutionLogger


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


class FakeTracing:
    def __init__(self):
        self.started = False
        self.stopped_path = None

    def start(self, screenshots=True, snapshots=True, sources=True):
        self.started = True

    def stop(self, path):
        self.stopped_path = path


class FakeContext:
    def __init__(self):
        self.tracing = FakeTracing()


class TestExecutionLoggerTracing(unittest.TestCase):
    def test_start_and_stop_trace_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            with ConfigOverride(LOG_DIR=log_dir, USE_BLACKBOX=True):
                logger = ExecutionLogger()
                ctx = FakeContext()

                logger.start_trace(ctx)
                self.assertTrue(ctx.tracing.started)

                logger.stop_trace(ctx, "job1", is_error=True)
                self.assertIsNotNone(ctx.tracing.stopped_path)
                self.assertIn("ERROR_job1_", Path(ctx.tracing.stopped_path).name)

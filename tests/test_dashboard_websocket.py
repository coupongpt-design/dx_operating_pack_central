import importlib.util
import logging
import unittest
from unittest import mock

FLASK_AVAILABLE = (
    importlib.util.find_spec("flask") is not None
    and importlib.util.find_spec("flask_socketio") is not None
)

if FLASK_AVAILABLE:
    import macro.dashboard as dashboard


@unittest.skipUnless(FLASK_AVAILABLE, "flask not installed")
class TestDashboardWebsocket(unittest.TestCase):
    def tearDown(self):
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            if isinstance(handler, dashboard.WebSocketLogHandler):
                root_logger.removeHandler(handler)

    def test_update_progress_emits(self):
        with mock.patch.object(dashboard.socketio, "emit") as emit_mock:
            dashboard.update_progress(1, 4, "Alice")
            self.assertEqual(dashboard.current_progress["percentage"], 25)
            emit_mock.assert_called_with("progress_update", dashboard.current_progress)

    def test_handle_connect_emits(self):
        with mock.patch("macro.dashboard.emit") as emit_mock:
            dashboard.handle_connect()
            emit_mock.assert_called_with("connection_response", {"data": "Connected to dashboard"})

    def test_handle_progress_request_emits(self):
        dashboard.current_progress = {"current": 1, "total": 2, "customer_name": "A", "percentage": 50}
        with mock.patch("macro.dashboard.emit") as emit_mock:
            dashboard.handle_progress_request()
            emit_mock.assert_called_with("progress_update", dashboard.current_progress)

    def test_setup_websocket_logging_wires_handler(self):
        root_logger = logging.getLogger()
        original_level = root_logger.level
        root_logger.setLevel(logging.INFO)
        try:
            with mock.patch.object(dashboard.socketio, "emit") as emit_mock:
                dashboard.setup_websocket_logging()
                logging.getLogger().info("hello")
                handlers = [h for h in root_logger.handlers if isinstance(h, dashboard.WebSocketLogHandler)]
                self.assertTrue(handlers)
                self.assertTrue(emit_mock.called)
        finally:
            root_logger.setLevel(original_level)

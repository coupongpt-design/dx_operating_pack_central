import unittest
from unittest import mock

from macro.config import CONFIG
from macro.notifier import Notifier


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


class FakeSMTP:
    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.logged_in = False
        self.sent = False

    def starttls(self):
        return None

    def login(self, username, password):
        self.logged_in = True
        return None

    def send_message(self, msg):
        self.sent = True
        return None

    def quit(self):
        return None


class TestNotifier(unittest.TestCase):
    def test_send_email_success(self):
        notif_cfg = {
            "enabled": True,
            "email": {
                "enabled": True,
                "smtp_server": "smtp.test",
                "smtp_port": 587,
                "username": "user@test",
                "password": "pass",
                "from": "from@test",
                "to": "to@test",
            },
            "slack_webhook": ""
        }
        with ConfigOverride(NOTIFICATION=notif_cfg), mock.patch("smtplib.SMTP", FakeSMTP):
            notifier = Notifier()
            ok = notifier.send_email("subject", "body")
            self.assertTrue(ok)

    def test_send_slack_success(self):
        notif_cfg = {
            "enabled": True,
            "email": {"enabled": False},
            "slack_webhook": "https://hooks.slack.test/services/xxx"
        }
        mock_response = mock.Mock()
        mock_response.status_code = 200

        with ConfigOverride(NOTIFICATION=notif_cfg), mock.patch("requests.post", return_value=mock_response):
            notifier = Notifier()
            ok = notifier.send_slack("hello", status="info")
            self.assertTrue(ok)

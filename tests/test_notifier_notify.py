import unittest
from unittest import mock

from config import CONFIG
from notifier import Notifier


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


class TestNotifierNotify(unittest.TestCase):
    def test_notify_completion_calls_channels(self):
        notif_cfg = {
            "enabled": True,
            "email": {"enabled": True},
            "slack_webhook": "https://hooks.slack.test/services/xxx",
        }
        with ConfigOverride(NOTIFICATION=notif_cfg):
            notifier = Notifier()
            with mock.patch.object(notifier, "send_email", return_value=True) as email_mock, mock.patch.object(
                notifier, "send_slack", return_value=True
            ) as slack_mock:
                notifier.notify_completion(10, 9, 1, 2.5)

            self.assertTrue(email_mock.called)
            self.assertTrue(slack_mock.called)

    def test_notify_error_calls_channels(self):
        notif_cfg = {
            "enabled": True,
            "email": {"enabled": True},
            "slack_webhook": "https://hooks.slack.test/services/xxx",
        }
        with ConfigOverride(NOTIFICATION=notif_cfg):
            notifier = Notifier()
            with mock.patch.object(notifier, "send_email", return_value=True) as email_mock, mock.patch.object(
                notifier, "send_slack", return_value=True
            ) as slack_mock:
                notifier.notify_error("Alice", "boom")

            self.assertTrue(email_mock.called)
            self.assertTrue(slack_mock.called)

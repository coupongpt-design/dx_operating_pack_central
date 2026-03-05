from __future__ import annotations

import google_messages
from google_messages import GoogleMessagesPage
from google_messages.google_messages_auth import GoogleMessagesAuthMixin
from google_messages.google_messages_base import GoogleMessagesBaseMixin
from google_messages.google_messages_chat import GoogleMessagesChatMixin
from google_messages.google_messages_processing import GoogleMessagesProcessingMixin


def test_facade_composes_expected_mixins() -> None:
    assert issubclass(GoogleMessagesPage, GoogleMessagesBaseMixin)
    assert issubclass(GoogleMessagesPage, GoogleMessagesAuthMixin)
    assert issubclass(GoogleMessagesPage, GoogleMessagesChatMixin)
    assert issubclass(GoogleMessagesPage, GoogleMessagesProcessingMixin)


def test_facade_exposes_core_workflow_methods() -> None:
    for method_name in (
        "wait_for_login",
        "enter_chat_room",
        "load_past_messages",
        "process_messages",
    ):
        assert hasattr(GoogleMessagesPage, method_name)


def test_module_keeps_time_symbol_for_patch_compat() -> None:
    assert hasattr(google_messages, "time")

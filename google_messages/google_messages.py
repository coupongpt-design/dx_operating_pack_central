from __future__ import annotations

import time

from .google_messages_auth import GoogleMessagesAuthMixin
from .google_messages_base import GoogleMessagesBaseMixin
from .google_messages_chat import GoogleMessagesChatMixin
from .google_messages_processing import GoogleMessagesProcessingMixin


class GoogleMessagesPage(
    GoogleMessagesBaseMixin,
    GoogleMessagesAuthMixin,
    GoogleMessagesChatMixin,
    GoogleMessagesProcessingMixin,
):
    """구현을 기능별 믹스인으로 분리한 파사드 클래스."""

    pass

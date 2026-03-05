# google_messages (Stage 2)

이 폴더는 Google Messages 자동화 기능 영역입니다.
이제 실제 구현 파일이 이 폴더로 이관되었습니다.

## 현재 구현 파일
- `google_messages/google_messages.py`
- `google_messages/google_messages_base.py`
- `google_messages/google_messages_auth.py`
- `google_messages/google_messages_chat.py`
- `google_messages/google_messages_processing.py`
- `google_messages/__init__.py`

## 호환성
- 기존 import 경로 `from google_messages import GoogleMessagesPage` 유지.
- 루트 `google_messages_auth.py`, `google_messages_base.py`, `google_messages_chat.py`, `google_messages_processing.py`는 하위 패키지를 재노출하는 호환 래퍼입니다.

## 연관 테스트(대표)
- `tests/test_google_messages_*.py`

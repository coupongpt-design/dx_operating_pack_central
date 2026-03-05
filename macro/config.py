import os
from pathlib import Path

# ==========================================
# [설정]
# ==========================================
CONFIG = {
    "EXCEL_FILE": "targets.xlsm",
    "BASE_DOWNLOAD_DIR": Path("./customer_data"),
    "USER_DATA_DIR": Path("./playwright_profile"),
    "LOG_DIR": Path("./system_logs"),
    "SCROLL_COUNT": 5,
    "LOG_FILE": "scraper.log",
    "VIEWPORT": {"width": 1280, "height": 850},
    "USE_BLACKBOX": False,
    "INSPECT_BUTTONS": False,
    "DEBUG_DATE_PARSE": False,
    "TIMEOUT_DEFAULT": 5000,
    "TIMEOUT_LONG": 60000,
    "BLOB_CHUNK_SIZE": 1024 * 1024,
    "HIGHLIGHT_KEYWORDS": ["참석", "불참", "입금", "영수증", "트윈", "더블", "취소", "환불", "예약"],
    "BROWSER_POOL_SIZE": 1,  # 안정성 우선 기본값 (필요 시 2 이상으로 조정)
    "NOTIFICATION": {  # 알림 설정
        "enabled": False,  # True로 변경 시 알림 활성화
        "email": {
            "enabled": False,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "your_email@gmail.com",
            "password": "your_app_password",
            "from": "your_email@gmail.com",
            "to": "recipient@example.com"
        },
        "slack_webhook": ""  # Slack Webhook URL
    }
}

SELECTORS = {
    "START_CHAT_BTNS": [
        "a[href='/web/conversations/new']",
        "div[role='button']:has-text('채팅 시작')",
        ".fab-link",
        "a[aria-label='채팅 시작']"
    ],
    "LOGIN_SUCCESS_INDICATOR": "mws-messages-list",
    "QR_CODE_INDICATOR": "mw-qr-code, .qr-code-wrapper",
    "SEARCH_INPUT": ["input[role='combobox']", "input[type='text']"],
    "MSG_LIST": "mws-messages-list",
    "MSG_WRAPPER": "mws-message-wrapper",
    "ALL_MSG_ITEMS": "mws-tombstone-message-wrapper, mws-message-wrapper",
    "TOMBSTONE_DATE": ".tombstone-timestamp",
    "MSG_ARIA_TARGET": "mws-text-message-part",
    "TIMESTAMP_VISIBLE": ".timestamp",
    "ABS_TIMESTAMP": "mws-absolute-timestamp",
    "MSG_INPUT_BOX": "mws-message-compose-input, textarea[aria-label*='문자'], .input-box"
}

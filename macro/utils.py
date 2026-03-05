import logging
import csv
import time
import sys
import pandas as pd
import dateparser
from datetime import datetime
from typing import Optional, Any
from pathlib import Path
from .config import CONFIG

class SafeStreamHandler(logging.StreamHandler):
    """Console-safe handler to avoid UnicodeEncodeError on Windows cp949."""
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            msg = self.format(record)
            safe_msg = msg.encode("ascii", "backslashreplace").decode("ascii")
            try:
                self.stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)

def setup_logging():
    """로깅 설정 초기화"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass

    CONFIG["LOG_DIR"].mkdir(exist_ok=True)
    
    # UTF-8 강제로 이모지 등 특수문자 처리
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(CONFIG["LOG_FILE"], encoding="utf-8"),
            SafeStreamHandler(stream=sys.stdout)
        ],
        force=True  # 기존 핸들러 강제 재설정
    )

def parse_date_smart(date_val: Any, is_end_date: bool = False) -> Optional[datetime]:
    """날짜 문자열을 스마트하게 파싱"""
    if pd.isna(date_val) or str(date_val).strip() == "":
        return None
    
    dt = date_val if isinstance(date_val, (pd.Timestamp, datetime)) else dateparser.parse(str(date_val))
    
    if dt and is_end_date:
        return dt.replace(hour=23, minute=59, second=59)
    return dt

class ExecutionLogger:
    """실행 로그 및 블랙박스 트레이싱 관리"""
    def __init__(self):
        self.log_dir = CONFIG["LOG_DIR"]
        self.log_dir.mkdir(exist_ok=True)
        self.trace_dir = self.log_dir / "traces"
        self.trace_dir.mkdir(exist_ok=True)
        self.csv_path = self.log_dir / "execution_log.csv"
        
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["타임스탬프", "대상", "상태", "소요시간(초)", "메세지수", "이미지수", "비고"])

    def start_trace(self, context):
        if not CONFIG.get("USE_BLACKBOX", False): return
        try:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        except Exception as e:
            logging.warning(f"Trace start failed: {e}")

    def stop_trace(self, context, name, is_error=False):
        if not CONFIG.get("USE_BLACKBOX", False): return
        try:
            status = "ERROR" if is_error else "OK"
            trace_path = self.trace_dir / f"{status}_{name}_{int(time.time())}.zip"
            context.tracing.stop(path=str(trace_path))
            if is_error:
                logging.warning(f"📸 [블랙박스] 에러 녹화 저장됨: {trace_path}")
        except Exception as e:
            logging.warning(f"Trace stop failed: {e}")

    def log_execution(self, name, status, duration, msg_count=0, img_count=0, note=""):
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    name, status, f"{duration:.2f}", msg_count, img_count, note
                ])
        except Exception as e:
            logging.error(f"Execution log failed: {e}")

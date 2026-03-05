import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from config import CONFIG

class JobTracker:
    """작업 상태 추적 및 체크포인트 관리"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (CONFIG["LOG_DIR"] / "job_tracker.db")
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # sqlite3 context manager doesn't close; ensure close to avoid open handles.
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    status TEXT NOT NULL,  -- pending/processing/completed/failed
                    error_message TEXT,
                    msg_count INTEGER DEFAULT 0,
                    img_count INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(phone)
                )
            """)
            conn.commit()
            logging.info("✅ 체크포인트 데이터베이스 초기화 완료")
    
    def start_job(self, name: str, phone: str):
        """작업 시작 기록"""
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO job_history 
                (customer_name, phone, status, created_at, updated_at)
                VALUES (?, ?, 'processing', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (name, phone))
            conn.commit()
    
    def update_job(self, phone: str, status: str, msg_count: int = 0, 
                   img_count: int = 0, duration: float = 0, error: str = ""):
        """작업 상태 업데이트"""
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.execute("""
                UPDATE job_history
                SET status = ?, msg_count = ?, img_count = ?, 
                    duration_seconds = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE phone = ?
            """, (status, msg_count, img_count, duration, error, phone))
            conn.commit()
    
    def get_pending_jobs(self) -> List[Dict]:
        """미완료 작업 목록 조회"""
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT customer_name, phone, status, error_message
                FROM job_history
                WHERE status IN ('pending', 'processing')
                ORDER BY created_at
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_job_status(self, phone: str) -> Optional[str]:
        """특정 고객의 작업 상태 조회"""
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            cursor = conn.execute(
                "SELECT status FROM job_history WHERE phone = ?", (phone,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    def get_statistics(self) -> Dict:
        """작업 통계 조회"""
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                    AVG(duration_seconds) as avg_duration,
                    SUM(msg_count) as total_messages,
                    SUM(img_count) as total_images
                FROM job_history
            """)
            row = cursor.fetchone()
            if row:
                return {
                    "total": row[0] or 0,
                    "completed": row[1] or 0,
                    "failed": row[2] or 0,
                    "processing": row[3] or 0,
                    "avg_duration": round(row[4] or 0, 2),
                    "total_messages": row[5] or 0,
                    "total_images": row[6] or 0
                }
            return {}
    
    def clear_all(self):
        """모든 작업 기록 삭제 (초기화)"""
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.execute("DELETE FROM job_history")
            conn.commit()
            logging.warning("⚠️ 모든 작업 기록이 삭제되었습니다.")

    def delete_job(self, phone: str) -> bool:
        """특정 고객 기록 삭제"""
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            cursor = conn.execute("DELETE FROM job_history WHERE phone = ?", (phone,))
            conn.commit()
            return cursor.rowcount > 0

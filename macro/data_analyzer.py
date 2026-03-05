"""
데이터 분석 엔진
수집된 메시지 데이터를 분석하여 통계 및 인사이트 제공
"""
import pandas as pd
import re
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter
from .config import CONFIG

class DataAnalyzer:
    """엑셀 데이터 분석 클래스"""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or CONFIG["BASE_DOWNLOAD_DIR"]
    
    def get_all_chat_files(self) -> List[Path]:
        """모든 chat_log.xlsx 파일 경로 수집"""
        return list(self.base_dir.glob("*/chat_log.xlsx"))
    
    def analyze_keywords(self) -> Dict[str, int]:
        """키워드 빈도 분석"""
        keywords = CONFIG.get("HIGHLIGHT_KEYWORDS", [])
        keyword_counts = Counter()
        
        for chat_file in self.get_all_chat_files():
            try:
                df = pd.read_excel(chat_file)
                if '내용' not in df.columns:
                    continue
                
                for content in df['내용'].dropna():
                    content_str = str(content)
                    for keyword in keywords:
                        if keyword in content_str:
                            keyword_counts[keyword] += content_str.count(keyword)
            except Exception as e:
                continue
        
        return dict(keyword_counts)
    
    def analyze_customers(self) -> List[Dict]:
        """고객별 메시지 통계"""
        customer_stats = []
        
        for chat_file in self.get_all_chat_files():
            try:
                customer_name = chat_file.parent.name
                df = pd.read_excel(chat_file)
                
                total_msgs = len(df)
                my_msgs = len(df[df['보낸 사람'] == '나'])
                other_msgs = total_msgs - my_msgs
                
                # 첨부파일 수 계산
                attachments = 0
                if '첨부파일' in df.columns:
                    attachments = df['첨부파일'].str.len().sum()
                
                customer_stats.append({
                    "name": customer_name,
                    "total_messages": total_msgs,
                    "my_messages": my_msgs,
                    "other_messages": other_msgs,
                    "attachments": int(attachments) if pd.notna(attachments) else 0
                })
            except Exception as e:
                continue
        
        # 메시지 수 기준 정렬
        customer_stats.sort(key=lambda x: x['total_messages'], reverse=True)
        return customer_stats
    
    def analyze_timeline(self) -> Dict[str, int]:
        """시간대별 메시지 분포"""
        hour_counts = Counter()
        
        for chat_file in self.get_all_chat_files():
            try:
                df = pd.read_excel(chat_file)
                if '날짜' not in df.columns:
                    continue
                
                df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
                for dt in df['날짜'].dropna():
                    hour = dt.hour
                    hour_counts[hour] += 1
            except Exception as e:
                continue
        
        # 0-23시 전체 포함
        return {f"{h:02d}:00": hour_counts.get(h, 0) for h in range(24)}
    
    def get_summary_statistics(self) -> Dict:
        """전체 요약 통계"""
        total_customers = len(list(self.base_dir.glob("*/")))
        total_messages = 0
        total_attachments = 0
        
        for chat_file in self.get_all_chat_files():
            try:
                df = pd.read_excel(chat_file)
                total_messages += len(df)
                if '첨부파일' in df.columns:
                    total_attachments += df['첨부파일'].str.len().sum()
            except:
                continue
        
        return {
            "total_customers": total_customers,
            "total_messages": total_messages,
            "total_attachments": int(total_attachments) if pd.notna(total_attachments) else 0,
            "avg_messages_per_customer": round(total_messages / total_customers, 1) if total_customers > 0 else 0
        }

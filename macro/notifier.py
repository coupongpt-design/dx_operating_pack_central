"""
알림 시스템
이메일 및 슬랙/디스코드 Webhook을 통한 작업 완료/실패 알림
"""
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config import CONFIG

class Notifier:
    """통합 알림 전송 클래스"""
    
    def __init__(self):
        self.email_config = CONFIG.get("NOTIFICATION", {}).get("email", {})
        self.slack_webhook = CONFIG.get("NOTIFICATION", {}).get("slack_webhook")
        self.enabled = CONFIG.get("NOTIFICATION", {}).get("enabled", False)
    
    def send_email(self, subject: str, body: str) -> bool:
        """이메일 전송"""
        if not self.email_config.get("enabled"):
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config.get('from')
            msg['To'] = self.email_config.get('to')
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(
                self.email_config.get('smtp_server'),
                self.email_config.get('smtp_port', 587)
            )
            server.starttls()
            server.login(
                self.email_config.get('username'),
                self.email_config.get('password')
            )
            server.send_message(msg)
            server.quit()
            
            logging.info(f"✅ 이메일 전송 완료: {subject}")
            return True
        except Exception as e:
            logging.error(f"❌ 이메일 전송 실패: {e}")
            return False
    
    def send_slack(self, message: str, status: str = "info") -> bool:
        """슬랙 Webhook 전송"""
        if not self.slack_webhook:
            return False
        
        try:
            # 상태별 이모지
            emoji_map = {
                "success": ":white_check_mark:",
                "error": ":x:",
                "warning": ":warning:",
                "info": ":information_source:"
            }
            emoji = emoji_map.get(status, ":robot_face:")
            
            payload = {
                "text": f"{emoji} {message}",
                "username": "구글 메시지 다운로더",
                "icon_emoji": ":robot_face:"
            }
            
            response = requests.post(self.slack_webhook, json=payload, timeout=10)
            if response.status_code == 200:
                logging.info("✅ 슬랙 알림 전송 완료")
                return True
            else:
                logging.error(f"❌ 슬랙 알림 실패: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"❌ 슬랙 알림 전송 실패: {e}")
            return False
    
    def notify_completion(self, total_customers: int, success_count: int, fail_count: int, duration_minutes: float):
        """작업 완료 알림"""
        if not self.enabled:
            return
        
        subject = f"[완료] 구글 메시지 다운로드 작업"
        body = f"""
작업이 완료되었습니다.

📊 결과:
- 총 고객 수: {total_customers}명
- 성공: {success_count}명
- 실패: {fail_count}명
- 소요 시간: {duration_minutes:.1f}분

대시보드: http://localhost:5000
        """.strip()
        
        self.send_email(subject, body)
        self.send_slack(
            f"작업 완료 | 성공: {success_count}/{total_customers} | 소요: {duration_minutes:.1f}분",
            "success"
        )
    
    def notify_error(self, customer_name: str, error_message: str):
        """에러 알림"""
        if not self.enabled:
            return
        
        subject = f"[에러] {customer_name} 처리 실패"
        body = f"""
고객 처리 중 오류가 발생했습니다.

고객명: {customer_name}
오류 내용: {error_message}

대시보드에서 상세 로그를 확인하세요.
        """.strip()
        
        self.send_email(subject, body)
        self.send_slack(f"에러 발생 | {customer_name}: {error_message}", "error")

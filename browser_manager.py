import logging
import os
from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page
from config import CONFIG

class BrowserManager:
    def __init__(self):
        self.playwright: Playwright = None
        self.context: BrowserContext = None
        self.page: Page = None

    def start(self):
        """브라우저 및 컨텍스트 시작"""
        logging.info("브라우저를 실행합니다...")
        try:
            # Packaged 실행 환경에서도 로컬 브라우저 번들을 찾도록 보장
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
            self.playwright = sync_playwright().start()
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(CONFIG["USER_DATA_DIR"].resolve()),
                headless=False,
                viewport=CONFIG["VIEWPORT"],
                accept_downloads=True,
                args=["--disable-blink-features=AutomationControlled"] # 탐지 우회 시도
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            return self.page
        except Exception as e:
            logging.error(f"브라우저 시작 실패: {e}")
            self.stop()
            raise e

    def stop(self):
        """브라우저 종료"""
        try:
            if self.context:
                self.context.close()
        except Exception as e:
            logging.error(f"컨텍스트 종료 중 에러: {e}")
        
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logging.error(f"Playwright 종료 중 에러: {e}")

    def cleanup_profile(self):
        """프로필 데이터 초기화 (Safe Mode)"""
        import shutil
        import time
        
        profile_dir = CONFIG["USER_DATA_DIR"].resolve()
        pool_dirs = [
            p for p in profile_dir.parent.glob(f"{profile_dir.name}_*")
            if p.name[len(profile_dir.name) + 1:].isdigit()
        ]

        if profile_dir.exists() or pool_dirs:
            logging.warning(f"⚠️ 프로필 데이터 초기화 중: {profile_dir}")
            try:
                if profile_dir.exists():
                    shutil.rmtree(profile_dir, ignore_errors=True)

                for pool_dir in pool_dirs:
                    shutil.rmtree(pool_dir, ignore_errors=True)

                time.sleep(1) # 파일 시스템 반영 대기
                logging.info("✅ 프로필이 초기화되었습니다. (새로운 QR 스캔 필요)")
            except Exception as e:
                logging.error(f"❌ 프로필 삭제 실패: {e}")
                logging.info("브라우저가 켜져 있다면 끄고 다시 시도해주세요.")

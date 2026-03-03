"""
브라우저 풀 관리 (병렬 처리)
로그인 프로필을 복제하여 여러 브라우저 컨텍스트에 동일한 세션을 적용
"""
import logging
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, BrowserContext
from typing import List, Optional
from config import CONFIG
from google_messages import GoogleMessagesPage

class BrowserPool:
    """브라우저 풀 관리 클래스"""
    
    def __init__(self, pool_size: int = 2):
        """
        초기화
        
        Args:
            pool_size: 동시에 실행할 브라우저 개수 (기본 2개)
        """
        self.pool_size = pool_size
        self.playwright = None
        self.contexts: List[BrowserContext] = []
        self.base_context: Optional[BrowserContext] = None
        self.base_profile_dir = CONFIG["USER_DATA_DIR"]
        self.pool_profile_prefix = f"{self.base_profile_dir.name}_"
        self.profile_dirs: List[Path] = []
        
        logging.info(f"🔧 브라우저 풀 초기화 (크기: {pool_size})")

    def _remove_profile_locks(self, profile_dir: Path):
        """복제된 프로필의 잠금 파일 제거"""
        lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie", "Lockfile"]
        for lock_name in lock_files:
            lock_path = profile_dir / lock_name
            if lock_path.exists():
                try:
                    lock_path.unlink()
                except Exception:
                    pass

    def _clone_profile(self, src: Path, dst: Path):
        """프로필 복제 (로그인 상태 공유 목적)"""
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
        self._remove_profile_locks(dst)

    def _ensure_base_login(self, keep_open: bool = False) -> bool:
        """
        기본 프로필에 로그인 보장
        로그인 후 프로필을 복제해 풀 컨텍스트에 적용한다.
        """
        self.base_profile_dir.mkdir(parents=True, exist_ok=True)
        self._remove_profile_locks(self.base_profile_dir)

        context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.base_profile_dir.resolve()),
            headless=False,
            viewport=CONFIG["VIEWPORT"],
            accept_downloads=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ]
        )

        success = False
        try:
            page = context.pages[0] if context.pages else context.new_page()
            # 초기 탭이 about:blank인 경우 바로 메시지 페이지로 이동
            try:
                if "messages.google.com" not in page.url:
                    page.goto(
                        "https://messages.google.com/web/",
                        timeout=CONFIG["TIMEOUT_LONG"],
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_url("**/messages.google.com/**", timeout=CONFIG["TIMEOUT_LONG"])
            except Exception:
                pass
            scraper = GoogleMessagesPage(page)
            if not scraper.wait_for_login():
                logging.error("❌ 로그인 실패 또는 시간 초과")
                return False
            logging.info("✅ 기본 프로필 로그인 완료")
            success = True
            if keep_open:
                self.base_context = context
            return True
        finally:
            if not keep_open or not success:
                try:
                    context.close()
                except Exception:
                    pass

    def _get_pool_profile_dir(self, index: int) -> Path:
        return Path(f"./{self.pool_profile_prefix}{index}")

    def _prepare_pool_profiles(self):
        """풀 프로필 준비 (기본 프로필 복제)"""
        self.profile_dirs = [self.base_profile_dir]
        for i in range(1, self.pool_size):
            target_dir = self._get_pool_profile_dir(i)
            self._clone_profile(self.base_profile_dir, target_dir)
            self.profile_dirs.append(target_dir)

    def _launch_context(self, profile_dir: Path, headless: bool) -> BrowserContext:
        """프로필 기반 컨텍스트 생성"""
        profile_dir.mkdir(exist_ok=True, parents=True)
        self._remove_profile_locks(profile_dir)
        return self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir.resolve()),
            headless=headless,
            viewport=CONFIG["VIEWPORT"],
            accept_downloads=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ]
        )

    def start(self):
        """브라우저 풀 시작"""
        try:
            # Packaged 실행 환경에서도 로컬 브라우저 번들을 찾도록 보장
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
            self.playwright = sync_playwright().start()

            keep_open = self.pool_size == 1
            if not self._ensure_base_login(keep_open=keep_open):
                self.stop()
                return False

            if keep_open:
                if not self.base_context:
                    logging.error("기본 브라우저 컨텍스트를 유지하지 못했습니다.")
                    self.stop()
                    return False
                self.profile_dirs = [self.base_profile_dir]
                self.contexts = [self.base_context]
                logging.info("  브라우저 #1 초기화 완료 (헤드리스: False)")
                logging.info("✅ 브라우저 풀 시작 완료 (1개)")
                return True

            # 로그인된 기본 프로필을 복제하여 풀 프로필 생성
            self._prepare_pool_profiles()

            # 브라우저 컨텍스트(탭) 여러 개 생성
            for i, profile_dir in enumerate(self.profile_dirs):
                context = self._launch_context(profile_dir, headless=False if i == 0 else True)

                self.contexts.append(context)
                logging.info(f"  브라우저 #{i+1} 초기화 완료 (헤드리스: {i > 0})")

            logging.info(f"✅ 브라우저 풀 시작 완료 ({len(self.contexts)}개)")
            return True

        except Exception as e:
            logging.error(f"❌ 브라우저 풀 시작 실패: {e}")
            self.stop()
            return False
    
    def get_context(self, index: int) -> Optional[BrowserContext]:
        """
        특정 인덱스의 브라우저 컨텍스트 반환
        
        Args:
            index: 브라우저 인덱스 (0부터 시작)
            
        Returns:
            BrowserContext 또는 None
        """
        if 0 <= index < len(self.contexts):
            context = self.contexts[index]
            if context:
                try:
                    is_closed_attr = getattr(context, "is_closed", None)
                    is_closed = is_closed_attr() if callable(is_closed_attr) else bool(is_closed_attr)
                except Exception:
                    is_closed = False
                if not is_closed:
                    return context
        return None

    def refresh_context(self, index: int) -> Optional[BrowserContext]:
        """닫힌 컨텍스트를 재생성하여 안정성 확보"""
        if not self.playwright:
            logging.error("Playwright가 시작되지 않아 컨텍스트를 재생성할 수 없습니다.")
            return None
        if index < 0 or index >= len(self.profile_dirs):
            logging.error(f"잘못된 컨텍스트 인덱스: {index}")
            return None

        # [Stability] 닫힌 컨텍스트를 안전하게 재생성
        try:
            if index < len(self.contexts) and self.contexts[index]:
                try:
                    self.contexts[index].close()
                except Exception:
                    pass
            context = self._launch_context(self.profile_dirs[index], headless=False if index == 0 else True)
            if index < len(self.contexts):
                self.contexts[index] = context
            else:
                while len(self.contexts) < index:
                    self.contexts.append(None)
                self.contexts.append(context)
            logging.info(f"  브라우저 #{index+1} 재시작 완료 (헤드리스: {index > 0})")
            return context
        except Exception as e:
            logging.error(f"  브라우저 #{index+1} 재시작 실패: {e}")
            return None
    
    def get_next_context(self, customer_index: int) -> BrowserContext:
        """
        라운드로빈 방식으로 다음 브라우저 컨텍스트 반환
        
        Args:
            customer_index: 현재 처리 중인 고객 인덱스
            
        Returns:
            BrowserContext
        """
        pool_index = customer_index % self.pool_size
        logging.debug(f"고객 #{customer_index} → 브라우저 #{pool_index}")
        return self.contexts[pool_index]
    
    def stop(self):
        """브라우저 풀 정리"""
        try:
            # 모든 컨텍스트 닫기
            for i, context in enumerate(self.contexts):
                try:
                    context.close()
                    logging.debug(f"  브라우저 #{i+1} 종료")
                except:
                    pass

            # Playwright 종료
            if self.playwright:
                try:
                    self.playwright.stop()
                except:
                    pass
            
            self.contexts.clear()
            logging.info("✅ 브라우저 풀 정리 완료")
            
        except Exception as e:
            logging.error(f"⚠️ 브라우저 풀 정리 중 오류: {e}")
    
    def __enter__(self):
        """with문 지원"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """with문 종료 시 자동 정리"""
        self.stop()

import logging
import sys
import time
import platform
import os
import subprocess
import warnings
from config import CONFIG
from utils import setup_logging, parse_date_smart, ExecutionLogger
from browser_manager import BrowserManager
from browser_pool import BrowserPool  # Phase 4-1: 브라우저 풀 추가
from google_messages import GoogleMessagesPage
from data_handler import DataHandler
from job_tracker import JobTracker
import dashboard
from notifier import Notifier
from data_analyzer import DataAnalyzer
from pdf_generator import create_summary_report
from version import get_version

def open_result_folder(path):
    try:
        abs_path = path.resolve()
        if platform.system() == "Windows": os.startfile(abs_path)
        elif platform.system() == "Darwin": subprocess.Popen(["open", str(abs_path)])
        else: subprocess.Popen(["xdg-open", str(abs_path)])
        logging.info("📂 결과 폴더를 열었습니다.")
    except: pass

def safe_input(prompt):
    try:
        return input(prompt)
    except EOFError:
        logging.error("입력을 읽을 수 없어 프로그램을 종료합니다. (EOF)")
        return None

def _ensure_portable_cwd():
    """패키징 실행 시 작업 경로를 exe 위치로 고정"""
    if getattr(sys, "frozen", False):
        try:
            os.chdir(os.path.dirname(sys.executable))
        except Exception:
            pass

def _normalize_phone(phone):
    return "".join(ch for ch in str(phone) if ch.isdigit())

def _remove_completion_flags(phone=None):
    base_dir = CONFIG["BASE_DOWNLOAD_DIR"]
    if not base_dir.exists():
        logging.warning("결과 폴더가 없어 작업완료.txt를 삭제할 수 없습니다.")
        return 0

    targets = []
    if phone:
        target_digits = _normalize_phone(phone)
        if not target_digits:
            return 0
        for entry in base_dir.iterdir():
            if not entry.is_dir():
                continue
            entry_digits = _normalize_phone(entry.name)
            if target_digits in entry_digits:
                targets.append(entry)
    else:
        targets = [entry for entry in base_dir.iterdir() if entry.is_dir()]

    removed = 0
    for entry in targets:
        flag = entry / "작업완료.txt"
        if flag.exists():
            try:
                flag.unlink()
                removed += 1
            except Exception as e:
                logging.warning(f"작업완료.txt 삭제 실패: {entry} ({e})")
    return removed

def _confirm_reset():
    confirm = safe_input("정말 초기화하려면 YES를 입력하세요: ")
    if confirm is None:
        return False
    return confirm.strip().upper() == "YES"

def _reset_menu(tracker):
    print("\n" + "-" * 50)
    print(" [재작업 초기화 메뉴]")
    print(" - DB: system_logs/job_tracker.db (작업 상태/재시작 체크포인트)")
    print(" - 작업완료.txt: 고객 폴더 내 완료 플래그 (이미 완료된 작업 스킵)")
    print("-" * 50)
    print(" 1. DB만 초기화")
    print(" 2. 작업완료.txt만 초기화")
    print(" 3. 둘 다 초기화")
    print(" 4. 돌아가기")
    print("-" * 50)

    choice = safe_input(">> 메뉴 선택 (번호 입력): ")
    if choice is None:
        return False
    choice = choice.strip()
    if choice == '4':
        return True
    if choice not in {'1', '2', '3'}:
        print("잘못된 입력입니다.")
        return True

    scope = safe_input("초기화 대상 선택 (1. 전체 / 2. 특정 전화번호 / 3. 취소): ")
    if scope is None:
        return False
    scope = scope.strip()
    if scope == '3':
        return True
    if scope not in {'1', '2'}:
        print("잘못된 입력입니다.")
        return True

    if scope == '1' and not _confirm_reset():
        print("초기화를 취소했습니다.")
        return True

    phone = None
    if scope == '2':
        phone = safe_input("전화번호 입력: ")
        if phone is None:
            return False
        phone = _normalize_phone(phone)
        if not phone:
            print("전화번호 입력이 올바르지 않습니다.")
            return True

    # [Reset] 선택된 초기화 옵션 실행
    if choice in {'1', '3'}:
        if phone:
            deleted = tracker.delete_job(phone)
            print("DB 기록 삭제 완료." if deleted else "DB 기록이 없습니다.")
        else:
            tracker.clear_all()

    if choice in {'2', '3'}:
        removed = _remove_completion_flags(phone)
        print(f"작업완료.txt 삭제: {removed}건")

    return True

def main():
    _ensure_portable_cwd()
    setup_logging()
    logger = ExecutionLogger()
    browser_mgr = BrowserManager()
    tracker = JobTracker()  # 체크포인트 시스템
    notifier = Notifier()  # 알림 시스템
    
    while True:
        print("\n" + "="*50)
        print(f" [구글 메시지 다운로더 v{get_version()} - 메인 메뉴]")
        print("="*50)
        print(" 1. 작업 시작 (Start)")
        print(" 2. 로그인 초기화 (Safe Mode/Reset)")
        print(" 3. 엑셀 양식 생성 (Create Template)")
        print(" 4. 종료 (Exit)")
        print(" 5. 재작업 초기화 (DB/작업완료)")
        print("="*50)
        
        if len(sys.argv) > 1 and sys.argv[1] == '--auto':
            choice = '1'
            print(">> 자동 실행 모드: 작업 시작")
        else:
            choice = safe_input(">> 메뉴 선택 (번호 입력): ")
            if choice is None:
                return
            choice = choice.strip()
        
        if choice == '1':
            break # 작업 시작 루프로 이동
        elif choice == '2':
            browser_mgr.cleanup_profile()
            print("\n[알림] 초기화 완료. 다시 '1. 작업 시작'을 선택하세요.")
            if safe_input("엔터 키를 누르면 메뉴로 돌아갑니다...") is None:
                return
            continue
        elif choice == '3':
            DataHandler.create_template()
            if safe_input("엔터 키를 누르면 메뉴로 돌아갑니다...") is None:
                return
            continue
        elif choice == '4':
            print("프로그램을 종료합니다.")
            return
        elif choice == '5':
            if not _reset_menu(tracker):
                return
            continue
        else:
            print("잘못된 입력입니다.")
            continue
    
    # 웹 대시보드 시작 (별도 스레드)
    print("\n🌐 웹 대시보드를 시작합니다...")
    dashboard.start_dashboard_thread(port=5000)
    print("   ✅ 브라우저에서 http://localhost:5000 접속하여 진행 상황을 확인할 수 있습니다.\n")
    time.sleep(2)  # 서버 시작 대기
    
    # Phase 4-1 (M1): 브라우저 풀 사용
    pool_size = CONFIG.get("BROWSER_POOL_SIZE", 2)
    logging.info(f"🔧 브라우저 풀 시작 (크기: {pool_size})")
    pool = BrowserPool(pool_size=pool_size)
    
    try:
        if not pool.start():
            logging.error("브라우저 풀 시작 실패")
            return

        # 브라우저 풀에서 로그인/프로필 준비 완료
        first_context = pool.get_context(0)
        if not first_context:
            logging.error("브라우저 컨텍스트를 가져올 수 없습니다")
            return

        while True:
            print("\n" + "="*40)
            print(" 작업 시작...")
            
            targets = DataHandler.get_targets()
            valid_list = []
            if targets is not None:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        category=FutureWarning,
                        message="Downcasting object dtype arrays",
                    )
                    targets = targets.fillna("")
                for _, row in targets.iterrows():
                    name = str(row.get('이름', '')).strip()
                    phone = str(row.get('전화번호', '')).replace("-", "").strip()
                    if phone:
                        if not name or name.lower() == 'nan': name = "이름미정"
                        valid_list.append((name, phone, parse_date_smart(row.get('시작일'), False), parse_date_smart(row.get('종료일'), True)))
                
                logging.info(f"총 {len(valid_list)}명 처리 시작")
                login_failed = False

                for idx, (name, phone, s, e) in enumerate(valid_list):
                    # 웹 대시보드에 진행률 업데이트
                    dashboard.update_progress(idx, len(valid_list), name)
                    folder_name = f"{name}_{phone}"
                    path = CONFIG["BASE_DOWNLOAD_DIR"] / folder_name
                    
                    # 체크포인트: 이미 완료된 작업 스킵
                    job_status = tracker.get_job_status(phone)
                    if job_status == 'completed' or (path / "작업완료.txt").exists():
                        print(f"\n[{idx+1}/{len(valid_list)}] {name} >> [스킵] 이미 완료된 작업입니다.")
                        logger.log_execution(name, "Skip", 0, note="이미 완료됨")
                        continue
                    
                    # Phase 4-1 (M1): 라운드로빈 방식으로 브라우저 선택
                    browser_idx = idx % pool_size
                    current_context = pool.get_context(browser_idx)
                    if not current_context:
                        # [Stability] 닫힌 컨텍스트는 재생성하여 작업 지속
                        logging.warning(f"브라우저 #{browser_idx+1} 컨텍스트 재시작을 시도합니다.")
                        current_context = pool.refresh_context(browser_idx)
                    if not current_context:
                        logging.error("브라우저 컨텍스트를 가져올 수 없습니다.")
                        logger.log_execution(name, "Fail", 0, note="브라우저 컨텍스트 없음")
                        tracker.update_job(phone, 'failed', error="브라우저 컨텍스트 없음")
                        continue

                    current_page = None
                    for page in current_context.pages:
                        if not page.is_closed():
                            current_page = page
                            break
                    if not current_page:
                        try:
                            current_page = current_context.new_page()
                        except Exception as e:
                            logging.error(f"페이지 생성 실패: {e}")
                            logger.log_execution(name, "Fail", 0, note="페이지 생성 실패")
                            tracker.update_job(phone, 'failed', error="페이지 생성 실패")
                            continue
                    
                    status_msg = "재작업" if path.exists() else "신규 작업"
                    print(f"\n[{idx+1}/{len(valid_list)}] {name}({phone}) 처리 시작 ({status_msg}) [브라우저 #{browser_idx+1}]")
                    path.mkdir(parents=True, exist_ok=True)
                    
                    # 체크포인트: 작업 시작 기록
                    tracker.start_job(name, phone)
                    
                    # 현재 브라우저의 scraper 생성
                    current_scraper = GoogleMessagesPage(current_page)

                    # 구글 메시지로 이동 (각 브라우저마다 필요 시)
                    try:
                        if "messages.google.com" not in current_page.url:
                            for attempt in range(1, 3):
                                try:
                                    current_page.goto("https://messages.google.com/web/", timeout=CONFIG["TIMEOUT_LONG"])
                                    time.sleep(2)  # 페이지 로딩 대기
                                    break
                                except Exception as e:
                                    logging.warning(f"페이지 이동 실패 ({attempt}/2): {e}")
                                    time.sleep(1.5 * attempt)
                    except Exception as e:
                        logging.warning(f"페이지 이동 실패 (계속 진행): {e}")

                    # [Change] 세션 만료 시 재로그인을 요구하고 실패 시 안전 종료
                    if not current_scraper.is_logged_in():
                        logging.warning("로그인 세션 만료 감지. 재로그인을 기다립니다...")
                        if not current_scraper.wait_for_login():
                            logging.error("로그인 재시도 실패. 작업을 중단합니다.")
                            login_failed = True
                            break
                    
                    start_time = time.time()
                    
                    try:
                        if current_scraper.enter_chat_room(phone):
                            current_scraper.load_past_messages(s)
                            msg_cnt, img_cnt = current_scraper.process_messages(path, s, e)
                            duration = time.time() - start_time
                            logger.log_execution(name, "Success", duration, msg_cnt, img_cnt)
                            
                            # 체크포인트: 작업 완료 기록
                            tracker.update_job(phone, 'completed', msg_cnt, img_cnt, duration)
                            
                            # 메인으로 복귀
                            try: current_page.goto("https://messages.google.com/web/")
                            except: pass
                        else:
                            duration = time.time() - start_time
                            logger.log_execution(name, "Fail", duration, note="진입 실패")
                            
                            # 체크포인트: 실패 기록
                            tracker.update_job(phone, 'failed', error="진입 실패")
                            
                            try: current_page.goto("https://messages.google.com/web/")
                            except: pass
                            
                    except Exception as e:
                        logging.error(f"[ERROR] 작업 중 오류: {e}")
                        logger.log_execution(name, "Error", 0, note=str(e))
                        
                        # 체크포인트: 에러 기록
                        tracker.update_job(phone, 'failed', error=str(e))
                        if "로그인" in str(e):
                            logging.warning("로그인 오류 감지. 다음 루프에서 재확인합니다.")

                if login_failed:
                    print("\n[오류] 로그인 실패로 작업을 중단합니다.")
                    break
            else:
                # [Fix] 타겟 로드 실패 시 다음 루프로 이동 (동작 변경 명시)
                if safe_input("\n[오류] 엑셀 파일을 확인한 뒤 엔터를 누르면 재시작합니다...") is None:
                    return
                continue

            open_result_folder(CONFIG["BASE_DOWNLOAD_DIR"])
            
            # 데이터 분석 및 PDF 리포트 생성
            try:
                analyzer = DataAnalyzer()
                summary = analyzer.get_summary_statistics()
                keywords = analyzer.analyze_keywords()
                customers = analyzer.analyze_customers()
                
                if len(valid_list) > 0:
                    pdf_path = create_summary_report(
                        CONFIG["BASE_DOWNLOAD_DIR"],
                        summary,
                        keywords,
                        customers
                    )
                    logging.info(f"📄 PDF 리포트 생성: {pdf_path}")
            except Exception as e:
                logging.warning(f"PDF 리포트 생성 실패: {e}")
            
            # 작업 완료 알림
            stats = tracker.get_statistics()
            notifier.notify_completion(
                total_customers=len(valid_list),
                success_count=stats.get('completed', 0),
                fail_count=stats.get('failed', 0),
                duration_minutes=(time.time() - start_time) / 60 if 'start_time' in locals() else 0
            )
            
            print("\n[완료] 엑셀 수정 후 엔터(Enter) -> 재시작")
            print("[종료] 'q' 입력 후 엔터")
            user_choice = safe_input(">> ")
            if user_choice is None:
                return
            if user_choice.strip().lower() == 'q':
                break
                
    except Exception as e:
        logging.error(f"치명적 오류 발생: {e}")
    finally:
        pool.stop()  # Phase 4-1: BrowserPool 정리

if __name__ == "__main__":
    main()

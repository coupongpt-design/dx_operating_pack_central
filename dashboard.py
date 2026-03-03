"""
웹 대시보드 서버
실시간 진행 상황 모니터링 및 로그 스트리밍
"""
import logging
import threading
import sys
from flask import Flask, render_template, jsonify, cli
from flask_socketio import SocketIO, emit
from pathlib import Path
from job_tracker import JobTracker
from config import CONFIG
from data_analyzer import DataAnalyzer

def _resource_path(relative: str) -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir / relative

app = Flask(__name__, template_folder=str(_resource_path("templates")))
app.config['SECRET_KEY'] = 'google_messages_scraper_secret'
cli.show_server_banner = lambda *args, **kwargs: None

class _DummySocketIO:
    def emit(self, *args, **kwargs):
        return None

    def run(self, app, host, port, debug, use_reloader):
        app.run(host=host, port=port, debug=debug, use_reloader=use_reloader, threaded=True)

    def on(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

def _init_socketio():
    # Packaged 환경에서 eventlet/gevent 미탑재 이슈 방지
    try:
        return SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    except Exception as e:
        logging.warning(f"SocketIO init failed; dashboard realtime disabled: {e}")
        return _DummySocketIO()

socketio = _init_socketio()

# 전역 변수
tracker = JobTracker()
analyzer = DataAnalyzer()
current_progress = {"current": 0, "total": 0, "customer_name": ""}

class WebSocketLogHandler(logging.Handler):
    """로그를 웹소켓으로 전송하는 핸들러"""
    def emit(self, record):
        log_entry = self.format(record)
        socketio.emit('log_message', {'message': log_entry})

def setup_websocket_logging():
    """웹소켓 로그 핸들러 등록"""
    ws_handler = WebSocketLogHandler()
    ws_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logging.getLogger().addHandler(ws_handler)

@app.route('/')
def index():
    """메인 대시보드 페이지"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def get_stats():
    """작업 통계 API"""
    stats = tracker.get_statistics()
    return jsonify(stats)

@app.route('/api/jobs')
def get_jobs():
    """작업 목록 API"""
    pending = tracker.get_pending_jobs()
    return jsonify(pending)

@app.route('/api/analysis/keywords')
def get_keyword_analysis():
    """키워드 분석 API"""
    keywords = analyzer.analyze_keywords()
    return jsonify(keywords)

@app.route('/api/analysis/customers')
def get_customer_analysis():
    """고객별 통계 API"""
    customers = analyzer.analyze_customers()
    return jsonify(customers[:20])  # 상위 20명만

@app.route('/api/analysis/timeline')
def get_timeline_analysis():
    """시간대별 분포 API"""
    timeline = analyzer.analyze_timeline()
    return jsonify(timeline)

@app.route('/api/analysis/summary')
def get_summary():
    """요약 통계 API"""
    summary = analyzer.get_summary_statistics()
    return jsonify(summary)

@socketio.on('connect')
def handle_connect():
    """클라이언트 연결 시"""
    emit('connection_response', {'data': 'Connected to dashboard'})

@socketio.on('request_progress')
def handle_progress_request():
    """진행률 요청 시"""
    emit('progress_update', current_progress)

def update_progress(current, total, customer_name):
    """진행률 업데이트 (메인 프로그램에서 호출)"""
    global current_progress
    current_progress = {
        "current": current,
        "total": total,
        "customer_name": customer_name,
        "percentage": int((current / total * 100)) if total > 0 else 0
    }
    socketio.emit('progress_update', current_progress)

def run_dashboard(port=5000):
    """대시보드 서버 실행 (별도 스레드)"""
    setup_websocket_logging()
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.info(f"🌐 웹 대시보드 실행 중: http://localhost:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)

def start_dashboard_thread(port=5000):
    """대시보드를 별도 스레드로 시작"""
    thread = threading.Thread(target=run_dashboard, args=(port,), daemon=True)
    thread.start()
    return thread

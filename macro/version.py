__version__ = "5.1.0"
__author__ = "Google Messages Scraper Team"
__description__ = "Enterprise-grade Customer Messaging Archive System"

# 버전 히스토리
VERSION_HISTORY = {
    "5.1.0": {
        "date": "2026-01-19",
        "features": [
            "Phase 4-1 M1: 브라우저 풀 기초 구현",
            "라운드로빈 방식 브라우저 분산 (2개)",
            "순차 처리 유지하면서 브라우저 부하 분산"
        ]
    },
    "5.0.0": {
        "date": "2026-01-19",
        "features": [
            "데이터 분석 대시보드 (Chart.js)",
            "알림 시스템 (이메일/슬랙)",
            "PDF 리포트 자동 생성",
            "작업 재개 기능 (체크포인트)",
            "실시간 웹 대시보드",
            "Strict mode 에러 완전 제거",
            "UTF-8 인코딩 강제"
        ]
    },
    "4.5.0": {
        "date": "2025-12-01",
        "features": [
            "엑셀 자동 서식",
            "이미지 임베딩",
            "키워드 강조"
        ]
    }
}

def get_version():
    """현재 버전 반환"""
    return __version__

def print_version_info():
    """버전 정보 출력"""
    print(f"Google Messages Scraper v{__version__}")
    print(f"Author: {__author__}")
    print(f"Description: {__description__}")

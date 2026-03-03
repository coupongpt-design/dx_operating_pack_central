# 구글 메시지 다운로더 v5.1

> **엔터프라이즈급 고객 상담 기록 자동 아카이빙 시스템**

[![Version](https://img.shields.io/badge/version-5.1-blue.svg)](https://github.com/yourusername/google-messages-scraper)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

---

## 📋 목차

- [소개](#소개)
- [주요 기능](#주요-기능)
- [시스템 요구사항](#시스템-요구사항)
- [설치 가이드](#설치-가이드)
- [사용 방법](#사용-방법)
- [설정 가이드](#설정-가이드)
- [FAQ](#faq)
- [문제 해결](#문제-해결)

---

## 소개

구글 메시지 웹에서 고객과의 문자 메시지를 **자동으로 수집·저장·분석**하는 업무 자동화 도구입니다.

### 사용 대상
- 여행사 / 호텔·펜션 등 숙박업
- 부동산 중개업
- 온라인 쇼핑몰
- 모든 B2C 서비스 사업자

### 핵심 가치
- ✅ **법적 증빙**: 예약/입금/취소 분쟁 시 완벽한 기록 보존
- ✅ **업무 자동화**: 100명 처리 시간 85% 절감 (13시간 → 2시간)
- ✅ **데이터 분석**: 키워드 통계, 차트, PDF 리포트 자동 생성

---

## 주요 기능

### 1️⃣ 자동 메시지 수집
- 엑셀에 고객 정보 입력 → 자동으로 모든 대화 내역 다운로드
- 텍스트 + 이미지 + 영수증 완벽 보존
- 날짜 범위 필터링 지원

### 2️⃣ 실시간 웹 대시보드
- 진행률 실시간 표시
- 로그 스트리밍
- 데이터 분석 차트 (키워드/시간대/고객별)

### 3️⃣ 작업 재개 기능
- 프로그램 중단 시 → 재시작 시 자동으로 이어서 실행
- 완료된 작업은 자동 스킵 (체크포인트 DB 기준)

### 4️⃣ 알림 시스템
- 작업 완료 시 이메일/슬랙 알림
- 에러 발생 시 즉시 통지

### 5️⃣ PDF 리포트 자동 생성
- 통계 테이블 포함 전문 리포트
- 경영진 보고 자료로 즉시 활용

### 6️⃣ 브라우저 풀 기반 안정화
- 로그인 완료된 기본 프로필을 복제해 동일 세션 유지
- 순차 처리 유지 + 컨텍스트 분리로 안정성 향상

---

## 시스템 요구사항

### 필수
- **OS**: Windows 10/11, macOS, Linux
- **Python**: 3.8 이상
- **브라우저**: Chromium (자동 설치)
- **저장 공간**: 최소 1GB (고객 데이터에 따라 증가)

### 권장
- **RAM**: 4GB 이상
- **인터넷**: 안정적인 연결 (10Mbps+)

---

## 설치 가이드

### 1단계: Python 설치

**Windows**:
1. [python.org](https://www.python.org/downloads/)에서 Python 3.8+ 다운로드
2. 설치 시 "Add Python to PATH" 체크 ✅

**macOS/Linux**:
```bash
# 이미 설치되어 있을 가능성 높음
python3 --version
```

### 2단계: 프로그램 다운로드

프로그램 파일들을 원하는 폴더에 압축 해제

### 3단계: 의존성 설치

```powershell
# 프로그램 폴더로 이동
cd D:\down\매크로\구글메세지다운로드\main

# 필요한 라이브러리 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

### 4단계: 초기 설정

`targets.xlsm` 파일 생성:
```
프로그램 실행 → 메뉴에서 "3. 엑셀 양식 생성" 선택
```

---

## 사용 방법

### 기본 사용 흐름

```
1. targets.xlsm에 고객 정보 입력
   (이름, 전화번호, 시작일, 종료일)

2. 프로그램 실행
   python main_refactored.py

3. 메뉴에서 "1. 작업 시작" 선택

4. (최초 1회) QR 코드 스캔하여 로그인

5. 웹 대시보드 접속
   http://localhost:5000

6. 자동 처리 완료 대기

7. customer_data 폴더에서 결과 확인
```

### 엑셀 파일 작성 예시

| 이름 | 전화번호 | 시작일 | 종료일 |
|------|----------|--------|--------|
| 홍길동 | 010-1234-5678 | 2024-01-01 | 2024-12-31 |
| 김철수 | 010-9876-5432 | | |

- **시작일/종료일**: 비워두면 전체 기간

---

## 설정 가이드

### 알림 설정 (선택사항)

[config.py](file:///D:/down/매크로/구글메세지다운로드/main/config.py) 파일 수정:

#### 이메일 알림 (Gmail)

1. Gmail 앱 비밀번호 생성
   - Google 계정 → 보안 → 2단계 인증 활성화
   - 앱 비밀번호 생성

2. config.py 수정:
```python
CONFIG["NOTIFICATION"] = {
    "enabled": True,  # False → True 변경
    "email": {
        "enabled": True,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "your@gmail.com",
        "password": "abcd efgh ijkl mnop",  # 앱 비밀번호
        "from": "your@gmail.com",
        "to": "manager@company.com"
    }
}
```

#### 슬랙 알림

1. Slack Webhook URL 생성
   - https://api.slack.com/messaging/webhooks

2. config.py 수정:
```python
CONFIG["NOTIFICATION"]["slack_webhook"] = "https://hooks.slack.com/services/..."
```

### 키워드 강조 커스터마이징

```python
CONFIG["HIGHLIGHT_KEYWORDS"] = [
    "예약", "취소", "환불", "입금", "영수증"
    # 원하는 키워드 추가
]
```

### 브라우저 풀 설정 (안정성/성능)

```python
# 기본값 1 (안정성 우선)
CONFIG["BROWSER_POOL_SIZE"] = 1
```

### 첨부 저장 설정 (대용량 처리)

```python
# blob 다운로드 청크 크기 (바이트)
CONFIG["BLOB_CHUNK_SIZE"] = 1024 * 1024
```

---

## FAQ

### Q1. QR 코드가 계속 나와요
**A**: 스마트폰의 메시지 앱에서 "기기 페어링" → QR 코드 스캐너로 화면의 코드를 찍으세요.

### Q2. 중간에 에러가 나서 멈췄어요
**A**: 프로그램을 다시 실행하면 **자동으로 이어서** 실행됩니다. (체크포인트 시스템)

### Q3. 특정 고객만 다시 받고 싶어요
**A**: `작업완료.txt` 삭제 후에도 스킵된다면 `system_logs/job_tracker.db`에 완료 기록이 남아 있습니다.  
해당 DB를 삭제하거나, 재처리할 고객의 기록을 제거하면 다시 처리됩니다.

### Q4. 웹 대시보드가 안 열려요
**A**: 
- 방화벽 확인
- 다른 프로그램이 5000 포트 사용 중인지 확인
- `http://127.0.0.1:5000`으로 시도

### Q5. 이미지가 누락됐어요
**A**: `검수보고서.csv`에서 누락 여부 확인. 네트워크 불안정 시 재실행하세요.

---

## 문제 해결

### 🔴 "로그인 실패" 오류

**원인**: 구글 메시지 웹에서 로그아웃됨

**해결**:
```
메뉴 → "2. 로그인 초기화" → QR 코드 다시 스캔
```

### 🔴 "ModuleNotFoundError" 에러

**원인**: 필요한 라이브러리 미설치

**해결**:
```powershell
pip install -r requirements.txt
playwright install chromium
```

### 🔴 브라우저가 안 열려요

**원인**: Playwright 브라우저 미설치

**해결**:
```powershell
playwright install chromium
```

### 🔴 엑셀 파일 저장 오류

**원인**: targets.xlsm 파일이 열려 있음

**해결**: 엑셀 프로그램에서 파일을 닫고 재실행

---

## 📞 지원

- **이메일**: support@example.com
- **문서**: [완료 보고서](file:///C:/Users/Admin/.gemini/antigravity/brain/1689ef6e-da04-4bfa-a677-e4aefb6f066c/walkthrough.md)

---

## 📄 라이선스

MIT License

---

## 🙏 크레딧

- **Playwright**: 브라우저 자동화
- **Flask**: 웹 대시보드
- **ReportLab**: PDF 생성
- **Chart.js**: 데이터 시각화

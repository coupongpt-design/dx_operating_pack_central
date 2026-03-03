@echo off
chcp 65001
echo [배포 파일 생성 도구]
echo.
echo 1. 필수 라이브러리 설치 중...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo 2. 실행 파일(EXE) 생성 중...
echo 잠시만 기다려주세요 (약 1~3분 소요)...
pyinstaller --onefile --name "GoogleMsgDownloader" --clean main_refactored.py

echo.
echo [완료] dist 폴더 안에 'GoogleMsgDownloader.exe'가 생성되었습니다.
echo.
pause

@echo off
setlocal enabledelayedexpansion
echo.
echo [Portable build]
echo.
echo 1. Install requirements...
python -m pip install -r requirements.txt
echo.
echo 2. Ensure PyInstaller...
python -c "import PyInstaller" >nul 2>nul || python -m pip install pyinstaller
echo.
echo 3. Install Playwright Chromium...
set PLAYWRIGHT_BROWSERS_PATH=0
python -m playwright install chromium
echo.
echo 4. Build onedir...
python -m PyInstaller --noconfirm --clean --onedir --name "GoogleMsgDownloader" --collect-all playwright --add-data "templates;templates" main_refactored.py
echo.
echo 5. Copy Playwright browsers...
python -c "import pathlib,shutil,playwright; src=pathlib.Path(playwright.__file__).resolve().parent/'driver'/'package'/'.local-browsers'; dst=pathlib.Path('dist/GoogleMsgDownloader/playwright/driver/package/.local-browsers'); dst.parent.mkdir(parents=True, exist_ok=True); print('PW src:', src); shutil.copytree(src, dst, dirs_exist_ok=True) if src.exists() else print('NO_BROWSER_DIR')"
echo.
echo 6. Copy sample targets.xlsm...
if exist targets.xlsm copy /y targets.xlsm dist\GoogleMsgDownloader\ >nul
echo.
echo [DONE] Copy dist\GoogleMsgDownloader to another PC.
pause
endlocal

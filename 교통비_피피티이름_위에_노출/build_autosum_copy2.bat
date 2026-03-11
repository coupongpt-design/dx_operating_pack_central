@echo off
python -m PyInstaller --noconfirm --clean --onefile --console --name autosum_copy2 AUTOSU~2.PY
if errorlevel 1 exit /b 1
echo Build complete: dist\autosum_copy2.exe

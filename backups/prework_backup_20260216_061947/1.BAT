@echo off
SETLOCAL

REM --- 사용자 환경에 맞게 Pythonw.exe 경로를 수정하세요 ---
REM 기본 설치 경로 예시:
SET PYTHON_PATH=C:\Users\Admin\AppData\Local\Programs\Python\Python311\pythonw.exe

REM 만약 다른 경로에 설치했다면, 해당 경로로 수정하세요.
REM 예: SET PYTHON_PATH=C:\Python310\pythonw.exe

REM 레지스트리 키 설정
SET KEY_PATH="HKCU\Software\Classes\Python.File\shell\Open with IDLE\command"
SET KEY_PATH_PYW="HKCU\Software\Classes\Python.NoConFile\shell\Open with IDLE\command"
SET COMMAND_STR="\"%PYTHON_PATH%\" \"C:\Users\Admin\AppData\Local\Programs\Python\Python311\Lib\idlelib\idle.pyw\" \"%%1\""
REM 위 COMMAND_STR의 idle.pyw 경로도 실제 설치 경로에 맞게 수정해야 합니다.

REM .py 파일에 대한 레지스트리 추가
REG ADD %KEY_PATH% /ve /t REG_SZ /d %COMMAND_STR% /f
REG ADD "HKCU\Software\Classes\Python.File\shell\Open with IDLE" /v "Icon" /t REG_SZ /d "\"%PYTHON_PATH%\",0" /f

REM .pyw 파일에 대한 레지스트리 추가
REG ADD %KEY_PATH_PYW% /ve /t REG_SZ /d %COMMAND_STR% /f
REG ADD "HKCU\Software\Classes\Python.NoConFile\shell\Open with IDLE" /v "Icon" /t REG_SZ /d "\"%PYTHON_PATH%\",0" /f

ECHO.
ECHO 레지스트리 항목이 성공적으로 추가되었습니다.
ECHO .py 파일을 마우스 우클릭하여 "Open with IDLE" 메뉴를 확인하세요.
PAUSE

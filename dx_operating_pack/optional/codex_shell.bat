@echo off
setlocal EnableExtensions

rem --- Hard sanitize PATH (prepend known-good system paths) ---
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0;C:\Program Files\Git\cmd;%PATH%"

rem --- Optional quick sanity check ---
where where >nul 2>nul
where powershell >nul 2>nul
where git >nul 2>nul

if "%~1"=="" (
  cmd /k
) else (
  cmd /c %*
)
endlocal
@echo off
setlocal
set "BIN_DIR=%~dp0"
set "TOOLKIT_ROOT=%BIN_DIR%.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TOOLKIT_ROOT%\start-issue.ps1" %*
exit /b %ERRORLEVEL%

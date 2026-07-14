@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-desktop-app.ps1" %*
exit /b %ERRORLEVEL%

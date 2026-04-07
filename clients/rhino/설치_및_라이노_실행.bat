@echo off
chcp 65001 >nul 2>&1
setlocal
REM CAD Manage - Install + Run Rhino (double-click to install and launch)

cd /d "%~dp0"

echo CAD Manage Rhino - Installing and starting...
echo.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install_and_run.ps1"
if errorlevel 1 (
  echo Error. Check %TEMP%\cadmanage_launcher_log.txt
  pause
  exit /b 1
)
echo.
echo Done. In Rhino, use [1] Get from DB to load.
echo.
pause

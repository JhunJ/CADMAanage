@echo off
chcp 65001 >nul 2>&1
setlocal
REM CAD Manage - Install + Run Rhino (double-click to install and launch)

cd /d "%~dp0"

echo [1/2] Installing CAD Manage Rhino...
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install_cadmanage_protocol.ps1"
if errorlevel 1 (
  echo Install error. Check %TEMP%\cadmanage_launcher_log.txt
  pause
  exit /b 1
)
echo.

echo [2/2] Starting Rhino...
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0open_rhino_cadmanage.ps1"
if errorlevel 1 (
  pause
  exit /b 1
)
echo Rhino started. Use menu [1] Get from DB to load.
echo.
pause

@echo off
REM CAD Manage - protocol launcher wrapper (shows errors if any)
set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%launcher.ps1" "%1"
if errorlevel 1 (
  echo.
  echo Launcher failed. Check %TEMP%\cadmanage_launcher_log.txt
  pause
)

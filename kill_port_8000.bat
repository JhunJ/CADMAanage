@echo off
REM Free every process listening on TCP 8000 (127.0.0.1 and 0.0.0.0 may differ).
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Free TCP port 8000
echo ============================================
echo.

where powershell >nul 2>&1
if errorlevel 1 (
    echo PowerShell not found.
    goto :fallback
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kill_port_8000.ps1"
if errorlevel 1 (
    echo.
    echo [fallback] taskkill via netstat ...
    goto :fallback
)
goto :show

:fallback
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do (
    if not "%%a"=="0" if not "%%a"=="4" (
        echo taskkill /F /PID %%a
        taskkill /F /PID %%a 2>nul
    )
)
timeout /t 2 /nobreak >nul

:show
echo.
echo netstat LISTENING on 8000 (empty = OK^):
netstat -ano 2>nul | findstr ":8000" | findstr "LISTENING"
echo.
echo If lines remain, run this BAT as Administrator (right-click).
echo Then run run.bat for CAD Manage.
pause

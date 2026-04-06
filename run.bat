@echo off
REM 더블클릭 시 cmd /k 로 새 창에서 실행 (창이 바로 꺼지지 않음)
if not "%~1"=="_" (
    cmd /k "%~f0" _
    exit /b 0
)

chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 (
    echo 오류: 작업 폴더로 이동할 수 없습니다. [%~dp0]
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   CAD Manage - run.bat
echo ==========================================
echo 경로: %CD%
echo.

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1" -ListenHost 0.0.0.0 -PreparePostgres -MigrationRetries 12 -FromRunBat
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1" -ListenHost 0.0.0.0 -PreparePostgres -MigrationRetries 12 -FromRunBat
)
set "PS_EXIT=%ERRORLEVEL%"

echo.
if not "%PS_EXIT%"=="0" (
    echo run.bat이 비정상 종료되었습니다. 위 메시지를 확인하세요.
)
pause
exit /b %PS_EXIT%

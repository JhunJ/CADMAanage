@echo off
REM ?붾툝?대┃ ??cmd /k 濡???李쎌뿉???ㅽ뻾 (李쎌씠 諛붾줈 爰쇱?吏 ?딆쓬)
if not "%~1"=="_" (
    cmd /k "%~f0" _
    exit /b 0
)

chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 (
    echo ?ㅻ쪟: ?묒뾽 ?대뜑濡??대룞?????놁뒿?덈떎. [%~dp0]
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   CAD Manage - run.bat
echo ==========================================
echo 寃쎈줈: %CD%
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
    echo run.bat??鍮꾩젙??醫낅즺?섏뿀?듬땲?? ??硫붿떆吏瑜??뺤씤?섏꽭??
)
pause
exit /b %PS_EXIT%

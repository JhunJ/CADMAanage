@echo off
REM DB 계정/비밀번호/PostGIS 맞추기 (postgres 비밀번호 1회 입력)
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ==========================================
echo   CAD Manage - DB setup (one-time)
echo ==========================================
echo.
echo Fixes: password authentication failed for user "caduser"
echo Uses .env default password: cadpass
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\init_db.ps1"
echo.
pause
exit /b %ERRORLEVEL%

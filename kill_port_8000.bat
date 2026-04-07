@echo off
REM 8000 포트 사용 중인 프로세스 종료. 관리자 권한으로 실행 권장.
echo 8000 포트 LISTENING 프로세스 확인 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    if not %%a==0 if not %%a==4 (
        echo PID %%a 종료 시도...
        taskkill /F /PID %%a
    )
)
timeout /t 2 /nobreak >nul
echo.
echo netstat 확인:
netstat -ano | findstr ":8000" | findstr "LISTENING"
echo.
echo 위에 아무것도 없으면 8000 포트 비어 있음. run.bat 실행하세요.
pause

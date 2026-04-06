@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ==========================================
echo   CAD Manage - Docker Compose 실행
echo ==========================================
echo.

docker compose up -d
if errorlevel 1 (
    echo 오류: Docker Compose 실행 실패. Docker가 실행 중인지 확인하세요.
    pause
    exit /b 1
)

echo.
echo 컨테이너 시작됨. DB 준비 대기 중...
timeout /t 5 /nobreak >nul

echo 마이그레이션 적용 중...
docker compose exec api alembic upgrade head

echo.
echo ------------------------------------------
echo   API:       http://localhost:8000
echo   업로드 UI: http://localhost:8000/upload
echo   API 문서:  http://localhost:8000/docs
echo ------------------------------------------
echo   로그 보기: docker compose logs -f
echo   중지:     docker compose down
echo.
start http://localhost:8000/upload

pause

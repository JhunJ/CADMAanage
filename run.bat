@echo off
REM 더블클릭 시 cmd /k 로 새 창에서 실행 (창이 바로 꺼지지 않음)
if not "%1"=="_" (
    cmd /k "%~f0" _
    exit /b 0
)

chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 (
    echo 오류: 작업 폴더로 이동할 수 없습니다. [%~dp0]
    goto :error_exit
)

echo.
echo ==========================================
echo   CAD Manage - 실행
echo ==========================================
echo 현재 경로: %CD%
echo.

REM 가상환경 없으면 생성
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] 가상환경 생성 중...
    python -m venv .venv
    if errorlevel 1 (
        echo 오류: Python이 설치되어 있지 않거나 python 명령을 찾을 수 없습니다.
        goto :error_exit
    )
    echo      완료.
) else (
    echo [1/5] 가상환경 확인됨.
)

REM .env 기본값
set "DATABASE_URL=postgresql+psycopg2://caduser:cadpass@localhost:5432/cadmanage"
if exist .env goto :load_env
if exist .env.example goto :copy_env
echo [2/5] .env 없음 - 기본 DB 연결 사용
goto :env_done
:load_env
echo [2/5] .env 로드 중...
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    set "line=!line: =!"
    if "!line!"=="DATABASE_URL" set "DATABASE_URL=%%b"
)
goto :env_done
:copy_env
copy .env.example .env >nul
echo [2/5] .env 생성됨 (기본값)
:env_done

REM 패키지 설치
echo [3/5] 패키지 확인 중...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo 오류: 패키지 설치 실패.
    goto :error_exit
)

REM PostgreSQL 준비 (Docker 또는 로컬 서비스)
echo [4/5] PostgreSQL 준비 중...
net session >nul 2>&1
if not errorlevel 1 (
    set "RUN_AS_ADMIN=1"
) else (
    set "RUN_AS_ADMIN=0"
)
netstat -an 2>nul | findstr ":5432" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    where docker >nul 2>&1
    if not errorlevel 1 (
        echo      Docker PostGIS 시작...
        docker compose up -d postgis 2>nul
        if not errorlevel 1 timeout /t 20 /nobreak >nul
    ) else (
        echo      로컬 PostgreSQL 서비스 시작 시도...
        if "!RUN_AS_ADMIN!"=="1" (
            powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_postgres_services.ps1"
        ) else (
            echo      [관리자 권한 필요] UAC 창에서 예를 눌러 run.bat을 관리자 권한으로 다시 실행합니다.
            powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '_' -Verb RunAs -WorkingDirectory '%~dp0' -Wait"
            exit /b 0
        )
        timeout /t 8 /nobreak >nul
    )
)

REM 마이그레이션 (실패 시 최대 5회 재시도)
echo [5/5] DB 마이그레이션 중...
set "mig_retry=0"
:do_migration
.venv\Scripts\python.exe -m alembic upgrade head
if not errorlevel 1 goto :migration_ok
set /a "mig_retry+=1"
if !mig_retry! geq 5 goto :migration_fail
echo      DB 연결 대기 중. 재시도 !mig_retry!/4...
timeout /t 6 /nobreak >nul
goto :do_migration

:migration_fail
echo.
echo 마이그레이션 실패. PostgreSQL 5432 포트에 연결할 수 없습니다.
echo.
echo 해결: run.bat을 우클릭 후 [관리자 권한으로 실행]으로 다시 시도하세요.
echo       ^(PostgreSQL 서비스 시작에 관리자 권한이 필요합니다^)
echo.
set /p cont="그래도 서버를 시작할까요? (y/N): "
if /i not "!cont!"=="y" goto :error_exit
goto :after_migration

:migration_ok
:after_migration

echo.
echo ------------------------------------------
echo   서버 시작 (로컬):     http://127.0.0.1:8000
echo   서버 시작 (내 PC IP): http://172.23.22.63:8000
echo   업로드 UI: http://127.0.0.1:8000/upload
echo   API 문서:  http://127.0.0.1:8000/docs
echo ------------------------------------------
echo   종료: Ctrl+C
echo.

.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

:normal_exit
echo.
echo 서버가 종료되었습니다.
pause
exit /b 0

:error_exit
echo.
pause
exit /b 1

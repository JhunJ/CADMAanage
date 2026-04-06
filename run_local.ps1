param(
    [string]$ListenHost = "127.0.0.1",
    [switch]$PreparePostgres,
    [int]$MigrationRetries = 1,
    [switch]$FromRunBat
)

# CAD Manage - Local run script (no Docker)
# Usage: .\run_local.ps1 from project root
# run.bat: -ListenHost 0.0.0.0 -PreparePostgres -MigrationRetries 10 -FromRunBat

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Set-Location $ProjectRoot

if ($FromRunBat) {
    try {
        chcp 65001 | Out-Null
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [Console]::OutputEncoding = $utf8
        [Console]::InputEncoding = $utf8
        $OutputEncoding = $utf8
    } catch {}
}

function Read-DotEnvLines {
    param([string]$Path)
    $raw = [System.IO.File]::ReadAllBytes($Path)
    $utf8Strict = New-Object System.Text.UTF8Encoding $false, $true
    try {
        $s = $utf8Strict.GetString($raw)
    } catch {
        $s = [System.Text.Encoding]::GetEncoding(949).GetString($raw)
    }
    return $s -split "`r?`n"
}

function Test-TcpPort {
    param([int]$Port, [string]$HostName = "127.0.0.1")
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        $wait = $iar.AsyncWaitHandle.WaitOne(2000, $false)
        if (-not $wait) { $client.Close(); return $false }
        try {
            $client.EndConnect($iar)
            return $client.Connected
        } finally {
            $client.Close()
        }
    } catch {
        return $false
    }
}

function Get-LanIPv4 {
    try {
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' -and
                $_.IPAddress -notlike '169.254.*'
            } |
            Select-Object -First 1 -ExpandProperty IPAddress
    } catch {
        return $null
    }
}

Write-Host "=== CAD Manage Local Run ===" -ForegroundColor Cyan

# 1) Python check
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Error: Python not found in PATH." -ForegroundColor Red
    exit 1
}
$version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
if (-not $version -or [int]($version.Split('.')[0]) -lt 3 -or [int]($version.Split('.')[1]) -lt 11) {
    Write-Host "Error: Python 3.11+ required." -ForegroundColor Red
    exit 1
}
Write-Host "OK  Python $version" -ForegroundColor Green

# 2) Create venv if missing
$venvPath = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating venv..." -ForegroundColor Yellow
    & python -m venv $venvPath
    if (-not (Test-Path $venvPython)) { Write-Host "venv creation failed." -ForegroundColor Red; exit 1 }
    Write-Host "OK  venv created." -ForegroundColor Green
}

# 3) Copy .env from .env.example if missing
$envPath = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path $envPath) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envPath
    Write-Host "OK  .env created. Edit .env if you need different DB password." -ForegroundColor Green
}

# 4) Load .env (DATABASE_URL etc.) — UTF-8 우선, 실패 시 CP949(메모장 ANSI)
if (Test-Path $envPath) {
    Read-DotEnvLines -Path $envPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match '^([^#=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage"
    Write-Host "Using default DATABASE_URL. Edit .env to change." -ForegroundColor Yellow
}

# 5) Install packages
Write-Host "Installing packages..." -ForegroundColor Yellow
& $venvPython -m pip install -q --upgrade pip
& $venvPython -m pip install -q -r (Join-Path $ProjectRoot "requirements.txt")
Write-Host "OK  Packages ready." -ForegroundColor Green

# 5b) PostgreSQL 준비 (run.bat 전용: Docker PostGIS 또는 로컬 서비스)
# run.bat은 cmd+Windows PowerShell 5.1 조합에서 한글이 깨지므로 FromRunBat일 때 영어 메시지 사용
if ($PreparePostgres) {
    if ($FromRunBat) {
        Write-Host "Checking PostgreSQL (TCP 5432)..." -ForegroundColor Yellow
    } else {
        Write-Host "PostgreSQL(5432) 확인 중..." -ForegroundColor Yellow
    }
    if (-not (Test-TcpPort -Port 5432)) {
        $dockerOk = $false
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            if ($FromRunBat) {
                Write-Host "Port 5432 closed — trying Docker PostGIS..." -ForegroundColor Yellow
            } else {
                Write-Host "5432 미응답 → Docker PostGIS 시작 시도..." -ForegroundColor Yellow
            }
            Push-Location $ProjectRoot
            try {
                & docker compose up -d postgis
                if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
            } catch {
                Write-Host "Docker error: $_" -ForegroundColor Red
            } finally {
                Pop-Location
            }
            if (-not $dockerOk) {
                if ($FromRunBat) {
                    Write-Host "Could not start PostGIS via Docker. Is Docker Desktop running?" -ForegroundColor Red
                } else {
                    Write-Host "Docker로 PostGIS를 켤 수 없습니다. Docker Desktop 실행 여부를 확인하세요." -ForegroundColor Red
                }
            }
        } else {
            if ($FromRunBat) {
                Write-Host "Docker not found — trying local PostgreSQL Windows service..." -ForegroundColor Yellow
            } else {
                Write-Host "docker 명령이 없습니다. 로컬 PostgreSQL 서비스 시작을 시도합니다." -ForegroundColor Yellow
            }
        }

        $deadline = (Get-Date).AddSeconds(90)
        while ((Get-Date) -lt $deadline -and -not (Test-TcpPort -Port 5432)) {
            Start-Sleep -Seconds 3
            if ($FromRunBat) {
                Write-Host "  Waiting for database..." -ForegroundColor Gray
            } else {
                Write-Host "  DB 대기 중..." -ForegroundColor Gray
            }
        }

        if (-not (Test-TcpPort -Port 5432)) {
            $startPg = Join-Path $ProjectRoot "scripts\start_postgres_services.ps1"
            if (Test-Path $startPg) {
                if ($FromRunBat) {
                    Write-Host "Trying to start PostgreSQL service (may need admin)..." -ForegroundColor Yellow
                } else {
                    Write-Host "로컬 PostgreSQL 서비스 기동 시도 (관리자 권한이 있으면 성공할 수 있음)..." -ForegroundColor Yellow
                }
                & powershell -NoProfile -ExecutionPolicy Bypass -File $startPg
                Start-Sleep -Seconds 6
                $deadline2 = (Get-Date).AddSeconds(40)
                while ((Get-Date) -lt $deadline2 -and -not (Test-TcpPort -Port 5432)) {
                    Start-Sleep -Seconds 2
                }
            }
        }
    }
    if (Test-TcpPort -Port 5432) {
        if ($FromRunBat) {
            Write-Host "OK  port 5432 is open" -ForegroundColor Green
        } else {
            Write-Host "OK  5432 포트 응답" -ForegroundColor Green
        }
    } else {
        if ($FromRunBat) {
            Write-Host "Warning: 5432 still closed — migration may fail." -ForegroundColor Yellow
        } else {
            Write-Host "경고: 5432에 아직 연결되지 않습니다. 마이그레이션은 실패할 수 있습니다." -ForegroundColor Yellow
        }
    }
}

# 6) DB migration (재시도)
Write-Host "Running DB migration..." -ForegroundColor Yellow
$migOk = $false
for ($mi = 0; $mi -lt $MigrationRetries; $mi++) {
    & $venvPython -m alembic upgrade head
    if ($LASTEXITCODE -eq 0) {
        $migOk = $true
        break
    }
    if ($mi -lt $MigrationRetries - 1) {
        if ($FromRunBat) {
            Write-Host "  Retry $($mi + 2)/$MigrationRetries (waiting for DB)..." -ForegroundColor Yellow
        } else {
            Write-Host "  재시도 $($mi + 2)/$MigrationRetries (DB 기동·네트워크 대기)..." -ForegroundColor Yellow
        }
        Start-Sleep -Seconds 5
    }
}

if (-not $migOk) {
    Write-Host "Migration failed. Check PostgreSQL and DATABASE_URL in .env." -ForegroundColor Red
    Write-Host "First-time: run .\scripts\init_db.ps1 (enter postgres password). See LOCAL_RUN.md." -ForegroundColor Yellow
    if ($FromRunBat) {
        exit 1
    }
    $cont = Read-Host "Start API server anyway? (y/N)"
    if ($cont -ne "y" -and $cont -ne "Y") { exit 1 }
} else {
    Write-Host "OK  Migration done." -ForegroundColor Green
}

# 7) Start API server
Write-Host ""
Write-Host "Starting API server (Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host "  API:  http://127.0.0.1:8000" -ForegroundColor Gray
if ($ListenHost -eq "0.0.0.0") {
    $lan = Get-LanIPv4
    if ($lan) {
        if ($FromRunBat) {
            Write-Host "  LAN:  http://${lan}:8000  (other devices on same network)" -ForegroundColor Gray
        } else {
            Write-Host "  LAN:  http://${lan}:8000  (같은 네트워크의 다른 기기)" -ForegroundColor Gray
        }
    }
}
Write-Host "  Docs: http://127.0.0.1:8000/docs" -ForegroundColor Gray
Write-Host ""
& $venvPython -m uvicorn app.main:app --reload --host $ListenHost --port 8000

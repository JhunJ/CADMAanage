param(
    [string]$ListenHost = "127.0.0.1",
    [switch]$PreparePostgres,
    [int]$MigrationRetries = 1,
    [switch]$FromRunBat,
    # true: 기동 전 8000 LISTEN 프로세스 종료(일람마스터 등 다른 앱 점유 해제 후 CAD Manage 기동)
    [switch]$FreePort8000
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

# 4) Load .env (DATABASE_URL etc.) ??UTF-8 ?곗꽑, ?ㅽ뙣 ??CP949(硫붾え??ANSI)
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

# 5b) PostgreSQL 以鍮?(run.bat ?꾩슜: Docker PostGIS ?먮뒗 濡쒖뺄 ?쒕퉬??
# run.bat? cmd+Windows PowerShell 5.1 議고빀?먯꽌 ?쒓???源⑥?誘濡?FromRunBat?????곸뼱 硫붿떆吏 ?ъ슜
if ($PreparePostgres) {
    if ($FromRunBat) {
        Write-Host "Checking PostgreSQL (TCP 5432)..." -ForegroundColor Yellow
    } else {
        Write-Host "PostgreSQL(5432) ?뺤씤 以?.." -ForegroundColor Yellow
    }
    if (-not (Test-TcpPort -Port 5432)) {
        $dockerOk = $false
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            if ($FromRunBat) {
                Write-Host "Port 5432 closed ??trying Docker PostGIS..." -ForegroundColor Yellow
            } else {
                Write-Host "5432 誘몄쓳????Docker PostGIS ?쒖옉 ?쒕룄..." -ForegroundColor Yellow
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
                    Write-Host "Docker濡?PostGIS瑜?耳????놁뒿?덈떎. Docker Desktop ?ㅽ뻾 ?щ?瑜??뺤씤?섏꽭??" -ForegroundColor Red
                }
            }
        } else {
            if ($FromRunBat) {
                Write-Host "Docker not found ??trying local PostgreSQL Windows service..." -ForegroundColor Yellow
            } else {
                Write-Host "docker 紐낅졊???놁뒿?덈떎. 濡쒖뺄 PostgreSQL ?쒕퉬???쒖옉???쒕룄?⑸땲??" -ForegroundColor Yellow
            }
        }

        $deadline = (Get-Date).AddSeconds(90)
        while ((Get-Date) -lt $deadline -and -not (Test-TcpPort -Port 5432)) {
            Start-Sleep -Seconds 3
            if ($FromRunBat) {
                Write-Host "  Waiting for database..." -ForegroundColor Gray
            } else {
                Write-Host "  DB ?湲?以?.." -ForegroundColor Gray
            }
        }

        if (-not (Test-TcpPort -Port 5432)) {
            $startPg = Join-Path $ProjectRoot "scripts\start_postgres_services.ps1"
            if (Test-Path $startPg) {
                if ($FromRunBat) {
                    Write-Host "Trying to start PostgreSQL service (may need admin)..." -ForegroundColor Yellow
                } else {
                    Write-Host "濡쒖뺄 PostgreSQL ?쒕퉬??湲곕룞 ?쒕룄 (愿由ъ옄 沅뚰븳???덉쑝硫??깃났?????덉쓬)..." -ForegroundColor Yellow
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
            Write-Host "OK  5432 ?ы듃 ?묐떟" -ForegroundColor Green
        }
    } else {
        if ($FromRunBat) {
            Write-Host "Warning: 5432 still closed ??migration may fail." -ForegroundColor Yellow
        } else {
            Write-Host "寃쎄퀬: 5432???꾩쭅 ?곌껐?섏? ?딆뒿?덈떎. 留덉씠洹몃젅?댁뀡? ?ㅽ뙣?????덉뒿?덈떎." -ForegroundColor Yellow
        }
    }
}

# 6) DB migration (?ъ떆??
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
            Write-Host "  ?ъ떆??$($mi + 2)/$MigrationRetries (DB 湲곕룞쨌?ㅽ듃?뚰겕 ?湲?..." -ForegroundColor Yellow
        }
        Start-Sleep -Seconds 5
    }
}

if (-not $migOk) {
    Write-Host "Migration failed. Check PostgreSQL and DATABASE_URL in .env." -ForegroundColor Red
    if ($FromRunBat) {
        Write-Host "If you see 'password authentication failed' for caduser:" -ForegroundColor Yellow
        Write-Host "  Double-click setup_db.bat once (enter postgres superuser password)." -ForegroundColor Yellow
        Write-Host "  Then run run.bat again." -ForegroundColor Yellow
    } else {
        Write-Host "First-time or wrong DB password: .\scripts\init_db.ps1 or setup_db.bat (postgres password)." -ForegroundColor Yellow
        Write-Host "See LOCAL_RUN.md." -ForegroundColor Yellow
    }
    if ($FromRunBat) {
        exit 1
    }
    $cont = Read-Host "Start API server anyway? (y/N)"
    if ($cont -ne "y" -and $cont -ne "Y") { exit 1 }
} else {
    Write-Host "OK  Migration done." -ForegroundColor Green
}

# 7) Optional: free port 8000 (e.g. another Python app was listening)
if ($FreePort8000) {
    Write-Host ""
    Write-Host "Freeing TCP port 8000 (LISTEN 프로세스 종료)..." -ForegroundColor Yellow
    try {
        $owning = @(Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
        foreach ($opid in $owning) {
            if (-not $opid -or $opid -le 0) { continue }
            $pname = "?"
            try {
                $p = Get-Process -Id $opid -ErrorAction SilentlyContinue
                if ($p) { $pname = $p.ProcessName }
            } catch {}
            Write-Host ("  종료 시도: PID {0} ({1})" -f $opid, $pname) -ForegroundColor Gray
            try {
                Stop-Process -Id $opid -Force -ErrorAction Stop
            } catch {
                Write-Host ("  PID {0} 종료 실패(관리자 권한 필요할 수 있음). kill_port_8000.bat 를 관리자로 실행하세요." -f $opid) -ForegroundColor Red
            }
        }
        Start-Sleep -Seconds 1
    } catch {
        Write-Host "  포트 조회/종료 중 오류: $_" -ForegroundColor Red
    }
}

# 8) Start API server
Write-Host ""
Write-Host "Starting API server (Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host "  API:  http://127.0.0.1:8000" -ForegroundColor Gray
if ($ListenHost -eq "0.0.0.0") {
    $lan = Get-LanIPv4
    if ($lan) {
        if ($FromRunBat) {
            Write-Host "  LAN:  http://${lan}:8000  (other devices on same network)" -ForegroundColor Gray
        } else {
            Write-Host "  LAN:  http://${lan}:8000  (媛숈? ?ㅽ듃?뚰겕???ㅻⅨ 湲곌린)" -ForegroundColor Gray
        }
    }
}
Write-Host "  Docs: http://127.0.0.1:8000/docs" -ForegroundColor Gray
Write-Host ""
& $venvPython -m uvicorn app.main:app --reload --host $ListenHost --port 8000

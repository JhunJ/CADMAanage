# CAD Manage - Local run script (no Docker)
# Usage: .\run_local.ps1 from project root

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Set-Location $ProjectRoot

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

# 4) Load .env (DATABASE_URL etc.)
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match '^([^#=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql+psycopg2://caduser:cadpass@localhost:5432/cadmanage"
    Write-Host "Using default DATABASE_URL. Edit .env to change." -ForegroundColor Yellow
}

# 5) Install packages
Write-Host "Installing packages..." -ForegroundColor Yellow
& $venvPython -m pip install -q -r (Join-Path $ProjectRoot "requirements.txt")
Write-Host "OK  Packages ready." -ForegroundColor Green

# 6) DB migration
Write-Host "Running DB migration..." -ForegroundColor Yellow
& $venvPython -m alembic upgrade head
$alembicOk = ($LASTEXITCODE -eq 0)
if (-not $alembicOk) {
    Write-Host "Migration failed. Check PostgreSQL is running and DATABASE_URL in .env." -ForegroundColor Red
    Write-Host "First-time setup: run .\scripts\init_db.ps1 (see LOCAL_RUN.md)." -ForegroundColor Yellow
    $cont = Read-Host "Start API server anyway? (y/N)"
    if ($cont -ne "y" -and $cont -ne "Y") { exit 1 }
} else {
    Write-Host "OK  Migration done." -ForegroundColor Green
}

# 7) Start API server
Write-Host ""
Write-Host "Starting API server (Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host "  API:  http://localhost:8000" -ForegroundColor Gray
Write-Host "  Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""
& $venvPython -m uvicorn app.main:app --reload --port 8000

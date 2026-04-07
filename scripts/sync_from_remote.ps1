# Pull latest from GitHub and refresh Python deps in .venv (multi-PC workflow).
# Usage (project root): .\scripts\sync_from_remote.ps1
# Optional: -Branch other-branch  -RunMigration

param(
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [switch]$RunMigration
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not (Test-Path (Join-Path $root "app\main.py"))) {
    Write-Host "Error: not CAD Manage project root (app\main.py missing)." -ForegroundColor Red
    exit 1
}

$gitDir = Join-Path $root ".git"
if (-not (Test-Path $gitDir)) {
    Write-Host "Error: .git not found. Clone https://github.com/JhunJ/CADMAanage.git first." -ForegroundColor Red
    exit 1
}

Write-Host "=== sync_from_remote ($Remote / $Branch) ===" -ForegroundColor Cyan
& git -C $root fetch $Remote
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$current = (& git -C $root branch --show-current).Trim()
if ($current -eq $Branch) {
    & git -C $root pull $Remote $Branch --no-edit
} else {
    Write-Host "Branch is '$current' (not '$Branch'). Trying: git pull (upstream)." -ForegroundColor Yellow
    & git -C $root pull --no-edit
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "git pull failed. On main? Try: git checkout $Branch && git pull $Remote $Branch" -ForegroundColor Red
    exit $LASTEXITCODE
}

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Host "Updating pip packages (requirements.txt)..." -ForegroundColor Yellow
    & $venvPy -m pip install -q --upgrade pip
    & $venvPy -m pip install -q -r (Join-Path $root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "OK  pip install done." -ForegroundColor Green
} else {
    Write-Host "No .venv yet — run .\run_local.ps1 or .\scripts\recreate_venv.ps1 then run_local.ps1" -ForegroundColor Yellow
}

if ($RunMigration) {
    if (-not (Test-Path $venvPy)) {
        Write-Host "-RunMigration skipped (no .venv)." -ForegroundColor Yellow
        exit 0
    }
    Write-Host "Running alembic upgrade head..." -ForegroundColor Yellow
    & $venvPy -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Migration failed — check PostgreSQL and .env DATABASE_URL." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK  migrations applied." -ForegroundColor Green
}

Write-Host "Done. Next: .\scripts\check_dev_env.ps1  then  .\run_local.ps1" -ForegroundColor Cyan

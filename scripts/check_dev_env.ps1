# Quick checks before run (another PC / after pull).
# Usage (project root): .\scripts\check_dev_env.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
$ok = $true

function Warn($msg) { Write-Host $msg -ForegroundColor Yellow }
function Bad($msg) { Write-Host $msg -ForegroundColor Red; $script:ok = $false }

Write-Host "=== check_dev_env ===" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $root "app\main.py"))) {
    Bad "Not project root (app\main.py missing)."
    exit 1
}

if (-not (Test-Path (Join-Path $root ".git"))) {
    Bad ".git missing — clone the repo first."
} else {
    $remote = (& git -C $root remote get-url origin 2>$null)
    if (-not $remote) {
        Warn "Git remote 'origin' not set. Add: git remote add origin https://github.com/JhunJ/CADMAanage.git"
    } elseif ($remote -notmatch "CADMAanage") {
        Warn "origin URL: $remote (expected JhunJ/CADMAanage if this is the shared repo)."
    }
    $st = (& git -C $root status -sb 2>$null)
    if ($st) { Write-Host "Git: $st" -ForegroundColor Gray }
}

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Bad "python not in PATH (need Python 3.11+)."
} else {
    $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($ver) {
        $maj, $min = $ver.Split(".")
        if ([int]$maj -lt 3 -or [int]$min -lt 11) {
            Bad "Python $ver — need 3.11+."
        } else {
            Write-Host "OK  Python $ver" -ForegroundColor Green
        }
    }
}

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Warn "No .venv — first run: .\run_local.ps1 (creates venv) or .\scripts\recreate_venv.ps1"
} else {
    Write-Host "OK  .venv present" -ForegroundColor Green
}

$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Warn "No .env — copy .env.example to .env"
} else {
    $raw = Get-Content $envFile -Raw -ErrorAction SilentlyContinue
    if ($raw -match "postgresql\+psycopg2://") {
        Bad ".env uses postgresql+psycopg2:// — change to postgresql+psycopg:// (see .env.example)."
    }
    if ($raw -match "DATABASE_URL\s*=\s*postgresql\+psycopg://") {
        Write-Host "OK  DATABASE_URL driver looks like psycopg (v3)" -ForegroundColor Green
    }
}

if (-not $ok) {
    Write-Host "Fix the items above, then .\run_local.ps1" -ForegroundColor Yellow
    exit 1
}
Write-Host "Looks fine for a local run." -ForegroundColor Green
exit 0

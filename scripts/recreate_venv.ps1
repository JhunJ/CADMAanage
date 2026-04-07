# Remove .venv so run_local.ps1 / pip can rebuild on this machine.
# Usage (from project root): .\scripts\recreate_venv.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root "app\main.py"))) {
    Write-Host "Error: run from CAD Manage project (app\main.py not found under $root)." -ForegroundColor Red
    exit 1
}
$venv = Join-Path $root ".venv"
if (Test-Path $venv) {
    Remove-Item -Recurse -Force $venv
    Write-Host "Removed .venv" -ForegroundColor Green
} else {
    Write-Host "No .venv to remove." -ForegroundColor Yellow
}
Write-Host "Next: cd `"$root`"; .\run_local.ps1" -ForegroundColor Cyan

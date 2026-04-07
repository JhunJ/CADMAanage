# Create PostgreSQL DB and user (caduser / cadmanage / PostGIS). Run once.
# Usage: .\scripts\init_db.ps1 from project root

$ErrorActionPreference = "Stop"

# Find psql: PATH first, then common install paths
$psqlExe = $null
$psqlCmd = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlCmd) {
    $psqlExe = $psqlCmd.Source
} else {
    $pgPaths = @(
        "C:\Program Files\PostgreSQL\18\bin\psql.exe",
        "C:\Program Files\PostgreSQL\17\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files\PostgreSQL\14\bin\psql.exe",
        "C:\Program Files (x86)\PostgreSQL\18\bin\psql.exe",
        "C:\Program Files (x86)\PostgreSQL\17\bin\psql.exe",
        "C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe"
    )
    foreach ($p in $pgPaths) {
        if (Test-Path $p) { $psqlExe = $p; break }
    }
}

if (-not $psqlExe) {
    Write-Host "psql not found. Either:" -ForegroundColor Red
    Write-Host "  1) Add PostgreSQL bin to PATH (e.g. C:\Program Files\PostgreSQL\18\bin)" -ForegroundColor Yellow
    Write-Host "  2) Or install PostgreSQL from https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
    exit 1
}

Write-Host "Creating caduser / cadmanage DB / PostGIS (using $psqlExe)" -ForegroundColor Cyan
Write-Host "Enter postgres user password when prompted." -ForegroundColor Yellow
Write-Host ""

# 1) Create user (ignore if exists)
$createUserSql = 'DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ''caduser'') THEN CREATE USER caduser WITH PASSWORD ''cadpass''; END IF; END $$;'
& $psqlExe -U postgres -h localhost -p 5432 -c $createUserSql
if ($LASTEXITCODE -ne 0) { Write-Host "User creation failed." -ForegroundColor Red; exit 1 }

# 2) Create DB (ignore error if exists)
& $psqlExe -U postgres -h localhost -p 5432 -c "CREATE DATABASE cadmanage OWNER caduser;"
if ($LASTEXITCODE -ne 0) {
    Write-Host "DB create returned error (may already exist). Continuing." -ForegroundColor Yellow
}

# 3) Enable PostGIS in cadmanage
& $psqlExe -U postgres -h localhost -p 5432 -d cadmanage -c "CREATE EXTENSION IF NOT EXISTS postgis;"
if ($LASTEXITCODE -ne 0) { Write-Host "PostGIS extension failed. Is PostGIS installed?" -ForegroundColor Red; exit 1 }

Write-Host "OK  DB ready. Run .\run_local.ps1 from project root." -ForegroundColor Green

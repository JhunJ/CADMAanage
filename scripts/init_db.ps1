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

$pgHost = "127.0.0.1"
$pgPort = "5432"

Write-Host "Creating caduser / cadmanage DB / PostGIS (using $psqlExe)" -ForegroundColor Cyan
Write-Host "Enter postgres superuser password when prompted." -ForegroundColor Yellow
Write-Host ""

# 1) Create role if missing
$createUserSql = 'DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ''caduser'') THEN CREATE USER caduser WITH PASSWORD ''cadpass''; END IF; END $$;'
& $psqlExe -U postgres -h $pgHost -p $pgPort -c $createUserSql
if ($LASTEXITCODE -ne 0) { Write-Host "User step failed." -ForegroundColor Red; exit 1 }

# 2) Always sync password to .env default (existing caduser + wrong password -> fixes auth errors)
& $psqlExe -U postgres -h $pgHost -p $pgPort -c "ALTER USER caduser WITH PASSWORD 'cadpass';"
if ($LASTEXITCODE -ne 0) { Write-Host "ALTER USER caduser failed." -ForegroundColor Red; exit 1 }

# 3) Create DB (ignore error if exists)
& $psqlExe -U postgres -h $pgHost -p $pgPort -c "CREATE DATABASE cadmanage OWNER caduser;"
if ($LASTEXITCODE -ne 0) {
    Write-Host "DB create returned error (may already exist). Continuing." -ForegroundColor Yellow
}

# 4) Ensure owner (DB媛 ?덉쟾???ㅻⅨ ?뚯쑀?먮줈 留뚮뱾?댁쭊 寃쎌슦)
& $psqlExe -U postgres -h $pgHost -p $pgPort -c "ALTER DATABASE cadmanage OWNER TO caduser;"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ALTER DATABASE OWNER skipped or failed (may be OK)." -ForegroundColor Yellow
}

# 5) Enable PostGIS in cadmanage
& $psqlExe -U postgres -h $pgHost -p $pgPort -d cadmanage -c "CREATE EXTENSION IF NOT EXISTS postgis;"
if ($LASTEXITCODE -ne 0) { Write-Host "PostGIS extension failed. Is PostGIS installed?" -ForegroundColor Red; exit 1 }

Write-Host "OK  DB ready. Run run.bat or .\run_local.ps1 from project root." -ForegroundColor Green

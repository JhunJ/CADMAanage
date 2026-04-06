# Start PostgreSQL services (newest first). Run elevated for net start.
$svcs = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'postgresql-x64-' } | Sort-Object Name -Descending
if ($svcs) {
    foreach ($s in $svcs) { net start $s.Name 2>$null }
} else {
    net start postgresql-x64-16 2>$null
    net start postgresql-x64-15 2>$null
}

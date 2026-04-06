# CAD Manage - 설치 + 라이노 실행 (설치_및_라이노_실행.bat 에서만 호출)
# 한 번에: 파일 복사, 프로토콜 등록, Rhino 실행/연결, CadManage 스크립트 실행
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if ($Host.UI.RawUI) { chcp 65001 | Out-Null }

$logPath = Join-Path $env:TEMP "cadmanage_launcher_log.txt"
function Log { param($msg) $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"; "$ts $msg" | Add-Content -Path $logPath -Encoding UTF8 -ErrorAction SilentlyContinue }

# 스크립트가 있는 폴더 = 배치와 같은 폴더
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $PSCommandPath }
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

$targetDir = Join-Path $env:LOCALAPPDATA "CadManageRhino"
$scriptPath = Join-Path $targetDir "cadmanage_rhino.py"

# ---------- 1) 설치 ----------
Write-Host "Installing (copy files, register protocol)..."
Log "Install+Run started. scriptDir=$scriptDir targetDir=$targetDir"
try {
    if (-not (Test-Path $targetDir)) { New-Item -ItemType Directory -Path $targetDir -Force | Out-Null }
    $pySrc = Join-Path $scriptDir "cadmanage_rhino.py"
    if (Test-Path $pySrc) {
        Copy-Item $pySrc -Destination $targetDir -Force
        Log "Copied cadmanage_rhino.py"
    } else {
        Log "WARN: cadmanage_rhino.py not found in $scriptDir"
    }
    foreach ($f in @("launcher.ps1", "launcher_wrapper.bat")) {
        $src = Join-Path $scriptDir $f
        if (Test-Path $src) { Copy-Item $src -Destination $targetDir -Force; Log "Copied $f" }
    }
    $launcherPath = Join-Path $targetDir "launcher_wrapper.bat"
    $regBase = "HKCU:\Software\Classes\cadmanage"
    if (-not (Test-Path $regBase)) { New-Item -Path $regBase -Force | Out-Null }
    Set-ItemProperty -Path $regBase -Name "(Default)" -Value "URL:CAD Manage Rhino" -Type String -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $regBase -Name "EditFlags" -Value 0x00210000 -Type DWord -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path "$regBase\URL Protocol")) { New-Item -Path "$regBase\URL Protocol" -Force | Out-Null }
    Set-ItemProperty -Path "$regBase\URL Protocol" -Name "(Default)" -Value "" -Type String -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path "$regBase\shell\open\command")) { New-Item -Path "$regBase\shell\open\command" -Force | Out-Null }
    Set-ItemProperty -Path "$regBase\shell\open\command" -Name "(Default)" -Value "`"$launcherPath`" `"%1`"" -Type String -Force -ErrorAction SilentlyContinue
    Log "Protocol registered"
    Write-Host "Install OK."
} catch {
    Log "Install error: $_"
    Write-Host "Install error: $_"
    exit 1
}

if (-not (Test-Path $scriptPath)) {
    Write-Host "Script not installed: $scriptPath"
    Log "Script missing after install: $scriptPath"
    exit 1
}

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

# ---------- 2) Rhino 실행 파일 경로 ----------
$rhinoExe = $null
foreach ($p in @(
    "${env:ProgramFiles}\Rhino 8\System\Rhino.exe",
    "${env:ProgramFiles(x86)}\Rhino 8\System\Rhino.exe",
    "$env:LOCALAPPDATA\Programs\Rhino 8\System\Rhino.exe"
)) {
    if (Test-Path $p) { $rhinoExe = $p; break }
}
if (-not $rhinoExe -and (Test-Path "HKCU:\Software\McNeel\Rhinoceros\8.0")) {
    try {
        $installPath = (Get-ItemProperty -Path "HKCU:\Software\McNeel\Rhinoceros\8.0" -Name "InstallPath" -ErrorAction SilentlyContinue).InstallPath
        if ($installPath) {
            $candidate = Join-Path $installPath "System\Rhino.exe"
            if (Test-Path $candidate) { $rhinoExe = $candidate }
        }
    } catch {}
}
if (-not $rhinoExe) {
    Write-Host "Rhino 8 not found. Install Rhino and run this again."
    Log "Rhino exe not found"
    exit 1
}

# ---------- 3) Always start Rhino with /runscript (ignore if already running) ----------
Write-Host "Starting Rhino with CadManage script..."
Log "Starting Rhino with /runscript"
$scriptPathArg = $scriptPath
if ($scriptPath -match "\s") { $scriptPathArg = "`"$scriptPath`"" }
$runScriptCmd = "_-RunPythonScript ($scriptPathArg)"
try {
    Start-Process -FilePath $rhinoExe -ArgumentList "/nosplash", "/runscript=`"$runScriptCmd`""
    Log "Start-Process with /runscript OK"
    Write-Host "Rhino is starting. CadManage window should appear in Rhino."
    Write-Host "If it does not, close Rhino and run this BAT again."
} catch {
    Write-Host "Rhino start failed: $_"
    Log "Start-Process failed: $_"
    exit 1
}
exit 0

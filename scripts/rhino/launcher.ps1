# CAD Manage - cadmanage:// URL 프로토콜 런처
# 웹 "라이노에서 열기" 클릭 시: launch.json 기록 후, Rhino가 이미 떠 있으면 그쪽에 연동 / 없으면 Rhino를 스크립트로 기동해 DB에서 객체 로드
param([Parameter(Mandatory=$false)][string]$Url)
if (-not $Url -and $args.Count -gt 0) { $Url = $args[0] }

$logPath = Join-Path $env:TEMP "cadmanage_launcher_log.txt"
function Log { param($msg) $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"; "$ts $msg" | Add-Content -Path $logPath -Encoding UTF8 }
Log "Launcher started. Args: $($args -join ' | ')"

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

if (-not $Url -or $Url -notmatch "^cadmanage://") {
    Log "ERROR: Invalid or missing URL: $Url"
    [System.Windows.Forms.MessageBox]::Show("cadmanage:// URL이 전달되지 않았습니다.`n로그: $logPath", "CAD Manage") | Out-Null
    exit 1
}
Log "URL: $Url"

# 쿼리 문자열 파싱 (project_id, commit_id, api_base)
$queryPart = $Url -replace "^cadmanage://open\?", ""
$params = @{}
foreach ($pair in $queryPart -split "&") {
    if ($pair -match "^([^=]+)=(.*)$") {
        $key = $matches[1]
        $val = [System.Uri]::UnescapeDataString($matches[2])
        $params[$key] = $val
    }
}
$project_id = $params["project_id"]
$commit_id = $params["commit_id"]
$api_base = ($params["api_base"] -replace "/$", "")
if (-not $api_base) {
    Log "ERROR: Missing api_base"
    [System.Windows.Forms.MessageBox]::Show("URL에 api_base(서버 주소)가 필요합니다.", "CAD Manage") | Out-Null
    exit 1
}

# 항상 launch.json 기록. api_base 필수, project_id/commit_id는 선택(있으면 기록).
$launchPath = Join-Path $env:TEMP "cadmanage_launch.json"
$launchObj = @{ api_base = $api_base }
if ($project_id) { $launchObj["project_id"] = [int]$project_id }
if ($commit_id) { $launchObj["commit_id"] = [int]$commit_id }
$jsonLine = $launchObj | ConvertTo-Json -Compress
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($launchPath, $jsonLine, $utf8NoBom)
Log "Launch file written: $launchPath (json length=$($jsonLine.Length), preview: $($jsonLine.Substring(0, [Math]::Min(80, $jsonLine.Length)))...)"

$scriptPath = Join-Path $env:LOCALAPPDATA "CadManageRhino\cadmanage_rhino.py"

# Rhino 프로세스가 이미 실행 중인지 확인 (프로세스명은 Rhino 또는 Rhinoceros)
$rhinoRunning = Get-Process -Name "Rhino" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $rhinoRunning) {
    $rhinoRunning = Get-Process -Name "Rhinoceros" -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($rhinoRunning) {
    Log "Rhino already running - running script in existing instance"
    $scriptRan = $false
    # 1) COM 우선 (StartScriptServer 불필요, 기존 인스턴스에서 바로 실행)
    try {
        $rhinoType = [Type]::GetTypeFromProgID("Rhino.Application")
        if ($rhinoType) {
            $rhinoApp = [System.Activator]::CreateInstance($rhinoType)
            $rhinoApp.RunScript(0, "_-RunPythonScript ($scriptPath)", "CadManage", $false)
            $scriptRan = $true
            Log "Script run via COM"
        }
    } catch { Log "COM RunScript failed: $_" }
    # 2) COM 실패 시 rhinocode (Rhino 8.11+, StartScriptServer 필요)
    if (-not $scriptRan) {
        $rhinoDir = (Get-Item $rhinoRunning.Path -ErrorAction SilentlyContinue).DirectoryName
        if ($rhinoDir) {
            $rhinocodeExe = Join-Path $rhinoDir "rhinocode.exe"
            if (Test-Path $rhinocodeExe) {
                try {
                    $proc = Start-Process -FilePath $rhinocodeExe -ArgumentList "script", $scriptPath -Wait -PassThru -NoNewWindow -ErrorAction Stop
                    if ($proc.ExitCode -eq 0) { $scriptRan = $true; Log "Script run via rhinocode" }
                } catch { Log "rhinocode failed: $_" }
            }
        }
    }
    if (-not $scriptRan) { Log "Could not run script in existing Rhino; activating window only" }
    try {
        $null = [System.Reflection.Assembly]::LoadWithPartialName("Microsoft.VisualBasic")
        [Microsoft.VisualBasic.Interaction]::AppActivate($rhinoRunning.Id) | Out-Null
    } catch {
        try {
            Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win32 { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }
"@ -ErrorAction SilentlyContinue
            if ($rhinoRunning.MainWindowHandle -ne [IntPtr]::Zero) {
                [Win32]::SetForegroundWindow($rhinoRunning.MainWindowHandle) | Out-Null
            }
        } catch {}
    }
    exit 0
}

# Rhino가 없으면: launch.json은 이미 기록됨 → Rhino를 스크립트로 기동 (스크립트가 launch.json을 읽고 DB에서 객체 로드)
$rhinoExe = $null
foreach ($p in @(
    "${env:ProgramFiles}\Rhino 8\System\Rhino.exe",
    "${env:ProgramFiles(x86)}\Rhino 8\System\Rhino.exe",
    "$env:LOCALAPPDATA\Programs\Rhino 8\System\Rhino.exe"
)) {
    if (Test-Path $p) { $rhinoExe = $p; break }
}
if (-not $rhinoExe -and (Test-Path "HKCU:\Software\McNeel\Rhinoceros\8.0")) {
    $installPath = (Get-ItemProperty -Path "HKCU:\Software\McNeel\Rhinoceros\8.0" -Name "InstallPath" -ErrorAction SilentlyContinue).InstallPath
    if ($installPath) {
        $candidate = Join-Path $installPath "System\Rhino.exe"
        if (Test-Path $candidate) { $rhinoExe = $candidate }
    }
}
if (-not $rhinoExe) {
    Log "ERROR: Rhino 8 not found"
    [System.Windows.Forms.MessageBox]::Show("Rhino 8을 찾을 수 없습니다. 설치 후 프로토콜을 다시 등록하세요.`n로그: $logPath", "CAD Manage") | Out-Null
    exit 1
}
if (-not (Test-Path $scriptPath)) {
    Log "WARNING: Script not found at $scriptPath - run install_cadmanage_protocol.ps1 first"
    [System.Windows.Forms.MessageBox]::Show("CadManage 연동 스크립트가 없습니다.`n설치_및_라이노_실행.bat 또는 install_cadmanage_protocol.ps1을 먼저 실행하세요.`n로그: $logPath", "CAD Manage") | Out-Null
    exit 1
}
$runScriptValue = "_-RunPythonScript ($scriptPath)"
Log "Starting Rhino with script: $runScriptValue"
try {
    Start-Process -FilePath $rhinoExe -ArgumentList "/nosplash", "/runscript=`"$runScriptValue`""
    Log "Rhino started; script will read launch.json and load from DB"
} catch {
    Log "ERROR Rhino Start-Process: $_"
    [System.Windows.Forms.MessageBox]::Show("Rhino 실행 실패: $_`n로그: $logPath", "CAD Manage") | Out-Null
    exit 1
}

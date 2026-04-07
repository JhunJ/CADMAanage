# CAD Manage - Rhino 실행 (기존 인스턴스 있으면 그쪽에서 스크립트 실행, 없으면 새로 기동)
# 설치_및_라이노_실행.bat 에서 호출
$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $env:LOCALAPPDATA "CadManageRhino\cadmanage_rhino.py"
if (-not (Test-Path $scriptPath)) {
    Write-Host "스크립트가 없습니다: $scriptPath"
    Write-Host "위 설치 단계가 완료되었는지 확인하세요."
    exit 1
}

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

$rhinoRunning = Get-Process -Name "Rhino" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $rhinoRunning) {
    $rhinoRunning = Get-Process -Name "Rhinoceros" -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($rhinoRunning) {
    $scriptRan = $false
    # COM 우선 (StartScriptServer 불필요)
    try {
        $rhinoType = [Type]::GetTypeFromProgID("Rhino.Application")
        if ($rhinoType) {
            $rhinoApp = [System.Activator]::CreateInstance($rhinoType)
            $rhinoApp.RunScript(0, "_-RunPythonScript ($scriptPath)", "CadManage", $false)
            $scriptRan = $true
        }
    } catch {}
    if (-not $scriptRan) {
        $rhinoDir = (Get-Item $rhinoRunning.Path -ErrorAction SilentlyContinue).DirectoryName
        if ($rhinoDir) {
            $rhinocodeExe = Join-Path $rhinoDir "rhinocode.exe"
            if (Test-Path $rhinocodeExe) {
                try {
                    $proc = Start-Process -FilePath $rhinocodeExe -ArgumentList "script", $scriptPath -Wait -PassThru -NoNewWindow -ErrorAction Stop
                    if ($proc.ExitCode -eq 0) { $scriptRan = $true }
                } catch {}
            }
        }
    }
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

# Rhino 미실행 → 먼저 Rhino만 기동한 뒤 COM으로 스크립트 실행 (rhinocode /runscript 오류 회피)
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
    Write-Host "Rhino 8을 찾을 수 없습니다. 설치 후 라이노를 실행한 뒤 메뉴에서 [1] 가져오기로 DB 불러오기를 사용하세요."
    exit 1
}

# /runscript 사용 시 rhinocode가 'no running instance' 오류를 내는 경우가 있으므로, Rhino만 띄운 뒤 COM으로 스크립트 실행
Start-Process -FilePath $rhinoExe -ArgumentList "/nosplash"
$maxWait = 30
$waited = 0
$rhinoProcess = $null
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 2
    $waited += 2
    $rhinoProcess = Get-Process -Name "Rhino" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $rhinoProcess) { $rhinoProcess = Get-Process -Name "Rhinoceros" -ErrorAction SilentlyContinue | Select-Object -First 1 }
    if ($rhinoProcess) { break }
}
if (-not $rhinoProcess) {
    Write-Host "Rhino가 시작되었을 수 있습니다. 창이 보이면 메뉴에서 [1] 가져오기로 DB 불러오기를 사용하세요."
    exit 0
}

# COM으로 스크립트 실행
$scriptRan = $false
for ($i = 0; $i -lt 5; $i++) {
    Start-Sleep -Seconds 1
    try {
        $rhinoType = [Type]::GetTypeFromProgID("Rhino.Application")
        if ($rhinoType) {
            $rhinoApp = [System.Activator]::CreateInstance($rhinoType)
            $rhinoApp.RunScript(0, "_-RunPythonScript ($scriptPath)", "CadManage", $false)
            $scriptRan = $true
            break
        }
    } catch {}
}
if (-not $scriptRan) {
    Write-Host "CadManage 스크립트 자동 실행에 실패했습니다. Rhino가 열리면 메뉴에서 [1] 가져오기를 선택하세요."
}

try {
    $null = [System.Reflection.Assembly]::LoadWithPartialName("Microsoft.VisualBasic")
    [Microsoft.VisualBasic.Interaction]::AppActivate($rhinoProcess.Id) | Out-Null
} catch {
    try {
        Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win32 { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }
"@ -ErrorAction SilentlyContinue
        if ($rhinoProcess.MainWindowHandle -ne [IntPtr]::Zero) {
            [Win32]::SetForegroundWindow($rhinoProcess.MainWindowHandle) | Out-Null
        }
    } catch {}
}
exit 0

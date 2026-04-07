# CAD Manage - cadmanage:// protocol installer (run once)
# Run from project root: .\scripts\rhino\install_cadmanage_protocol.ps1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if ($Host.UI.RawUI) { chcp 65001 | Out-Null }

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetDir = Join-Path $env:LOCALAPPDATA "CadManageRhino"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

Copy-Item (Join-Path $scriptDir "cadmanage_rhino.py") -Destination $targetDir -Force
Copy-Item (Join-Path $scriptDir "launcher.ps1") -Destination $targetDir -Force
Copy-Item (Join-Path $scriptDir "launcher_wrapper.bat") -Destination $targetDir -Force

$launcherPath = Join-Path $targetDir "launcher_wrapper.bat"
$regBase = "HKCU:\Software\Classes\cadmanage"
if (-not (Test-Path $regBase)) { New-Item -Path $regBase -Force | Out-Null }
Set-ItemProperty -Path $regBase -Name "(Default)" -Value "URL:CAD Manage Rhino" -Type String -Force
# Edge needs EditFlags to show "Open with" prompt for custom protocols
Set-ItemProperty -Path $regBase -Name "EditFlags" -Value 0x00210000 -Type DWord -Force
if (-not (Test-Path "$regBase\URL Protocol")) { New-Item -Path "$regBase\URL Protocol" -Force | Out-Null }
Set-ItemProperty -Path "$regBase\URL Protocol" -Name "(Default)" -Value "" -Type String -Force
if (-not (Test-Path "$regBase\shell\open\command")) {
    New-Item -Path "$regBase\shell\open\command" -Force | Out-Null
}
$cmd = "`"$launcherPath`" `"%1`""
Set-ItemProperty -Path "$regBase\shell\open\command" -Name "(Default)" -Value $cmd -Type String -Force

Write-Host "CAD Manage Rhino - Install OK"
Write-Host "  Path: $targetDir"
Write-Host "  Next: Web -> select project/version -> click 'Open in Rhino' -> allow when browser asks."
Write-Host "  Log file if issues: $env:TEMP\cadmanage_launcher_log.txt"

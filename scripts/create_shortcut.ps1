param(
    [string]$TargetPath = "",
    [string]$ShortcutPath = ""
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $TargetPath) {
    $TargetPath = Join-Path $Root "dist\Damien\Damien.exe"
}
if (-not $ShortcutPath) {
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $Desktop "Damien.lnk"
}

if (-not (Test-Path -LiteralPath $TargetPath)) {
    Write-Host "Missing packaged app: $TargetPath"
    Write-Host "Build it first with: .\scripts\build.ps1"
    exit 1
}

$ResolvedTarget = (Resolve-Path -LiteralPath $TargetPath).Path
$WorkingDirectory = Split-Path -Parent $ResolvedTarget
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ResolvedTarget
$Shortcut.WorkingDirectory = $WorkingDirectory
$Shortcut.IconLocation = "$ResolvedTarget,0"
$Shortcut.Description = "Damien local Windows assistant"
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"

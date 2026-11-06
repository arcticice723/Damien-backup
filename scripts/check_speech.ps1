$ErrorActionPreference = "Continue"

$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
    Write-Host "Missing Damien .venv. Run .\scripts\setup.ps1 first."
    exit 1
}

.\.venv\Scripts\python.exe .\scripts\check_speech.py

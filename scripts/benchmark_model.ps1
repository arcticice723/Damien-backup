$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
    Write-Host "Missing Damien .venv. Run .\scripts\setup.ps1 first."
    exit 1
}

.\.venv\Scripts\python.exe .\scripts\benchmark_model.py @args

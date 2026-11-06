$ErrorActionPreference = "Stop"

$env:PYTHONPATH = ".\src"
if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
    Write-Host "Missing Damien .venv. Run .\scripts\setup.ps1 first."
    exit 1
}

.\.venv\Scripts\python.exe -m unittest discover -s tests

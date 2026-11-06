$ErrorActionPreference = "Stop"

$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "Setting up Damien locally in this folder..."

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.13 for Windows, then rerun this script."
}

if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating .venv with Python 3.13..."
    py -3.13 -m venv .venv
}

Write-Host "Using Python:"
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.version)"

Write-Host "Installing Damien dependencies into .venv..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete. Run Damien with:"
Write-Host ".\scripts\run.ps1"

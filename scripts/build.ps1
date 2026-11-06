$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$AssetsDir = Join-Path $Root "assets"
$Icon = Join-Path $AssetsDir "damien.ico"
$DistApp = Join-Path $Root "dist\Damien"
$RequiredSpeechAssets = @(
    "faster_whisper\assets\silero_vad_v6.onnx"
)

$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Missing Damien .venv. Run .\scripts\setup.ps1 first."
    exit 1
}

Write-Host "Installing packaging dependencies into project .venv..."
& $Python -m pip install -r $Requirements pyinstaller

if (-not (Test-Path -LiteralPath $Icon)) {
    Write-Host "Creating placeholder app icon at assets\damien.ico..."
    New-Item -ItemType Directory -Force -Path $AssetsDir | Out-Null
    $IconScript = @'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

icon_path = Path("assets/damien.ico")
icon_path.parent.mkdir(parents=True, exist_ok=True)
image = Image.new("RGBA", (256, 256), (16, 20, 24, 255))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((28, 28, 228, 228), radius=44, fill=(31, 122, 77, 255))
draw.ellipse((78, 64, 178, 164), fill=(244, 247, 250, 255))
draw.rectangle((116, 150, 140, 196), fill=(244, 247, 250, 255))
draw.rectangle((88, 192, 168, 212), fill=(244, 247, 250, 255))
try:
    font = ImageFont.truetype("arial.ttf", 62)
except OSError:
    font = ImageFont.load_default()
draw.text((108, 80), "D", fill=(16, 20, 24, 255), font=font)
image.save(icon_path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
'@
    Push-Location $Root
    try {
        $IconScript | & $Python -
    }
    finally {
        Pop-Location
    }
}

Write-Host "Building Damien.exe..."
Push-Location $Root
try {
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name Damien `
        --icon $Icon `
        --paths (Join-Path $Root "src") `
        --collect-data faster_whisper `
        --collect-all piper `
        --collect-all sounddevice `
        --collect-all pystray `
        --collect-all PIL `
        --hidden-import faster_whisper `
        --hidden-import piper `
        --hidden-import pyttsx3 `
        (Join-Path $Root "main.py")
}
finally {
    Pop-Location
}

Write-Host "Copying editable runtime files beside Damien.exe..."
New-Item -ItemType Directory -Force -Path $DistApp | Out-Null
foreach ($dir in @("config", "approved_documents", "logs", "history", "memory", "assets")) {
    $source = Join-Path $Root $dir
    $target = Join-Path $DistApp $dir
    if (Test-Path -LiteralPath $source) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force -ErrorAction SilentlyContinue
    }
    else {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
    }
}

Write-Host "Verifying packaged speech assets..."
foreach ($asset in $RequiredSpeechAssets) {
    $assetPath = Join-Path (Join-Path $DistApp "_internal") $asset
    if (-not (Test-Path -LiteralPath $assetPath)) {
        throw "Missing packaged speech asset: $assetPath"
    }
}

Write-Host "Build complete: $DistApp\Damien.exe"
Write-Host "Create a desktop shortcut with: .\scripts\create_shortcut.ps1"

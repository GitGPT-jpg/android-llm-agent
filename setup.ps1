# ============================================================
#  Android LLM Agent — one-command environment setup
#  Usage: Right-click → Run with PowerShell (as Administrator)
# ============================================================

$ErrorActionPreference = "Stop"
$BOT_DIR   = $PSScriptRoot
$TOOLS_DIR = "$BOT_DIR\tools"

New-Item -ItemType Directory -Force -Path $TOOLS_DIR | Out-Null

Write-Host "`n[1/3] Downloading ADB platform-tools ..." -ForegroundColor Cyan
$adbZip = "$TOOLS_DIR\platform-tools.zip"
if (-not (Test-Path "$TOOLS_DIR\platform-tools\adb.exe")) {
    Invoke-WebRequest -Uri "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" `
        -OutFile $adbZip -UseBasicParsing
    Expand-Archive -Path $adbZip -DestinationPath $TOOLS_DIR -Force
    Remove-Item $adbZip
    Write-Host "  ADB downloaded." -ForegroundColor Green
} else {
    Write-Host "  ADB already present, skipping." -ForegroundColor Yellow
}

Write-Host "`n[2/3] Downloading scrcpy ..." -ForegroundColor Cyan
$scrcpyDir = "$TOOLS_DIR\scrcpy"
if (-not (Test-Path "$scrcpyDir\scrcpy.exe")) {
    $release = Invoke-RestMethod "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
    $asset   = $release.assets | Where-Object { $_.name -like "*win64*" } | Select-Object -First 1
    if ($asset) {
        $scrcpyZip = "$TOOLS_DIR\scrcpy.zip"
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $scrcpyZip -UseBasicParsing
        Expand-Archive -Path $scrcpyZip -DestinationPath $scrcpyDir -Force
        Remove-Item $scrcpyZip
        Write-Host "  scrcpy downloaded." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Could not auto-download scrcpy." -ForegroundColor Red
        Write-Host "  Download manually from https://github.com/Genymobile/scrcpy/releases (win64) to $scrcpyDir" -ForegroundColor Red
    }
} else {
    Write-Host "  scrcpy already present, skipping." -ForegroundColor Yellow
}

Write-Host "`n[3/3] Installing Python dependencies ..." -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: Python not found. Please install Python 3.11+." -ForegroundColor Red
    exit 1
}
Set-Location $BOT_DIR
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
Write-Host "  Python dependencies installed." -ForegroundColor Green

# Add ADB and scrcpy to PATH for this session only
$env:PATH = "$TOOLS_DIR\platform-tools;$scrcpyDir;$env:PATH"

# Bootstrap config files if not present
if (-not (Test-Path "$BOT_DIR\.env")) {
    Copy-Item "$BOT_DIR\.env.example" "$BOT_DIR\.env"
    Write-Host "`n  Created .env from template — edit it and add your API keys." -ForegroundColor Yellow
}
if (-not (Test-Path "$BOT_DIR\config\device.json")) {
    Copy-Item "$BOT_DIR\config\device.example.json" "$BOT_DIR\config\device.json"
    Write-Host "  Created config/device.json from template — calibrate coordinates for your device." -ForegroundColor Yellow
}

Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "  Setup complete! Next steps:" -ForegroundColor Green
Write-Host "  1. Edit .env and set your API keys"
Write-Host "  2. Enable USB debugging on your Android device and connect via USB"
Write-Host "  3. Run:  .\tools\platform-tools\adb.exe devices"
Write-Host "  4. Authorize the connection prompt on your phone"
Write-Host "  5. Calibrate screen coordinates:  python scripts\adb_helper.py"
Write-Host "  6. Start the agent:  python main.py"
Write-Host "=============================================" -ForegroundColor Cyan

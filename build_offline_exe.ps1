param(
    [string]$PythonExe = "python",
    [string]$AppName = "DocToMdConverter"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:KMP_DUPLICATE_LIB_OK = "TRUE"
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"

Write-Host "Installing build dependencies..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r requirements.txt
& $PythonExe -m pip install pyinstaller

Write-Host "Preparing bundled OCR assets..."
& $PythonExe scripts\prepare_offline_assets.py

if (Test-Path build) {
    Remove-Item -Recurse -Force build
}
if (Test-Path "dist\$AppName") {
    Remove-Item -Recurse -Force "dist\$AppName"
}

Write-Host "Building offline one-folder executable..."
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name $AppName `
    --paths . `
    --runtime-hook pyi_runtime_hook.py `
    --collect-all paddle `
    --collect-all paddleocr `
    --collect-all paddlex `
    --collect-all tkinterdnd2 `
    --collect-submodules win32com `
    --hidden-import win32com `
    --hidden-import win32com.client `
    --hidden-import pythoncom `
    --hidden-import pywintypes `
    --hidden-import win32timezone `
    --add-data "src\config\ocr_corrections.json;src\config" `
    --add-data "offline_assets\paddle_models;runtime_assets\paddle_models" `
    --add-data "tools\hwp2md.exe;tools" `
    src\main.py

Write-Host ""
Write-Host "Build completed."
Write-Host "Output folder: dist\$AppName"
Write-Host "Executable  : dist\$AppName\$AppName.exe"


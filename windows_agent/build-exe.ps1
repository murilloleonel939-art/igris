# Compila IgrisAgent.exe en Windows con PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --noconsole --collect-all docx --collect-all openpyxl --collect-all pptx --collect-all lxml --hidden-import websockets --hidden-import tkinter --hidden-import _tkinter --name IgrisAgent agent.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller no pudo generar IgrisAgent.exe" }
Write-Host "Creado: $root\dist\IgrisAgent.exe" -ForegroundColor Green

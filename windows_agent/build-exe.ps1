# Compila IgrisAgent.exe en Windows con PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --noconsole --collect-all docx --collect-all openpyxl --collect-all pptx --collect-all lxml --collect-all XlsxWriter --hidden-import tkinter --hidden-import _tkinter --name IgrisAgent agent.py
Write-Host "Creado: $root\dist\IgrisAgent.exe" -ForegroundColor Green

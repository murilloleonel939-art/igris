# Compila IgrisAgent.exe en Windows con PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name IgrisAgent agent.py
Write-Host "Creado: $root\dist\IgrisAgent.exe" -ForegroundColor Green

# Compila IgrisAgent.exe en Windows con PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
py -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --name IgrisAgent agent.py
Write-Host "Creado: $root\dist\IgrisAgent.exe" -ForegroundColor Green

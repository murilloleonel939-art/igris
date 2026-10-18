# Instalador del agente local de IGRIS para Windows.
# Ejecutar en PowerShell con: powershell -ExecutionPolicy Bypass -File .\install.ps1
$ErrorActionPreference = "Stop"

$baseUrl = "https://raw.githubusercontent.com/murilloleonel939-art/igris/main/windows_agent"
$installDir = Join-Path $env:LOCALAPPDATA "IGRIS\agent"
$agentPath = Join-Path $installDir "agent.py"
$launcherPath = Join-Path $installDir "start-agent.ps1"
$configPath = Join-Path $installDir "config.ps1"
$taskName = "IGRIS Local Agent"

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) {
    throw "No se encontró Python. Instala Python 3.11 o superior desde https://www.python.org/downloads/windows/ y vuelve a ejecutar este instalador."
}
$pythonCommand = $python.Source

$url = Read-Host "URL WebSocket de IGRIS (ejemplo: wss://tu-dominio.com/api/device/ws)"
$token = Read-Host "NODE_TOKEN del backend"
if ([string]::IsNullOrWhiteSpace($url) -or [string]::IsNullOrWhiteSpace($token)) {
    throw "La URL y el NODE_TOKEN son obligatorios."
}
$url = $url.Trim().TrimEnd('/')
if (-not $url.StartsWith("wss://")) {
    throw "La URL debe comenzar con wss://"
}

Invoke-WebRequest "$baseUrl/agent.py" -OutFile $agentPath
& $pythonCommand -m pip install --user "websockets>=12,<16"

@"
`$env:IGRIS_DEVICE_URL = '$($url.Replace("'", "''"))'
`$env:NODE_TOKEN = '$($token.Replace("'", "''"))'
& '$($pythonCommand.Replace("'", "''"))' '$($agentPath.Replace("'", "''"))'
"@ | Set-Content -Encoding UTF8 $launcherPath

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcherPath`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host ""
Write-Host "IGRIS quedó instalado y arrancará al iniciar sesión." -ForegroundColor Green
Write-Host "Archivos instalados en: $installDir"
Write-Host "Para detenerlo: Stop-ScheduledTask -TaskName '$taskName'"
Write-Host "Para desinstalarlo: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false; Remove-Item '$installDir' -Recurse -Force"

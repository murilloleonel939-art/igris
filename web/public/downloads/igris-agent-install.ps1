# Instalador autocontenido del agente local de IGRIS para Windows.
# Ejecutar con: powershell -ExecutionPolicy Bypass -File .\install.ps1
$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:LOCALAPPDATA "IGRIS\agent"
$agentPath = Join-Path $installDir "agent.py"
$launcherPath = Join-Path $installDir "start-agent.ps1"
$taskName = "IGRIS Local Agent"

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "No se encontró Python ni winget. Instala Python 3.11 o superior desde https://www.python.org/downloads/windows/ y vuelve a ejecutar este instalador."
    }
    Write-Host "Python no está instalado. Instalándolo con winget..." -ForegroundColor Yellow
    & $winget.Source install --id Python.Python.3.12 --exact --scope user --accept-source-agreements --accept-package-agreements
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $python) {
        throw "Python se instaló, pero Windows aún no lo encuentra. Cierra y vuelve a abrir PowerShell y ejecuta el instalador otra vez."
    }
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

$agentSource = @'
"""Agente Windows de IGRIS. Ejecutar al iniciar sesión, sin permisos de administrador."""
from __future__ import annotations

import asyncio
import ctypes
import json
import os
import subprocess
import time
import webbrowser
from urllib.parse import urlparse

import websockets


ALLOWED_HOSTS = {"www.google.com", "google.com", "www.youtube.com", "youtube.com"}

PROGRAMS = {
    "chrome": os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
}


def execute(command: dict) -> dict:
    action = command.get("action")
    params = command.get("params") or {}
    if action == "chrome_open_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            return {"ok": False, "error": "URL no permitida"}
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            return {"ok": False, "error": "Sitio no autorizado"}
        chrome = PROGRAMS["chrome"]
        if os.path.isfile(chrome):
            subprocess.Popen([chrome, url], shell=False)
        else:
            webbrowser.get("windows-default").open(url)
        return {"ok": True}
    if action == "chrome_play_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://www.youtube.com/watch?"):
            return {"ok": False, "error": "Video de YouTube no permitido"}
        chrome = PROGRAMS["chrome"]
        if os.path.isfile(chrome):
            subprocess.Popen([chrome, url], shell=False)
        else:
            webbrowser.get("windows-default").open(url)
        # autoplay=1 inicia el video; no enviamos una tecla adicional que pudiera pausarlo.
        time.sleep(3)
        return {"ok": True, "url": url, "message": "Video abierto con reproducción solicitada."}
    if action.startswith("media_"):
        if action not in {"media_play_pause", "media_next", "media_previous"}:
            return {"ok": False, "error": "Acción no permitida"}
        vk = {"media_play_pause": 0xB3, "media_next": 0xB0, "media_previous": 0xB1}[action]
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True}
    if action.startswith("volume_"):
        if action not in {"volume_up", "volume_down", "volume_mute"}:
            return {"ok": False, "error": "Acción no permitida"}
        vk = {"volume_up": 0xAF, "volume_down": 0xAE, "volume_mute": 0xAD}[action]
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True}
    if action == "launch_program":
        program = params.get("program")
        path = PROGRAMS.get(program)
        if not path:
            return {"ok": False, "error": "Programa no autorizado"}
        subprocess.Popen([path], shell=False)
        return {"ok": True}
    return {"ok": False, "error": "Acción desconocida"}


async def main() -> None:
    url = os.environ["IGRIS_DEVICE_URL"]
    token = os.environ["NODE_TOKEN"]
    while True:
        try:
            async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {token}"}, ping_interval=20, ping_timeout=20) as ws:
                print("Agente local IGRIS conectado")
                while True:
                    raw = await ws.recv()
                    command = json.loads(raw)
                    result = await asyncio.to_thread(execute, command)
                    await ws.send(json.dumps({"id": command.get("id"), "result": result}))
        except Exception as exc:
            print(f"Agente desconectado: {exc}; reintentando")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
'@

$agentSource | Set-Content -Encoding UTF8 $agentPath
& $pythonCommand -m pip install --user "websockets>=12,<16"

$escapedUrl = $url.Replace("'", "''")
$escapedToken = $token.Replace("'", "''")
$escapedPython = $pythonCommand.Replace("'", "''")
$escapedAgent = $agentPath.Replace("'", "''")
@"
`$env:IGRIS_DEVICE_URL = '$escapedUrl'
`$env:NODE_TOKEN = '$escapedToken'
& '$escapedPython' '$escapedAgent'
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

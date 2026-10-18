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
import base64
import ctypes
import json
import os
import struct
import subprocess
import time
import webbrowser
import socket
import zlib
from pathlib import Path
from urllib.parse import quote, urlparse

import websockets


ALLOWED_HOSTS = {"www.google.com", "google.com", "www.youtube.com", "youtube.com", "open.spotify.com", "www.spotify.com", "store.steampowered.com", "www.bing.com"}

def enumerate_programs() -> list[dict[str, str]]:
    """Obtiene aplicaciones ejecutables desde accesos directos del menú Inicio."""
    roots = [
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    found: dict[str, dict[str, str]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for shortcut in root.rglob("*"):
                if shortcut.suffix.lower() not in {".lnk", ".exe"} or not shortcut.is_file():
                    continue
                name = shortcut.stem.strip()
                if name and name.lower() not in found:
                    found[name.lower()] = {"name": name, "path": str(shortcut)}
        except (OSError, PermissionError):
            continue
    return sorted(found.values(), key=lambda item: item["name"].lower())[:500]


DYNAMIC_PROGRAMS: dict[str, str] = {}


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def _capture_screen_png() -> str:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    if not (1 <= width <= 10000 and 1 <= height <= 10000):
        raise RuntimeError("Tamaño de pantalla no válido")
    desktop = user32.GetDC(0)
    source = gdi32.CreateCompatibleDC(desktop)
    bitmap = gdi32.CreateCompatibleBitmap(desktop, width, height)
    old = gdi32.SelectObject(source, bitmap)
    try:
        if not gdi32.BitBlt(source, 0, 0, width, height, desktop, 0, 0, 0x00CC0020):
            raise RuntimeError("No se pudo capturar la pantalla")
        info = _BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        pixels = (ctypes.c_ubyte * (width * height * 4))()
        if not gdi32.GetDIBits(source, bitmap, 0, height, pixels, ctypes.byref(info), 0):
            raise RuntimeError("No se pudo leer la pantalla")
        rows = bytearray()
        raw = bytes(pixels)
        for row in range(height):
            rows.append(0)
            for col in range(width):
                i = (row * width + col) * 4
                rows.extend((raw[i + 2], raw[i + 1], raw[i], 255))
        png = b"\\x89PNG\\r\\n\\x1a\\n"
        png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        png += _png_chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        png += _png_chunk(b"IEND", b"")
        return base64.b64encode(png).decode("ascii")
    finally:
        gdi32.SelectObject(source, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(source)
        user32.ReleaseDC(0, desktop)


def _window_text(hwnd: int) -> str:
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def enumerate_windows() -> list[dict[str, str | int]]:
    windows: list[dict[str, str | int]] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            title = _window_text(hwnd)
            if title:
                windows.append({"hwnd": int(hwnd), "title": title[:240]})
        return True

    ctypes.windll.user32.EnumWindows(callback_type(callback), 0)
    return windows[:100]


def _find_window(title: str = "", hwnd_value: int = 0):
    if hwnd_value:
        hwnd = ctypes.c_void_p(hwnd_value)
        if ctypes.windll.user32.IsWindow(hwnd):
            return hwnd
    wanted = title.strip().lower()
    if not wanted:
        return ctypes.windll.user32.GetForegroundWindow()
    for item in enumerate_windows():
        if wanted in str(item["title"]).lower():
            return ctypes.c_void_p(int(item["hwnd"]))
    return None


def _key_event(vk: int, flags: int = 0) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


PROGRAMS = {
    "chrome": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"), os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe")],
    "edge": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe")],
    "spotify": [os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe")],
    "steam": [os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Steam", "steam.exe")],
    "explorer": ["explorer.exe"],
    "word": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft Office", "root", "Office16", "WINWORD.EXE"), os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Microsoft Office", "root", "Office16", "WINWORD.EXE")],
    "excel": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft Office", "root", "Office16", "EXCEL.EXE"), os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Microsoft Office", "root", "Office16", "EXCEL.EXE")],
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
}


def execute(command: dict) -> dict:
    action = command.get("action")
    params = command.get("params") or {}
    if action == "capture_screen":
        try:
            image = _capture_screen_png()
            if len(image) > 12_000_000:
                return {"ok": False, "error": "La captura es demasiado grande"}
            return {"ok": True, "image": image, "media_type": "image/png", "message": "Captura actual de la pantalla"}
        except Exception as exc:
            return {"ok": False, "error": f"No pude capturar la pantalla: {exc}"}
    if action == "list_windows":
        return {"ok": True, "windows": enumerate_windows()}
    if action == "focus_window":
        hwnd = _find_window(str(params.get("title", "")), int(params.get("hwnd") or 0))
        if not hwnd:
            return {"ok": False, "error": "No encontré esa ventana"}
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return {"ok": True}
    if action == "click":
        try:
            x, y = int(params.get("x")), int(params.get("y"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Coordenadas inválidas"}
        if not (0 <= x <= 10000 and 0 <= y <= 10000):
            return {"ok": False, "error": "Coordenadas fuera de rango"}
        ctypes.windll.user32.SetCursorPos(x, y)
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
        return {"ok": True, "x": x, "y": y}
    if action == "press_key":
        key = str(params.get("key", "")).strip().upper()
        keys = {"ENTER": 0x0D, "ESC": 0x1B, "TAB": 0x09, "SPACE": 0x20, "BACKSPACE": 0x08, "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27, "CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10}
        if len(key) == 1 and key.isalnum():
            vk = ord(key)
        else:
            vk = keys.get(key)
        if vk is None:
            return {"ok": False, "error": "Tecla no permitida"}
        _key_event(vk)
        _key_event(vk, 2)
        return {"ok": True, "key": key}
    if action == "chrome_open_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            return {"ok": False, "error": "URL no permitida"}
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            return {"ok": False, "error": "Sitio no autorizado"}
        chrome = next((candidate for candidate in PROGRAMS["chrome"] if os.path.isfile(candidate)), None)
        if chrome:
            subprocess.Popen([chrome, url], shell=False)
        else:
            webbrowser.get("windows-default").open(url)
        return {"ok": True}
    if action == "chrome_play_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://www.youtube.com/watch?"):
            return {"ok": False, "error": "Video de YouTube no permitido"}
        chrome = next((candidate for candidate in PROGRAMS["chrome"] if os.path.isfile(candidate)), None)
        if chrome:
            subprocess.Popen([chrome, url], shell=False)
        else:
            webbrowser.get("windows-default").open(url)
        # autoplay=1 inicia el video; no enviamos una tecla adicional que pudiera pausarlo.
        time.sleep(3)
        return {"ok": True, "url": url, "message": "Video abierto con reproducción solicitada."}
    if action == "edge_open_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            return {"ok": False, "error": "URL no permitida"}
        edge = next((candidate for candidate in PROGRAMS["edge"] if os.path.isfile(candidate)), None)
        if edge:
            subprocess.Popen([edge, url], shell=False)
        else:
            return {"ok": False, "error": "Microsoft Edge no está instalado"}
        return {"ok": True, "url": url}
    if action == "spotify_search":
        query = str(params.get("query", "")).strip()
        if not query:
            return {"ok": False, "error": "Falta la búsqueda de Spotify"}
        spotify = next((candidate for candidate in PROGRAMS["spotify"] if os.path.isfile(candidate)), None)
        if spotify:
            subprocess.Popen([spotify], shell=False)
            time.sleep(2)
            # La aplicación de Spotify acepta búsquedas mediante su URI interna.
            os.startfile("spotify:search:" + quote(query))
            return {"ok": True, "query": query}
        url = "https://open.spotify.com/search/" + quote(query)
        return execute({"action": "chrome_open_url", "params": {"url": url}})
    if action == "steam_search":
        query = params.get("query", "")
        url = "https://store.steampowered.com/search/?term=" + quote(str(query).strip())
        return execute({"action": "chrome_open_url", "params": {"url": url}})
    if action == "search_files":
        query = str(params.get("query", "")).strip().lower()
        folder = str(params.get("folder", "")).strip() or os.path.expanduser("~")
        if not query or not os.path.isdir(folder):
            return {"ok": False, "error": "Búsqueda o carpeta no válida"}
        matches = []
        try:
            for path in Path(folder).rglob("*"):
                if path.is_file() and query in path.name.lower():
                    matches.append(str(path))
                    if len(matches) >= 30:
                        break
        except (OSError, PermissionError) as exc:
            return {"ok": False, "error": f"No se pudo buscar: {exc}"}
        return {"ok": True, "matches": matches, "count": len(matches)}
    if action == "open_file":
        path = os.path.abspath(str(params.get("path", "")))
        if not os.path.isfile(path):
            return {"ok": False, "error": "El archivo no existe"}
        os.startfile(path)
        return {"ok": True, "path": path}
    if action == "type_text":
        text = str(params.get("text", ""))
        if not text:
            return {"ok": False, "error": "Texto vacío"}
        # Usa el portapapeles y Ctrl+V para conservar acentos y saltos de línea.
        import tkinter as tk
        root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(text); root.update()
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
        time.sleep(0.5)
        root.destroy()
        return {"ok": True, "characters": len(text)}
    if action == "system_power":
        power_action = params.get("action")
        wake_after = int(params.get("wake_after_seconds") or 0)
        if power_action == "wake":
            return {"ok": True, "message": "El equipo ya está activo para recibir esta orden."}
        if power_action == "sleep":
            if wake_after:
                # Programa el despertar mediante el Programador de tareas de Windows.
                task_name = "IGRIS-Wake"
                run_at = time.strftime("%H:%M", time.localtime(time.time() + wake_after))
                date_at = time.strftime("%m/%d/%Y", time.localtime(time.time() + wake_after))
                created = subprocess.run(["schtasks", "/Create", "/TN", task_name, "/TR", "cmd /c exit", "/SC", "ONCE", "/ST", run_at, "/SD", date_at, "/F", "/RU", "SYSTEM"], check=False, capture_output=True)
                if created.returncode != 0:
                    return {"ok": False, "error": "No se pudo programar el despertar de Windows."}
                # schtasks crea la tarea, y PowerShell activa la opción WakeToRun.
                subprocess.run(["powershell", "-NoProfile", "-Command", "$settings = New-ScheduledTaskSettingsSet -WakeToRun; Set-ScheduledTask -TaskName 'IGRIS-Wake' -Settings $settings"], check=False, capture_output=True)
                subprocess.run(["powercfg", "/SETACVALUEINDEX", "SCHEME_CURRENT", "SUB_NONE", "RTCWAKE", "1"], check=False, capture_output=True)
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
            return {"ok": True, "message": "El equipo entrará en suspensión."}
        return {"ok": False, "error": "Acción de energía no permitida"}
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
        program = str(params.get("program", "")).strip().lower()
        dynamic_path = DYNAMIC_PROGRAMS.get(program)
        paths = PROGRAMS.get(program)
        if dynamic_path:
            if not os.path.isfile(dynamic_path) or Path(dynamic_path).suffix.lower() not in {".exe", ".lnk"}:
                return {"ok": False, "error": "La aplicación ya no está disponible"}
            if Path(dynamic_path).suffix.lower() == ".lnk":
                os.startfile(dynamic_path)
            else:
                subprocess.Popen([dynamic_path], shell=False)
            return {"ok": True, "program": program}
        if not paths:
            return {"ok": False, "error": "Programa no autorizado"}
        path = next((candidate for candidate in paths if os.path.isfile(candidate)), paths[0])
        if os.path.isfile(path) or path in {"explorer.exe", "notepad.exe", "calc.exe"}:
            subprocess.Popen([path], shell=False)
        elif program == "spotify":
            os.startfile("spotify:")
        elif program in {"word", "excel"}:
            # Office también puede estar registrado como aplicación de Windows.
            uri = "ms-word:" if program == "word" else "ms-excel:"
            try:
                os.startfile(uri)
            except OSError:
                return {"ok": False, "error": f"No se encontró {program} instalado"}
        else:
            return {"ok": False, "error": f"No se encontró {program} instalado"}
        return {"ok": True, "program": program}
    return {"ok": False, "error": "Acción desconocida"}


async def main() -> None:
    url = os.environ["IGRIS_DEVICE_URL"]
    token = os.environ["NODE_TOKEN"]
    while True:
        try:
            async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {token}"}, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({
                    "type": "hello",
                    "agent_version": "2.0",
                    "machine_id": socket.gethostname(),
                    "hostname": socket.gethostname(),
                    "programs": enumerate_programs(),
                }))
                hello_result = json.loads(await ws.recv())
                if hello_result.get("type") != "hello_ack":
                    raise RuntimeError("El servidor no aceptó el agente")
                DYNAMIC_PROGRAMS.clear()
                DYNAMIC_PROGRAMS.update({item["name"].lower(): item["path"] for item in enumerate_programs()})
                print("Agente local IGRIS conectado")
                while True:
                    raw = await ws.recv()
                    command = json.loads(raw)
                    if command.get("action") == "sync_programs":
                        programs = enumerate_programs()
                        DYNAMIC_PROGRAMS.clear()
                        DYNAMIC_PROGRAMS.update({item["name"].lower(): item["path"] for item in programs})
                        await ws.send(json.dumps({"id": command.get("id"), "result": {"ok": True, "programs": programs}}))
                        continue
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

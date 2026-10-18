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

"""Herramientas para controlar el computador Windows conectado a IGRIS."""
from __future__ import annotations

from urllib.parse import quote, urlparse

from core.local_agent import run_local_action

ALLOWED_HOSTS = {"www.google.com", "google.com", "www.youtube.com", "youtube.com"}


async def open_chrome(url: str = "https://www.google.com") -> dict:
    if not isinstance(url, str) or not url.startswith("https://"):
        return {"error": "La página debe usar https."}
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        return {"error": "Ese sitio no está autorizado."}
    return await run_local_action("chrome_open_url", url=url[:2048])


async def search_youtube(query: str) -> dict:
    if not isinstance(query, str) or not query.strip():
        return {"error": "Falta la búsqueda."}
    url = "https://www.youtube.com/results?search_query=" + quote(query.strip()[:200])
    return await run_local_action("chrome_open_url", url=url)


async def media_control(action: str) -> dict:
    allowed = {"play_pause", "next", "previous"}
    if action not in allowed:
        return {"error": "Acción multimedia no permitida."}
    return await run_local_action("media_" + action)


async def volume_control(action: str) -> dict:
    allowed = {"up", "down", "mute"}
    if action not in allowed:
        return {"error": "Acción de volumen no permitida."}
    return await run_local_action("volume_" + action)


async def launch_program(program: str) -> dict:
    allowed = {"chrome", "notepad", "calculator"}
    if program not in allowed:
        return {"error": "Ese programa no está autorizado."}
    return await run_local_action("launch_program", program=program)

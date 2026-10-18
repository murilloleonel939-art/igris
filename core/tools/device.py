"""Herramientas para controlar el computador Windows conectado a IGRIS."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, quote, urlparse

import httpx

from core.local_agent import hub, run_local_action

ALLOWED_HOSTS = {"www.google.com", "google.com", "www.youtube.com", "youtube.com"}


async def open_chrome(url: str = "https://www.google.com") -> dict:
    if not isinstance(url, str) or not url.startswith("https://"):
        return {"error": "La página debe usar https."}
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        return {"error": "Ese sitio no está autorizado."}
    # Si el modelo construye una búsqueda de YouTube para una orden de reproducción,
    # conviértela en selección automática del primer resultado.
    if parsed.hostname in {"www.youtube.com", "youtube.com"} and parsed.path == "/results":
        query = parse_qs(parsed.query).get("search_query", [""])[0]
        if query:
            return await search_youtube(query, play=True)
    return await run_local_action("chrome_open_url", url=url[:2048])


async def search_youtube(query: str, play: bool = True) -> dict:
    """Busca en YouTube y, por defecto, abre el primer resultado reproducible."""
    if not isinstance(query, str) or not query.strip():
        return {"error": "Falta la búsqueda."}
    clean_query = query.strip()[:200]
    search_url = "https://www.youtube.com/results?search_query=" + quote(clean_query)
    video_url = None
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=12
        ) as client:
            response = await client.get(search_url)
            response.raise_for_status()
        # YouTube incluye los ids de los resultados en la página de búsqueda.
        ids = re.findall(r'"videoId"\s*:\s*"([A-Za-z0-9_-]{11})"', response.text)
        if not ids:
            ids = re.findall(r'videoId(?:\\?"|\\?\s*:)\s*\\?"([A-Za-z0-9_-]{11})', response.text)
        for video_id in dict.fromkeys(ids):
            video_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
            break
    except Exception:
        # Si YouTube bloquea la consulta, al menos se abre la búsqueda normal.
        pass

    if video_url and play:
        result = await run_local_action("chrome_play_url", url=video_url)
        if result.get("ok"):
            return {"ok": True, "query": clean_query, "video_url": video_url, "message": "Video abierto para reproducción."}
        return result
    result = await run_local_action("chrome_open_url", url=search_url)
    if result.get("ok"):
        return {"ok": True, "query": clean_query, "search_url": search_url, "message": "Búsqueda abierta; no se pudo seleccionar automáticamente un video."}
    return result


async def capture_screen() -> dict:
    """Solicita una captura puntual para que el proveedor multimodal la analice."""
    return await run_local_action("capture_screen")


async def list_windows() -> dict:
    return await run_local_action("list_windows")


async def focus_window(title: str = "", hwnd: int = 0) -> dict:
    if not isinstance(title, str) or len(title) > 240:
        return {"error": "Título de ventana no válido."}
    if not isinstance(hwnd, int) or hwnd < 0:
        return {"error": "Identificador de ventana no válido."}
    return await run_local_action("focus_window", title=title, hwnd=hwnd)


async def click_screen(x: int, y: int) -> dict:
    if not isinstance(x, int) or not isinstance(y, int) or not 0 <= x <= 10000 or not 0 <= y <= 10000:
        return {"error": "Coordenadas inválidas."}
    return await run_local_action("click", x=x, y=y)


async def press_key(key: str) -> dict:
    if not isinstance(key, str) or len(key.strip()) > 20:
        return {"error": "Tecla no válida."}
    return await run_local_action("press_key", key=key.strip())


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
    if not isinstance(program, str):
        return {"error": "Falta el nombre del programa."}
    program = program.strip().lower()
    built_in = {"chrome", "edge", "spotify", "steam", "explorer", "word", "excel", "notepad", "calculator"}
    discovered = {item.get("name", "").strip().lower() for item in hub.programs if isinstance(item, dict)}
    if program not in built_in and program not in discovered:
        return {"error": "Ese programa no aparece en el catálogo del agente."}
    return await run_local_action("launch_program", program=program)


async def search_files(query: str, folder: str = "") -> dict:
    if not isinstance(query, str) or not query.strip():
        return {"error": "Falta el nombre o parte del nombre del archivo."}
    if folder and not isinstance(folder, str):
        return {"error": "La carpeta no es válida."}
    return await run_local_action("search_files", query=query.strip()[:200], folder=(folder or "")[:500])


async def open_file(path: str) -> dict:
    if not isinstance(path, str) or not path.strip():
        return {"error": "Falta la ruta del archivo."}
    return await run_local_action("open_file", path=path.strip()[:1000])


async def type_in_office(text: str, application: str = "") -> dict:
    if not isinstance(text, str) or not text.strip():
        return {"error": "Falta el texto que debo escribir."}
    allowed = {"word", "excel", "notepad", ""}
    if application not in allowed:
        return {"error": "Solo puedo escribir en Word, Excel o el bloc de notas."}
    return await run_local_action("type_text", text=text[:10000], application=application)


async def search_spotify(query: str) -> dict:
    if not isinstance(query, str) or not query.strip():
        return {"error": "Falta la búsqueda de Spotify."}
    return await run_local_action("spotify_search", query=query.strip()[:200])


async def search_steam(query: str) -> dict:
    if not isinstance(query, str) or not query.strip():
        return {"error": "Falta el juego que debo buscar."}
    return await run_local_action("steam_search", query=query.strip()[:200])


async def navigate_edge(url: str = "https://www.bing.com") -> dict:
    if not isinstance(url, str) or not url.startswith("https://"):
        return {"error": "La dirección debe usar https."}
    return await run_local_action("edge_open_url", url=url[:2048])


async def system_power(action: str, wake_after_seconds: int = 0) -> dict:
    allowed = {"sleep", "wake"}
    if action not in allowed:
        return {"error": "Acción de energía no permitida."}
    if not isinstance(wake_after_seconds, int) or not 0 <= wake_after_seconds <= 86400:
        return {"error": "El tiempo de reanudación debe estar entre 0 y 86400 segundos."}
    return await run_local_action("system_power", action=action, wake_after_seconds=wake_after_seconds)

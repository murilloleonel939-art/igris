"""Herramientas para administrar listas de reproducción de YouTube."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import httpx

from core.tools._common import google_credentials, google_error_message
from core.tools.google_client import get_access_token, google_get, google_post

BASE = "https://www.googleapis.com/youtube/v3"


def _video_id(value: str) -> str:
    value = (value or "").strip()
    parsed = urlparse(value)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/").split("/")[0]
    if parsed.path == "/watch" and parsed.query:
        return parse_qs(parsed.query).get("v", [""])[0]
    if parsed.path.startswith("/shorts/"):
        return parsed.path.split("/", 2)[2].split("/", 1)[0]
    return value


def _clean_id(value: str) -> str:
    result = _video_id(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", result):
        raise ValueError("El identificador o enlace del video de YouTube no es válido.")
    return result


async def list_youtube_playlists(_session=None, page_token: str = "") -> dict:
    creds, error = await google_credentials(_session)
    if error:
        return error
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
            if page_token:
                params["pageToken"] = page_token
            data = await google_get(client, creds, f"{BASE}/playlists", params)
        return {"playlists": [{"id": x["id"], "title": x["snippet"]["title"], "video_count": x["contentDetails"].get("itemCount", 0)} for x in data.get("items", [])], "next_page_token": data.get("nextPageToken")}
    except Exception as exc:
        return google_error_message(exc)


async def create_youtube_playlist(title: str, description: str = "", privacy_status: str = "private", _session=None) -> dict:
    creds, error = await google_credentials(_session)
    if error:
        return error
    if privacy_status not in {"private", "public", "unlisted"}:
        return {"error": "La privacidad debe ser private, public o unlisted."}
    title = (title or "").strip()
    if not title:
        return {"error": "Debes indicar el nombre de la lista."}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            data = await google_post(client, creds, f"{BASE}/playlists", {"snippet": {"title": title, "description": description or ""}, "status": {"privacyStatus": privacy_status}}, {"part": "snippet,status"})
        item = data.get("snippet", {})
        return {"success": True, "playlist": {"id": data.get("id"), "title": item.get("title"), "privacy_status": data.get("status", {}).get("privacyStatus")}}
    except Exception as exc:
        return google_error_message(exc)


async def add_video_to_youtube_playlist(playlist_id: str, video_id: str, _session=None) -> dict:
    creds, error = await google_credentials(_session)
    if error:
        return error
    try:
        video_id = _clean_id(video_id)
        playlist_id = (playlist_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", playlist_id):
            return {"error": "El identificador de la lista de YouTube no es válido."}
        async with httpx.AsyncClient(timeout=20) as client:
            data = await google_post(client, creds, f"{BASE}/playlistItems", {"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}, {"part": "snippet"})
        return {"success": True, "message": "Video añadido a la lista.", "item_id": data.get("id"), "video_id": video_id, "playlist_id": playlist_id}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return google_error_message(exc)


async def remove_video_from_youtube_playlist(
    playlist_id: str = "", video_id: str = "", item_id: str = "", _session=None
) -> dict:
    creds, error = await google_credentials(_session)
    if error:
        return error
    playlist_id = (playlist_id or "").strip()
    item_id = (item_id or "").strip()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            access = await get_access_token(client, creds)
            headers = {"Authorization": f"Bearer {access}"}
            if not item_id:
                if not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", playlist_id):
                    return {"error": "El identificador de la lista de YouTube no es válido."}
                video_id = _clean_id(video_id)
                data = await google_get(
                    client, creds, f"{BASE}/playlistItems",
                    {"part": "id,snippet", "playlistId": playlist_id, "videoId": video_id, "maxResults": 50},
                )
                item_id = next((item.get("id") for item in data.get("items", []) if item.get("id")), "")
                if not item_id:
                    return {"error": "Ese video no está en la lista indicada."}
            if not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", item_id):
                return {"error": "El identificador del elemento de la lista no es válido."}
            response = await client.delete(f"{BASE}/playlistItems", params={"id": item_id}, headers=headers)
            response.raise_for_status()
        return {"success": True, "message": "Video quitado de la lista."}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return google_error_message(exc)

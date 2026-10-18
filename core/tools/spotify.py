"""Cliente OAuth y herramientas de Spotify por usuario."""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import httpx

from core import crypto, database
from core.tools._common import session_user_id

logger = logging.getLogger(__name__)
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"
SCOPES = (
    "user-read-private user-read-email user-read-playback-state "
    "user-modify-playback-state user-read-currently-playing "
    "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"
)


@dataclass(frozen=True)
class SpotifyCredentials:
    client_id: str
    client_secret: str
    refresh_token: str
    user_id: int


class SpotifyNotConfigured(Exception):
    pass


class SpotifyReauthNeeded(Exception):
    pass


_access_tokens: dict[int, tuple[str, float]] = {}


def client_config() -> tuple[str, str]:
    return os.getenv("SPOTIFY_CLIENT_ID", "").strip(), os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()


def redirect_uri() -> str:
    explicit = os.getenv("SPOTIFY_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    base = os.getenv("IGRIS_PUBLIC_URL", "").strip().rstrip("/")
    return f"{base}/api/user/spotify/callback" if base else "https://igris.zottagroup.com/api/user/spotify/callback"


def oauth_configured() -> bool:
    client_id, client_secret = client_config()
    return bool(client_id and client_secret)


def authorization_url(state: str) -> str:
    client_id, _ = client_config()
    return f"{AUTH_URL}?{urlencode({'client_id': client_id, 'response_type': 'code', 'redirect_uri': redirect_uri(), 'scope': SCOPES, 'state': state, 'show_dialog': 'true'})}"


def forget_token(user_id: int) -> None:
    _access_tokens.pop(user_id, None)


def stored_credentials(user_id: int) -> Optional[SpotifyCredentials]:
    client_id, client_secret = client_config()
    if not client_id or not client_secret:
        return None
    with database.SessionLocal() as db:
        from core.database import SpotifyAccount
        account = db.query(SpotifyAccount).filter(SpotifyAccount.user_id == user_id).first()
        if account is None:
            return None
        refresh_token = crypto.decrypt(account.refresh_token_enc)
    if not refresh_token:
        return None
    return SpotifyCredentials(client_id, client_secret, refresh_token, user_id)


async def get_access_token(client: httpx.AsyncClient, creds: SpotifyCredentials) -> str:
    import time
    cached = _access_tokens.get(creds.user_id)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    basic = base64.b64encode(f"{creds.client_id}:{creds.client_secret}".encode()).decode()
    response = await client.post(TOKEN_URL, data={"grant_type": "refresh_token", "refresh_token": creds.refresh_token}, headers={"Authorization": f"Basic {basic}"})
    data = response.json()
    if response.status_code != 200:
        if data.get("error") in {"invalid_grant", "invalid_client"}:
            raise SpotifyReauthNeeded("Tu autorización de Spotify ya no es válida. Vuelve a conectar tu cuenta.")
        raise RuntimeError(data.get("error_description") or data.get("error") or response.status_code)
    token = data["access_token"]
    rotated_refresh = data.get("refresh_token")
    if rotated_refresh:
        from core.database import SpotifyAccount
        with database.SessionLocal() as db:
            account = db.query(SpotifyAccount).filter(SpotifyAccount.user_id == creds.user_id).first()
            if account is not None:
                account.refresh_token_enc = crypto.encrypt(rotated_refresh)
                account.last_error = None
                db.commit()
    _access_tokens[creds.user_id] = (token, time.time() + int(data.get("expires_in", 3600)))
    return token


async def spotify_request(session, method: str, path: str, *, params=None, json=None) -> dict:
    user_id = session_user_id(session)
    if user_id is None:
        return {"error": "Spotify requiere una sesión de usuario."}
    creds = stored_credentials(user_id)
    if creds is None:
        return {"error": "Conecta tu cuenta de Spotify desde Conexiones para usar esta función."}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await get_access_token(client, creds)
            response = await client.request(method, f"{API_BASE}{path}", params=params, json=json, headers={"Authorization": f"Bearer {token}"})
            if response.status_code == 204:
                return {"success": True}
            response.raise_for_status()
            return response.json()
    except SpotifyReauthNeeded as exc:
        return {"error": str(exc)}
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("error", {}).get("message", exc.response.status_code)
        except Exception:
            detail = exc.response.status_code
        return {"error": f"Spotify rechazó la operación: {detail}"}
    except Exception as exc:
        return {"error": f"Spotify no respondió correctamente: {exc}"}


async def search_spotify_api(query: str, _session=None) -> dict:
    query = (query or "").strip()
    if not query:
        return {"error": "Falta la búsqueda de Spotify."}
    data = await spotify_request(_session, "GET", "/search", params={"q": query[:200], "type": "track,artist,album", "limit": 10})
    if "error" in data:
        return data
    return {"tracks": [{"id": x["id"], "name": x["name"], "artists": [a["name"] for a in x.get("artists", [])], "uri": x["uri"]} for x in data.get("tracks", {}).get("items", [])], "artists": [{"id": x["id"], "name": x["name"], "uri": x["uri"]} for x in data.get("artists", {}).get("items", [])], "albums": [{"id": x["id"], "name": x["name"], "uri": x["uri"]} for x in data.get("albums", {}).get("items", [])]}


async def list_spotify_playlists(_session=None) -> dict:
    data = await spotify_request(_session, "GET", "/me/playlists", params={"limit": 50})
    if "error" in data:
        return data
    return {"playlists": [{"id": x["id"], "name": x["name"], "public": x.get("public"), "track_count": x.get("tracks", {}).get("total", 0), "uri": x["uri"]} for x in data.get("items", [])]}


async def create_spotify_playlist(name: str, description: str = "", public: bool = False, _session=None) -> dict:
    name = (name or "").strip()
    if not name:
        return {"error": "Debes indicar el nombre de la playlist."}
    me = await spotify_request(_session, "GET", "/me")
    if "error" in me:
        return me
    return await spotify_request(_session, "POST", f"/users/{me['id']}/playlists", json={"name": name, "description": description or "", "public": bool(public)})


async def add_tracks_to_spotify_playlist(playlist_id: str, track_uris: list[str], _session=None) -> dict:
    playlist_id = (playlist_id or "").strip()
    uris = [str(uri).strip() for uri in (track_uris or []) if str(uri).strip()]
    if not playlist_id or not uris:
        return {"error": "Indica la playlist y al menos una canción."}
    return await spotify_request(_session, "POST", f"/playlists/{playlist_id}/items", json={"uris": uris[:100]})


async def remove_tracks_from_spotify_playlist(playlist_id: str, track_uris: list[str], _session=None) -> dict:
    playlist_id = (playlist_id or "").strip()
    uris = [str(uri).strip() for uri in (track_uris or []) if str(uri).strip()]
    if not playlist_id or not uris:
        return {"error": "Indica la playlist y al menos una canción."}
    return await spotify_request(_session, "DELETE", f"/playlists/{playlist_id}/items", json={"tracks": [{"uri": uri} for uri in uris[:100]]})


async def start_spotify_playback(track_uri: str = "", _session=None) -> dict:
    body = {"uris": [track_uri]} if track_uri else None
    return await spotify_request(_session, "PUT", "/me/player/play", json=body)

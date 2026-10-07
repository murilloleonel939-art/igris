"""Cliente mínimo de Google para IGRIS (OAuth con refresh token + GET autenticado).

Variables de entorno (Coolify, servicio de backend):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
El refresh token se obtiene una sola vez con scripts/google_auth.py.
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"

_cache = {"token": None, "exp": 0.0}


class GoogleNotConfigured(Exception):
    """Faltan las variables de entorno de Google."""


async def get_access_token(client: httpx.AsyncClient) -> str:
    """Devuelve un access token vigente (lo renueva con el refresh token)."""
    if _cache["token"] and time.time() < _cache["exp"] - 60:
        return _cache["token"]

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
    if not (client_id and client_secret and refresh_token):
        raise GoogleNotConfigured(
            "Google no está configurado: faltan GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET o GOOGLE_REFRESH_TOKEN"
        )

    r = await client.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if r.status_code != 200:
        # Normalmente "invalid_grant": token revocado/caducado -> reautorizar
        try:
            reason = r.json().get("error", r.status_code)
        except Exception:
            reason = r.status_code
        logger.error(f"Google rechazó el refresh token: {reason}")
        raise RuntimeError(
            f"Google rechazó la autorización ({reason}). Hay que volver a autorizar con scripts/google_auth.py"
        )

    data = r.json()
    _cache["token"] = data["access_token"]
    _cache["exp"] = time.time() + int(data.get("expires_in", 3600))
    return _cache["token"]


async def google_get(client: httpx.AsyncClient, url: str, params=None) -> dict:
    """GET autenticado a una API de Google. Devuelve el JSON."""
    token = await get_access_token(client)
    r = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()

"""Cliente de Google para IGRIS: una cuenta por usuario.

Cómo funciona ahora
-------------------
Cada usuario autoriza SU PROPIA cuenta de Google desde el área /u. El refresh
token resultante se guarda cifrado en la tabla google_accounts y es el que usan
las herramientas de correo y calendario. Por eso dos usuarios ya no ven el mismo
buzón.

Queda un respaldo: si el usuario no tiene cuenta conectada y existe
GOOGLE_REFRESH_TOKEN en el entorno, se usa esa (la del dueño de la instalación).
Es lo que mantiene funcionando el panel del administrador, que no tiene usuario.

Caché de access token
---------------------
Los access token duran una hora y se piden con el refresh token. La caché está
indexada por usuario, no global: con una caché global, el token de un usuario
podría acabar usándose para las peticiones de otro.

Los refresh token los emite Google solo cuando se pide acceso sin conexión
(access_type=offline) y con consentimiento; por eso hay que volver a autorizar si
el usuario revoca el acceso desde su cuenta de Google.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

# Permisos que se piden. Se conceden por bloques según lo que el administrador
# haya habilitado al usuario.
SCOPE_EMAIL = "https://www.googleapis.com/auth/gmail.readonly"
SCOPE_EMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
SCOPE_EMAIL_MODIFY = "https://www.googleapis.com/auth/gmail.modify"
SCOPE_CALENDAR_READ = "https://www.googleapis.com/auth/calendar.readonly"
SCOPE_CALENDAR_WRITE = "https://www.googleapis.com/auth/calendar.events"

# Identidad de la cuenta autorizada: permite mostrarle al usuario qué correo
# conectó. No da acceso a nada más.
SCOPE_IDENTITY = "openid email"


def scopes_for(features) -> list:
    """Permisos de Google que corresponden a las funciones habilitadas.

    Nunca se pide más de lo necesario: a quien solo tiene "ver calendario" no se
    le pide permiso para crear eventos. Menos permisos concedidos es menos riesgo
    si algún día se filtra un token.

    email_write incluye gmail.send y gmail.modify (papelera). Si el usuario
    tiene email_write, gmail.readonly queda implícito en gmail.modify, pero se
    añade explícitamente por claridad y compatibilidad.
    """
    scopes = [SCOPE_IDENTITY]
    if "email" in features:
        scopes.append(SCOPE_EMAIL)
    if "email_write" in features:
        # gmail.modify cubre readonly + papelera; gmail.send es independiente.
        scopes.append(SCOPE_EMAIL_SEND)
        scopes.append(SCOPE_EMAIL_MODIFY)
    if "calendar" in features:
        scopes.append(SCOPE_CALENDAR_READ)
    if "calendar_write" in features:
        # calendar.events cubre leer, crear, modificar y borrar eventos.
        scopes.append(SCOPE_CALENDAR_WRITE)
    return scopes


class GoogleNotConfigured(Exception):
    """El usuario no tiene cuenta conectada (o faltan las credenciales del entorno)."""


class GoogleReauthNeeded(Exception):
    """Google rechazó el token: el usuario tiene que volver a autorizar."""


@dataclass(frozen=True)
class Credentials:
    """Credenciales con las que se firma una petición a Google.

    `user_id` es None cuando son las del entorno (respaldo del administrador).
    """

    client_id: str
    client_secret: str
    refresh_token: str
    user_id: Optional[int] = None


# Caché de access tokens: {clave: (token, expira_en)}. La clave es el usuario
# (o "env" para las credenciales del entorno), nunca una global.
_token_cache: dict[str, tuple] = {}

# Margen de seguridad: un token que expira en menos de esto se renueva ya.
_EXPIRY_MARGIN = 60


# ============= CREDENCIALES =============

def client_config() -> tuple:
    """(client_id, client_secret) de la aplicación de Google, del entorno."""
    return (
        os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
    )


def oauth_configured() -> bool:
    """¿Está la aplicación configurada para el flujo de autorización?"""
    client_id, client_secret = client_config()
    return bool(client_id and client_secret)


def redirect_uri() -> str:
    """URI de redirección que Google debe tener registrada.

    Tiene que coincidir EXACTAMENTE con la que se da de alta en Google Cloud, o
    Google devuelve "redirect_uri_mismatch".
    """
    explicit = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    base = os.environ.get("IGRIS_PUBLIC_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/api/user/google/callback"
    return "https://igris.zottagroup.com/api/user/google/callback"


def env_credentials() -> Optional[Credentials]:
    """Credenciales del entorno (respaldo del administrador), si están completas."""
    client_id, client_secret = client_config()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
    if not (client_id and client_secret and refresh_token):
        return None
    return Credentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        user_id=None,
    )


def stored_credentials(user_id: int) -> Optional[Credentials]:
    """Credenciales del usuario a partir de su refresh token cifrado en la BD."""
    from core import crypto, database
    from core.database import GoogleAccount

    client_id, client_secret = client_config()
    if not (client_id and client_secret):
        return None

    with database.SessionLocal() as db:
        account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user_id).first()
        if account is None:
            return None
        refresh_token = crypto.decrypt(account.refresh_token_enc)

    if not refresh_token:
        # Token ilegible: normalmente cambió SECRET_KEY. El usuario debe reconectar.
        logger.warning("La cuenta de Google del usuario %s no se puede descifrar", user_id)
        return None

    return Credentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        user_id=user_id,
    )


def resolve_credentials(user_id: Optional[int]) -> Credentials:
    """Credenciales para este usuario, con el respaldo del entorno.

    Se prefiere SIEMPRE la cuenta del propio usuario. Solo si no tiene ninguna se
    cae a la del entorno, y únicamente cuando el usuario no está identificado
    (panel del administrador): así un usuario sin cuenta conectada recibe un aviso
    claro en lugar de ver, sin saberlo, el correo de otra persona.
    """
    if user_id is not None:
        # Si el servidor ni siquiera tiene las credenciales de aplicación, ese es
        # el problema y no lo que haya hecho el usuario: se dice tal cual.
        client_id, client_secret = client_config()
        if not (client_id and client_secret):
            raise GoogleNotConfigured(
                "Google no está configurado en el servidor: faltan GOOGLE_CLIENT_ID "
                "y GOOGLE_CLIENT_SECRET. Avisa al administrador de Igris."
            )
        creds = stored_credentials(user_id)
        if creds is not None:
            return creds
        env_creds = env_credentials()
        # El administrador puede seguir usando la cuenta compartida del entorno.
        if env_creds is not None and _is_admin(user_id):
            return env_creds
        # Dos motivos distintos, y el usuario merece saber cuál es el suyo:
        # si ya tenía cuenta guardada pero no se puede descifrar, el problema es
        # del servidor (cambió SECRET_KEY) y reconectar lo arregla; decirle que
        # "no ha conectado" le haría dar vueltas buscando algo que ya hizo.
        if _has_stored_account(user_id):
            raise GoogleNotConfigured(
                "Tu cuenta de Google está conectada, pero el servidor no puede leer "
                "el permiso guardado. Entra en tu página de Igris, sección "
                "«Conexiones», y vuelve a conectarla."
            )
        raise GoogleNotConfigured(
            "No has conectado tu cuenta de Google. Hazlo en tu página de Igris, "
            "en la sección «Conexiones»."
        )

    env_creds = env_credentials()
    if env_creds is None:
        raise GoogleNotConfigured(
            "Google no está configurado: faltan GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET o GOOGLE_REFRESH_TOKEN"
        )
    return env_creds


def _is_admin(user_id: int) -> bool:
    from core import database
    from core.database import User

    with database.SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        return bool(user and user.is_admin)


def _has_stored_account(user_id: int) -> bool:
    """¿El usuario tiene una cuenta de Google guardada, aunque no se pueda leer?

    Sirve para distinguir "nunca la conectó" de "está conectada pero el servidor
    no puede descifrarla": el mensaje al usuario es distinto en cada caso.
    """
    from core import database
    from core.database import GoogleAccount

    with database.SessionLocal() as db:
        return db.query(GoogleAccount).filter(GoogleAccount.user_id == user_id).first() is not None


def mark_account_error(user_id: Optional[int], message: str) -> None:
    """Anota en la cuenta del usuario el último fallo de Google (para mostrarlo en /u)."""
    if user_id is None:
        return
    from core import database
    from core.database import GoogleAccount

    try:
        with database.SessionLocal() as db:
            account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user_id).first()
            if account is not None:
                account.last_error = message[:500]
                db.commit()
    except Exception:
        logger.exception("No se pudo anotar el error de Google del usuario %s", user_id)


# ============= ACCESS TOKEN =============

async def get_access_token(client: httpx.AsyncClient, creds: Credentials) -> str:
    """Devuelve un access token vigente, renovándolo con el refresh token."""
    cache_key = f"user:{creds.user_id}" if creds.user_id is not None else "env"
    cached = _token_cache.get(cache_key)
    if cached and time.time() < cached[1] - _EXPIRY_MARGIN:
        return cached[0]

    r = await client.post(
        TOKEN_URL,
        data={
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if r.status_code != 200:
        try:
            reason = r.json().get("error", r.status_code)
        except Exception:
            reason = r.status_code
        logger.error("Google rechazó un refresh token: %s", reason)
        if str(reason) in ("invalid_grant", "unauthorized_client"):
            # El usuario revocó el acceso o el token caducó: hay que reconectar.
            mark_account_error(
                creds.user_id,
                "Google rechazó la autorización. Vuelve a conectar tu cuenta.",
            )
            raise GoogleReauthNeeded(
                "Tu autorización de Google ya no es válida. Vuelve a conectar tu "
                "cuenta de Google en la sección «Conexiones»."
            )
        raise RuntimeError(f"Google rechazó la autorización ({reason})")

    data = r.json()
    token = data["access_token"]
    # Un token caducado en la caché no se reutiliza; se guarda con su caducidad real.
    _token_cache[cache_key] = (token, time.time() + int(data.get("expires_in", 3600)))
    return token


def forget_token(user_id: Optional[int]) -> None:
    """Olvida el access token en caché de un usuario (al desconectar su cuenta)."""
    _token_cache.pop(f"user:{user_id}" if user_id is not None else "env", None)


# ============= PETICIONES AUTENTICADAS =============

async def google_get(client: httpx.AsyncClient, creds: Credentials, url: str, params=None) -> dict:
    """GET autenticado a una API de Google. Devuelve el JSON."""
    token = await get_access_token(client, creds)
    r = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


async def google_post(client: httpx.AsyncClient, creds: Credentials, url: str, json_body: dict, params=None) -> dict:
    """POST autenticado (JSON) a una API de Google. Devuelve el JSON."""
    token = await get_access_token(client, creds)
    r = await client.post(
        url,
        json=json_body,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()

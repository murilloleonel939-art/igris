"""
IGRIS — Área de usuarios (/u) y panel de administración de usuarios.

Dos superficies de autenticación que NO se mezclan:

  /api/admin/*  ->  header X-Igris-Key o JWT Bearer de un usuario con
                    is_admin=True. Ambos se validan en el backend.
  /api/user/*   ->  header Authorization: Bearer <JWT> con role="user".

La clave de admin NUNCA sirve en /api/user. Un JWT solo sirve en /api/admin si
pertenece a una cuenta activa marcada como administradora en la base de datos.

El chat de cada usuario se aísla por una clave construida en el servidor:
    user:<id del token>:<identificador de conversación>
El identificador que envía el navegador solo separa las conversaciones propias
de ese usuario; no puede alcanzar la sesión de otro.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
import re
import secrets
import time
from collections import deque
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from jose import JWTError, jwt
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from core import tts
from core.auth import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)
from core.capabilities import (
    FEATURES,
    FEATURE_ORDER,
    DEFAULT_FEATURES,
    admin_capabilities,
    capabilities_from_user,
)
from core.database import GoogleAccount, Profile, TelegramLink, User, get_db
from core import stt, voice

router = APIRouter()

logger = logging.getLogger(__name__)

# ============= CONFIGURACIÓN =============

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PASSWORD_MIN = 8

# Login de usuario: 8 fallos por IP+usuario dentro de 5 minutos.
# Es independiente del límite de la clave de admin (ese vive en main.py y
# cuenta solo fallos de la clave), para que un usuario no pueda bloquear el
# acceso del administrador ni al contrario.
LOGIN_MAX_FAILS = 8
LOGIN_WINDOW = 300
_MAX_TRACKED = 10000

_login_fails: dict[str, deque] = {}
_login_lock = Lock()

# Duración del token de usuario: 12 horas, para cubrir una jornada de trabajo
# sin obligar a volver a entrar.
USER_TOKEN_MINUTES = 12 * 60

# Tope de texto para la voz (evita peticiones enormes al sintetizador)
TTS_MAX_CHARS = 2000

# Almacén de sesiones compartido con el resto del servidor. Se enlaza desde
# main.py con bind_sessions(): así el chat de los usuarios usa exactamente el
# mismo Brain y el mismo historial que el chat del administrador.
_sessions = None


def bind_sessions(sessions) -> None:
    """Enlaza el SessionStore global (lo llama main.py al montar el router)."""
    global _sessions
    _sessions = sessions


# ============= LÍMITE DE INTENTOS =============

def _client_ip(request: Request) -> str:
    """IP real detrás del proxy (Coolify/Traefik).

    Se usa el ÚLTIMO valor de X-Forwarded-For: lo añade el proxy más cercano y
    el cliente no puede falsificarlo (el primero sí podría venir inventado).
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "desconocida"


def _login_key(request: Request, username: str) -> str:
    return f"{_client_ip(request)}|{username.lower()}"


def _too_many_fails(key: str) -> bool:
    now = time.time()
    with _login_lock:
        hits = _login_fails.get(key)
        if not hits:
            return False
        while hits and now - hits[0] > LOGIN_WINDOW:
            hits.popleft()
        return len(hits) >= LOGIN_MAX_FAILS


def _record_fail(key: str) -> None:
    now = time.time()
    with _login_lock:
        # Evita que el diccionario crezca sin límite
        if len(_login_fails) > _MAX_TRACKED:
            _login_fails.clear()
        _login_fails.setdefault(key, deque()).append(now)


def _clear_fails(key: str) -> None:
    with _login_lock:
        _login_fails.pop(key, None)


# ============= DEPENDENCIAS DE AUTENTICACIÓN =============

async def require_admin_key(
    request: Request,
    x_igris_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Exige la clave única o un token Bearer de usuario administrador.

    Reutiliza require_key de main.py para mantener el mismo límite de intentos y
    para que /api/admin acepte el mismo acceso que el resto del panel.
    """
    from server.main import require_key

    await require_key(request, x_igris_key, authorization)


def require_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Valida el token del área /u y devuelve el usuario.

    Exige role == "user". Un token sin ese rol (por ejemplo uno manipulado, o
    la respuesta de un futuro login de administrador) se rechaza aquí.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida",
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o no válida",
        )

    if payload.get("role") != "user":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o no válida",
        )

    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o no válida",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o no válida",
        )
    # Cuenta desactivada después de emitir el token: se corta el acceso ya
    # mismo, sin esperar a que el token caduque.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contacta al administrador.",
        )
    return user


# ============= MODELOS =============

class LoginIn(BaseModel):
    username: str
    password: str


class UserCreateIn(BaseModel):
    username: str
    email: str
    password: str
    is_admin: bool = False
    # Funciones habilitadas de salida. Si no se envían, se aplican los valores por
    # defecto de core/capabilities.py (hora y clima activos).
    features: Optional[list[str]] = None

    @field_validator("features")
    @classmethod
    def _v_features(cls, v):
        return _validate_features(v)

    @field_validator("username")
    @classmethod
    def _v_username(cls, v: str) -> str:
        v = (v or "").strip()
        if not USERNAME_RE.match(v):
            raise ValueError(
                "El usuario debe tener entre 3 y 32 caracteres y solo puede "
                "contener letras, números, punto, guion y guion bajo"
            )
        return v

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Correo electrónico no válido")
        return v

    @field_validator("password")
    @classmethod
    def _v_password(cls, v: str) -> str:
        if len(v or "") < PASSWORD_MIN:
            raise ValueError(
                f"La contraseña debe tener al menos {PASSWORD_MIN} caracteres"
            )
        return v


class UserUpdateIn(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    addressing_instruction: Optional[str] = None  # Instrucción de trato personalizado
    features: Optional[list[str]] = None          # Funciones habilitadas (reemplaza el conjunto)

    @field_validator("features")
    @classmethod
    def _v_features(cls, v):
        return _validate_features(v)

    @field_validator("email")
    @classmethod
    def _v_email(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Correo electrónico no válido")
        return v

    @field_validator("password")
    @classmethod
    def _v_password(cls, v):
        if v is None:
            return v
        if len(v) < PASSWORD_MIN:
            raise ValueError(
                f"La contraseña debe tener al menos {PASSWORD_MIN} caracteres"
            )
        return v


def _validate_features(value):
    """Comprueba que las funciones enviadas existen. None respeta el valor actual."""
    if value is None:
        return value
    unknown = [f for f in value if f not in FEATURES]
    if unknown:
        raise ValueError("Función desconocida: " + ", ".join(unknown))
    # Se guarda sin repetidos y en el orden canónico.
    return [f for f in FEATURE_ORDER if f in set(value)]


def _set_features(user: User, features) -> None:
    """Escribe en el usuario las columnas de permisos según la lista de funciones."""
    wanted = set(features or ())
    for key, feat in FEATURES.items():
        setattr(user, feat.column, key in wanted)


class ChatIn(BaseModel):
    text: str
    session_id: Optional[str] = None


class TtsIn(BaseModel):
    text: str


def _public_user(u: User, db: Session = None) -> dict[str, Any]:
    """Serializa un usuario SIN exponer nunca el hash de la contraseña.

    Añade el estado de sus conexiones (Google y Telegram) para que el panel pueda
    mostrarlo de un vistazo, sin dar ningún dato del token.
    """
    features = sorted(
        (key for key, feat in FEATURES.items() if bool(getattr(u, feat.column, False))),
        key=FEATURE_ORDER.index,
    )

    connection = {"google": None, "google_error": None, "telegram": None, "telegram_linked": False}
    if db is not None:
        account = db.query(GoogleAccount).filter(GoogleAccount.user_id == u.id).first()
        if account is not None:
            connection["google"] = account.email
            connection["google_error"] = account.last_error
        link = db.query(TelegramLink).filter(TelegramLink.user_id == u.id).first()
        if link is not None:
            connection["telegram_linked"] = bool(link.chat_id)
            connection["telegram"] = link.username

    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "is_admin": bool(u.is_admin),
        "is_active": bool(u.is_active),
        "addressing_instruction": u.addressing_instruction or "",
        "features": features,
        "connections": connection,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ============= ADMINISTRACIÓN DE USUARIOS =============

@router.get("/api/admin/features")
def list_features(_: None = Depends(require_admin_key)):
    """Catálogo de funciones para el panel: qué existe, qué hace y qué necesita.

    El panel se construye a partir de esto, así que añadir una función en
    core/capabilities.py la hace aparecer sola en la interfaz.
    """
    return {
        "features": [
            {
                "key": key,
                "label": FEATURES[key].label,
                "description": FEATURES[key].description,
                "requires_google": FEATURES[key].requires_google,
                "default": key in DEFAULT_FEATURES,
            }
            for key in FEATURE_ORDER
        ]
    }


@router.get("/api/admin/users")
def list_users(
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.id.asc()).all()
    return {"users": [_public_user(u, db) for u in users]}


@router.post("/api/admin/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateIn,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese nombre",
        )
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo",
        )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
        # El administrador crea la cuenta ya activa: puede entrar de inmediato.
        is_active=True,
    )
    # Funciones: las que envíe el panel o, si no envía ninguna lista, las de fábrica.
    # Ojo: una lista VACÍA es una elección válida (usuario sin ninguna función), así
    # que se distingue de None.
    if payload.features is None:
        _set_features(user, DEFAULT_FEATURES)
    else:
        _set_features(user, payload.features)

    db.add(user)
    db.commit()
    db.refresh(user)
    return _public_user(user, db)


@router.put("/api/admin/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateIn,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if payload.email is not None and payload.email != user.email:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese correo",
            )
        user.email = payload.email
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
    if payload.addressing_instruction is not None:
        user.addressing_instruction = payload.addressing_instruction.strip() or None
    if payload.features is not None:
        _set_features(user, payload.features)

    db.commit()
    db.refresh(user)
    return _public_user(user, db)


@router.delete("/api/admin/users/{user_id}")
def delete_user(
    user_id: int,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    username = user.username
    db.delete(user)
    db.commit()
    return {"success": True, "message": f"Usuario '{username}' eliminado"}


@router.delete("/api/admin/users/{user_id}/telegram")
def admin_unlink_telegram(
    user_id: int,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    """El administrador desvincula el Telegram de cualquier usuario.

    Borra el chat_id de la fila TelegramLink del usuario. A partir de ese momento
    el bot deja de atender al chat vinculado como ese usuario y no le envía
    recordatorios. El usuario puede volver a vincular cuando quiera desde /u.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    link = db.query(TelegramLink).filter(TelegramLink.user_id == user_id).first()
    if not link or not link.chat_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este usuario no tiene Telegram vinculado",
        )
    chat_id = link.chat_id
    link.chat_id = None
    link.username = None
    link.linked_at = None
    db.commit()
    logger.info(
        "Admin desvinculó Telegram del usuario %s (chat %s)", user_id, chat_id
    )
    return {"success": True, "message": f"Telegram desvinculado del usuario '{user.username}'"}


# ============= ACCESO DE USUARIOS =============

@router.post("/api/user/login")
def user_login(
    payload: LoginIn,
    request: Request,
    db: Session = Depends(get_db),
):
    username = (payload.username or "").strip()
    key = _login_key(request, username)

    if _too_many_fails(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Inténtalo en unos minutos.",
        )

    user = db.query(User).filter(User.username == username).first()

    # Mismo mensaje para usuario inexistente y para contraseña incorrecta: así
    # no se puede averiguar qué nombres están registrados.
    if not user or not verify_password(payload.password, user.password_hash):
        _record_fail(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contacta al administrador.",
        )

    _clear_fails(key)

    token = create_access_token(
        user_id=user.id,
        expires_delta=timedelta(minutes=USER_TOKEN_MINUTES),
        role="user",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _public_user(user, db),
    }


@router.get("/api/user/me")
def user_me(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Comprueba que la sesión sigue viva y devuelve los datos del usuario."""
    return _public_user(user, db)


# ============= CHAT Y VOZ DEL USUARIO =============

def _session_key(user_id: int, client_sub: Optional[str]) -> str:
    """Clave de sesión del chat, construida SIEMPRE en el servidor.

    El identificador que manda el navegador solo separa conversaciones propias:
    se limpia de caracteres raros y se prefija con el id del token, de modo que
    un valor falso no puede alcanzar la sesión de otro usuario.
    """
    sub = re.sub(r"[^A-Za-z0-9_-]", "", client_sub or "")[:64]
    return f"user:{user_id}:{sub or 'default'}"


def _bind_identity(session, user: User, db: Session) -> None:
    """Fija en la sesión QUIÉN es el usuario y QUÉ puede hacer.

    Se hace en cada mensaje, no solo al crear la sesión: si el administrador
    cambia los permisos o el usuario conecta su Google, el siguiente mensaje ya lo
    nota, sin tener que esperar a que caduque la sesión (que dura 2 horas).

    La sesión es la única fuente que ven las herramientas, y las herramientas no
    la reciben del modelo: por eso un usuario no puede actuar como otro.
    """
    session.user_id = user.id
    session.capabilities = (
        admin_capabilities() if user.is_admin else capabilities_from_user(user)
    )
    session.addressing_instruction = user.addressing_instruction or ""

    account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    session.google_linked = account.email if account is not None else None

    link = db.query(TelegramLink).filter(TelegramLink.user_id == user.id).first()
    session.telegram_linked = bool(link and link.chat_id)


@router.post("/api/user/voice-profile")
async def register_voice_profile(
    audio: list[UploadFile] = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Registra o reemplaza la huella de voz del usuario."""
    samples = [await item.read() for item in audio]
    samples = [item for item in samples if len(item) >= 10_000]
    if len(samples) < 3:
        raise HTTPException(status_code=422, detail="Necesitas al menos 3 muestras de voz válidas")
    try:
        vector = await asyncio.to_thread(voice.average_embedding, samples, ".webm")
        encoded = voice.serialize(vector)
    except Exception as exc:
        logger.exception("No se pudo registrar la voz")
        raise HTTPException(status_code=500, detail=f"No se pudo registrar la voz: {exc}")

    profile = db.query(Profile).filter(
        Profile.user_id == user.id,
        Profile.name == "Voz principal",
    ).first()
    if profile is None:
        profile = Profile(user_id=user.id, name="Voz principal")
        db.add(profile)
    profile.voice_print = encoded
    profile.is_authorized = True
    db.commit()
    return {"status": "ok", "message": "Voz registrada correctamente"}


@router.get("/api/user/voice-profile")
async def voice_profile_status(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(
        Profile.user_id == user.id,
        Profile.name == "Voz principal",
    ).first()
    return {"registered": bool(profile and profile.voice_print and profile.is_authorized)}


@router.delete("/api/user/voice-profile")
def delete_voice_profile(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Elimina todas las muestras cifradas de voz del usuario."""
    profile = db.query(Profile).filter(
        Profile.user_id == user.id,
        Profile.name == "Voz principal",
    ).first()
    if profile is not None:
        db.delete(profile)
        db.commit()
    logger.info("Perfil de voz eliminado por el usuario %s", user.id)
    return {"success": True, "message": "Perfil de voz eliminado"}


@router.post("/api/user/voice-chat")
async def user_voice_chat(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Verifica al hablante, transcribe y solo entonces ejecuta la orden."""
    profile = db.query(Profile).filter(
        Profile.user_id == user.id,
        Profile.name == "Voz principal",
        Profile.is_authorized.is_(True),
    ).first()
    if profile is None or not profile.voice_print:
        raise HTTPException(status_code=403, detail="Registra tu voz antes de usar órdenes por voz")
    data = await audio.read()
    if len(data) < 1_000:
        raise HTTPException(status_code=422, detail="El audio está vacío o es demasiado corto")
    try:
        verified, score = await asyncio.to_thread(voice.verify, data, profile.voice_print, ".webm")
    except Exception as exc:
        logger.exception("Falló la verificación de voz")
        raise HTTPException(status_code=500, detail=f"No se pudo verificar la voz: {exc}")
    if not verified:
        logger.warning("Voz no reconocida para usuario %s: score=%.4f threshold=%s", user.id, score, os.getenv("IGRIS_VOICE_THRESHOLD", "0.40"))
        raise HTTPException(status_code=403, detail=f"Voz no reconocida (similitud {score:.2f})")

    try:
        text = (await asyncio.to_thread(stt.transcribe, data, ".webm")).strip()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"No se pudo transcribir el audio: {exc}")
    if not text:
        raise HTTPException(status_code=422, detail="No se entendió la orden")

    if _sessions is None:
        return {"status": "error", "message": "El chat no está disponible en este momento."}
    session = _sessions.get(_session_key(user.id, session_id))
    _bind_identity(session, user, db)
    try:
        reply = await session.say(text)
        return {"status": "ok", "text": text, "reply": reply, "voice_score": round(score, 3)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.post("/api/user/chat")
async def user_chat(
    payload: ChatIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El mensaje está vacío",
        )

    if _sessions is None:
        return {
            "status": "error",
            "message": "El chat no está disponible en este momento.",
        }

    # El Brain se comparte con el resto del servidor, pero el historial queda
    # aislado por usuario gracias a la clave anterior.
    session = _sessions.get(_session_key(user.id, payload.session_id))
    # Identidad y permisos SIEMPRE frescos, y la instrucción de trato: si el admin
    # la cambió en caliente, el próximo mensaje ya refleja el nuevo trato.
    _bind_identity(session, user, db)
    try:
        reply = await session.say(text)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/user/tts")
async def user_tts(payload: TtsIn, user: User = Depends(require_user)):
    """Voz de Igris para el área de usuarios (mismo sintetizador que el panel)."""
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El texto está vacío",
        )
    if len(text) > TTS_MAX_CHARS:
        text = text[:TTS_MAX_CHARS]

    try:
        audio_bytes = await tts.synthesize(text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo generar la voz: {e}",
        )

    from fastapi.responses import Response

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=igris_response.mp3"},
    )


# ============= CONEXIONES DEL USUARIO (Google y Telegram) =============

# El estado del flujo OAuth vive en memoria y caduca: es una defensa contra CSRF
# (que alguien fuerce la conexión de SU cuenta de Google en la sesión de otro).
# Diez minutos son de sobra para completar el consentimiento de Google.
OAUTH_STATE_TTL = 600

_oauth_states: dict[str, tuple] = {}
_oauth_lock = Lock()

TELEGRAM_CODE_TTL = 900  # 15 minutos para usar el código de vinculación


def _prune_oauth_states() -> None:
    now = time.time()
    for state, (_, created) in list(_oauth_states.items()):
        if now - created > OAUTH_STATE_TTL:
            _oauth_states.pop(state, None)


def _issue_oauth_state(user_id: int) -> str:
    state = secrets.token_urlsafe(32)
    with _oauth_lock:
        _prune_oauth_states()
        _oauth_states[state] = (user_id, time.time())
    return state


def _consume_oauth_state(state: str) -> Optional[int]:
    """Devuelve el user_id dueño del estado y lo borra (un solo uso)."""
    with _oauth_lock:
        _prune_oauth_states()
        entry = _oauth_states.pop(state or "", None)
    if entry is None:
        return None
    user_id, created = entry
    if time.time() - created > OAUTH_STATE_TTL:
        return None
    return user_id


def _google_status(user: User, db: Session) -> dict:
    """Estado de la conexión de Google del usuario (sin exponer ningún token)."""
    from core.tools import google_client

    account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    caps = admin_capabilities() if user.is_admin else capabilities_from_user(user)
    needed = google_client.scopes_for(caps.features)
    return {
        "app_configured": google_client.oauth_configured(),
        "connected": account is not None,
        "email": account.email if account is not None else None,
        "error": account.last_error if account is not None else None,
        "needs_google": any(caps.has(f) for f in ("email", "calendar", "calendar_write")),
        "scopes": needed,
        "redirect_uri": google_client.redirect_uri(),
    }


@router.get("/api/user/connections")
def user_connections(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Qué tiene conectado el usuario y qué le falta.

    Es lo que alimenta la sección «Conexiones» de /u.
    """
    caps = admin_capabilities() if user.is_admin else capabilities_from_user(user)
    link = db.query(TelegramLink).filter(TelegramLink.user_id == user.id).first()

    return {
        "features": sorted(caps.features, key=FEATURE_ORDER.index),
        "google": _google_status(user, db),
        "telegram": {
            "linked": bool(link and link.chat_id),
            "username": link.username if link else None,
            "bot_url": None,  # lo rellena el frontend con la variable de build
        },
    }


@router.get("/api/user/google/start")
def google_start(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Devuelve la URL de consentimiento de Google.

    Se devuelve para que el frontend navegue él mismo, en lugar de redirigir
    desde aquí: así el navegador manda el token de sesión (que no viaja en
    cookies) y no hay que confiar en el estado de una redirección.
    """
    from urllib.parse import urlencode

    from core.tools import google_client

    client_id, _ = google_client.client_config()
    if not (client_id and google_client.oauth_configured()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google no está configurado en el servidor "
                "(faltan GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET)."
            ),
        )

    caps = admin_capabilities() if user.is_admin else capabilities_from_user(user)
    scopes = google_client.scopes_for(caps.features)
    if not any(caps.has(f) for f in ("email", "calendar", "calendar_write")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No tienes ninguna función de Google habilitada. "
                "Pídele al administrador que te active el correo o el calendario."
            ),
        )

    params = {
        "client_id": client_id,
        "redirect_uri": google_client.redirect_uri(),
        "response_type": "code",
        "scope": " ".join(scopes),
        # access_type=offline + prompt=consent son lo que hace que Google entregue
        # un refresh token (y uno nuevo aunque ya hubiera autorizado antes).
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": _issue_oauth_state(user.id),
    }
    return {"auth_url": f"{google_client.AUTH_URL}?{urlencode(params)}"}


@router.get("/api/user/google/callback")
async def google_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Recibe el código de Google y guarda el refresh token del usuario.

    OJO: esta URL la abre el NAVEGADOR (redirección de Google), así que no lleva
    el token de sesión y no se puede exigir require_user. La identidad se
    comprueba con el 'state', que este servidor emitió para un usuario concreto
    hace menos de diez minutos y que solo sirve una vez. Sin eso, cualquiera
    podría intentar conectar una cuenta ajena.

    Devuelve una página HTML mínima que se cierra sola.
    """
    from core.tools import google_client
    from core import crypto
    from fastapi.responses import HTMLResponse
    from html import escape

    def _page(title: str, detail: str, ok: bool) -> HTMLResponse:
        color = "#10b981" if ok else "#ef4444"
        # En la página de éxito se redirige automáticamente al chat del usuario.
        # En la de error no: el usuario necesita leer el motivo antes de cerrar.
        redirect_snippet = ""
        if ok:
            redirect_snippet = """
<meta http-equiv="refresh" content="3;url=https://webigris.zottagroup.com/u">
<script>setTimeout(()=>{window.location.replace('https://webigris.zottagroup.com/u')},3000)</script>"""
        return HTMLResponse(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Igris</title>{redirect_snippet}</head>
<body style="margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
             display:flex;align-items:center;justify-content:center;height:100vh">
  <div style="text-align:center;max-width:32rem;padding:2rem">
    <h1 style="color:{color};font-size:1.25rem;margin:0 0 .75rem">{escape(title)}</h1>
    <p style="color:#94a3b8;line-height:1.6;margin:0">{escape(detail)}</p>
    {'<p style="color:#64748b;font-size:.875rem;margin-top:1.5rem">Redirigiendo a Igris en unos segundos… <a href="https://webigris.zottagroup.com/u" style="color:#6366f1;text-decoration:none">Ir ahora</a></p>' if ok else '<p style="color:#64748b;font-size:.875rem;margin-top:1.5rem">Puedes cerrar esta pestaña y volver a Igris.</p>'}
  </div>
</body></html>""")

    if error:
        return _page("No se conectó la cuenta", f"Google respondió: {error}", False)

    if not code or not state:
        return _page("Faltan datos", "Google no envió el código de autorización.", False)

    user_id = _consume_oauth_state(state)
    if user_id is None:
        return _page(
            "La solicitud caducó",
            "Vuelve a intentarlo desde la sección «Conexiones». Por seguridad, "
            "cada intento dura diez minutos y solo sirve una vez.",
            False,
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        return _page("Cuenta no válida", "Tu usuario ya no está disponible.", False)

    client_id, client_secret = google_client.client_config()

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                google_client.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": google_client.redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
            payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code != 200:
                reason = payload.get("error_description") or payload.get("error") or r.status_code
                logger.error("Google rechazó el código de autorización: %s", reason)
                return _page("Google rechazó la autorización", str(reason), False)
    except Exception as e:
        logger.exception("Fallo al canjear el código de Google")
        return _page("No hubo conexión con Google", str(e), False)

    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        # Pasa cuando Google considera que ya había consentimiento. Con
        # prompt=consent no debería ocurrir; si ocurre, se le dice qué hacer.
        return _page(
            "Sin permiso permanente",
            "Google no entregó un permiso de larga duración. Entra en "
            "myaccount.google.com/permissions, retira el acceso de Igris y "
            "vuelve a intentarlo.",
            False,
        )

    granted = payload.get("scope", "")
    email = None

    # El token se cifra ANTES de tocar la base. crypto.encrypt() puede fallar
    # (falta la dependencia 'cryptography'), y en ese caso NO se guarda nada: es
    # preferible pedirle al usuario que lo intente más tarde que dejar su refresh
    # token en claro en la tabla.
    try:
        token_cifrado = crypto.encrypt(refresh_token)
    except Exception as e:
        logger.error("No se pudo cifrar el refresh token de Google: %s", e)
        return _page(
            "No se pudo guardar la conexión",
            "El servidor no pudo guardar tu permiso de forma segura, así que no se "
            "guardó nada. Avisa al administrador de Igris e inténtalo de nuevo.",
            False,
        )

    # Se guarda ya el token para poder preguntarle a Google de qué cuenta es.
    account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if account is None:
        account = GoogleAccount(user_id=user.id, refresh_token_enc=token_cifrado)
        db.add(account)
    else:
        account.refresh_token_enc = token_cifrado
        account.last_error = None
    account.scopes = granted
    db.commit()

    try:
        creds = google_client.Credentials(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            user_id=user.id,
        )
        google_client.forget_token(user.id)
        async with httpx.AsyncClient(timeout=15) as client:
            info = await google_client.google_get(
                client, creds, "https://openidconnect.googleapis.com/v1/userinfo"
            )
        email = info.get("email")
    except Exception as e:
        # No es grave: la cuenta funciona, solo no se pudo leer su correo.
        logger.warning("No se pudo leer el correo de la cuenta conectada: %s", e)

    if email:
        account.email = email
        db.commit()

    logger.info("Cuenta de Google conectada para el usuario %s (%s)", user.id, email or "sin correo")

    # Las herramientas leen la cuenta de la base en cada llamada, pero el access
    # token cacheado de la cuenta anterior podría seguir vivo: se descarta.
    google_client.forget_token(user.id)
    return _page("Cuenta conectada", f"Ya puedes pedirle a Igris tu correo y tu calendario.", True)


@router.delete("/api/user/google")
def google_disconnect(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Desconecta la cuenta de Google: borra el refresh token guardado."""
    from core.tools import google_client

    account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if account is not None:
        db.delete(account)
        db.commit()
    google_client.forget_token(user.id)
    logger.info("Cuenta de Google desconectada por el usuario %s", user.id)
    return {"success": True, "message": "Cuenta de Google desconectada"}


@router.post("/api/user/telegram/code")
def telegram_code(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Genera un código para vincular el Telegram del usuario.

    El usuario lo envía al bot con /start <código>. Solo entonces se guarda su
    chat_id: así nadie puede decir "soy laura" y recibir sus recordatorios.
    """
    code = f"{secrets.randbelow(10**6):06d}"

    link = db.query(TelegramLink).filter(TelegramLink.user_id == user.id).first()
    if link is None:
        link = TelegramLink(user_id=user.id)
        db.add(link)
    link.link_code = code
    link.code_expires_at = datetime.utcnow() + timedelta(seconds=TELEGRAM_CODE_TTL)
    db.commit()

    return {
        "code": code,
        "expires_in_minutes": TELEGRAM_CODE_TTL // 60,
        "instructions": f"Envía este mensaje al bot de Igris en Telegram: /start {code}",
    }


@router.delete("/api/user/telegram")
def telegram_unlink(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Desvincula el Telegram del usuario (dejará de recibir sus recordatorios)."""
    link = db.query(TelegramLink).filter(TelegramLink.user_id == user.id).first()
    if link is not None:
        # Se conserva el código si lo hubiera; se suelta el chat.
        link.chat_id = None
        link.username = None
        link.linked_at = None
        db.commit()
        logger.info("Telegram desvinculado por el usuario %s", user.id)
    return {"success": True, "message": "Telegram desvinculado"}


# ============= UTILIDAD =============

def generate_secret_key() -> str:
    """Genera una SECRET_KEY válida para pegar en Coolify."""
    return secrets.token_urlsafe(48)


def constant_time_check(a: str, b: str) -> bool:
    """Comparación en tiempo constante (por si se necesita en el futuro)."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

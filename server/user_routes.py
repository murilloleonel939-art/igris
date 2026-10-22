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
import json
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
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
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
from core.database import GoogleAccount, KnowledgeNode, MemoryLink, Note, Profile, Reminder, SessionLocal, SpotifyAccount, TelegramLink, TvBoxPairingCode, TvBoxToken, User, UserMemory, get_db
from server.tvbox_routes import _connections, _digest
from core.settings_manager import get_settings
from core.memory import link_memories, linked_memories_block, load_memories, neural_memory_context, remember_from_text
from core.neural import model_status, train_user_model
from core.knowledge_graph import confirm_graph_relation, export_graph, graph_audit, graph_context, graph_neighbors, graph_summary, import_graph, learn_from_assistant, preview_graph_import, search_graph_nodes, set_graph_relation_status, stale_graph_relations, validate_graph_payload
from core.tools import gcalendar, gmail
from core.tools.time_tools import DEFAULT_TZ, _format
from core import stt, voice

router = APIRouter()

logger = logging.getLogger(__name__)

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_LIVE_URL = "wss://api.deepgram.com/v1/listen"

# Fin de frase para el TTS progresivo: corta al puntuar, sin romper abreviaturas
# ni decimales habituales en español.
_SENTENCE_END = re.compile(r"[.!?…]+[\"'»)]*\s+")


async def transcribe_user_audio(data: bytes, content_type: str = "audio/webm") -> str:

    """Transcribe audio con Deepgram cuando está configurado y usa Whisper como respaldo."""
    configured = get_settings().get_stt_config()
    provider = configured.get("provider", "deepgram")
    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if provider != "deepgram" or not api_key:
        return (await asyncio.to_thread(stt.transcribe, data, ".webm")).strip()

    params = {
        "model": configured.get("cloud_model") or os.getenv("DEEPGRAM_MODEL", "nova-3"),
        "language": configured.get("language") or os.getenv("DEEPGRAM_LANGUAGE", "es"),
        "smart_format": "true",
        "punctuate": "true",
        "utterances": "false",
    }
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type or "audio/webm",
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(DEEPGRAM_URL, params=params, headers=headers, content=data)
        response.raise_for_status()
        payload = response.json()
        channels = payload.get("results", {}).get("channels", [])
        alternatives = channels[0].get("alternatives", []) if channels else []
        text = alternatives[0].get("transcript", "").strip() if alternatives else ""
        if not text:
            raise ValueError("Deepgram no devolvió una transcripción")
        return text
    except Exception:
        logger.exception("Falló la transcripción con Deepgram; se intentará Whisper local")
        return (await asyncio.to_thread(stt.transcribe, data, ".webm")).strip()


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


def _user_from_bearer(authorization: Optional[str], db: Session) -> User:
    """Valida un Bearer JWT del área /u para HTTP o WebSocket."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión expirada o no válida")

    if payload.get("role") != "user" or not isinstance(payload.get("user_id"), int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión expirada o no válida")

    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión expirada o no válida")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu cuenta está desactivada. Contacta al administrador.")
    return user


def require_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Valida el token del área /u y devuelve el usuario."""
    return _user_from_bearer(authorization, db)


# ============= MODELOS =============

class LoginIn(BaseModel):
    username: str
    password: str


class GraphRelationConfirmIn(BaseModel):
    relation_id: int


class GraphImportIn(BaseModel):
    version: int
    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []


class GraphRelationStatusIn(BaseModel):
    relation_id: int
    status: str

    @field_validator("status")
    @classmethod
    def _v_status(cls, value: str) -> str:
        value = (value or "").strip().lower()
        if value not in {"active", "archived"}:
            raise ValueError("El estado debe ser active o archived")
        return value


class MemoryCreateIn(BaseModel):
    kind: str
    content: str

    @field_validator("kind")
    @classmethod
    def _v_kind(cls, value: str) -> str:
        value = (value or "").strip().lower()
        if value not in {"personal", "operational"}:
            raise ValueError("El tipo de memoria no es válido")
        return value

    @field_validator("content")
    @classmethod
    def _v_content(cls, value: str) -> str:
        value = re.sub(r"\\s+", " ", (value or "")).strip()
        if not value or len(value) > 260:
            raise ValueError("La memoria debe tener entre 1 y 260 caracteres")
        return value


class MemoryUpdateIn(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _v_content(cls, value: str) -> str:
        value = re.sub(r"\\s+", " ", (value or "")).strip()
        if not value or len(value) > 260:
            raise ValueError("La memoria debe tener entre 1 y 260 caracteres")
        return value


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
    image_data: Optional[str] = None
    image_mime: str = "image/png"


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

    connection = {
        "google": None,
        "google_error": None,
        "youtube": None,
        "youtube_error": None,
        "spotify": None,
        "spotify_error": None,
        "telegram": None,
        "telegram_linked": False,
        "voice": False,
    }
    if db is not None:
        account = db.query(GoogleAccount).filter(GoogleAccount.user_id == u.id).first()
        if account is not None:
            connection["google"] = account.email
            connection["google_error"] = account.last_error
            connection["youtube"] = account.email if bool(getattr(u, "can_use_youtube", False)) else None
            connection["youtube_error"] = account.last_error if bool(getattr(u, "can_use_youtube", False)) else None
        spotify_account = db.query(SpotifyAccount).filter(SpotifyAccount.user_id == u.id).first()
        if spotify_account is not None:
            connection["spotify"] = spotify_account.display_name or spotify_account.email or spotify_account.spotify_user_id
            connection["spotify_error"] = spotify_account.last_error
        link = db.query(TelegramLink).filter(TelegramLink.user_id == u.id).first()
        if link is not None:
            connection["telegram_linked"] = bool(link.chat_id)
            connection["telegram"] = link.username
        voice = (
            db.query(Profile)
            .filter(Profile.user_id == u.id, Profile.name == "Voz principal")
            .first()
        )
        connection["voice"] = bool(voice and voice.voice_print and voice.is_authorized)

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


@router.get("/api/admin/users/{user_id}/neural-network")
def admin_neural_status(
    user_id: int,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    """Consulta el estado neuronal de cualquier cuenta desde administración."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return {"user_id": user.id, "username": user.username, **model_status(db, user.id)}


@router.post("/api/admin/users/{user_id}/neural-network/train")
def admin_train_neural(
    user_id: int,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    """Reentrena la red neuronal local del usuario seleccionado."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    result = train_user_model(db, user.id)
    return {"user_id": user.id, "username": user.username, **result, **model_status(db, user.id)}


@router.get("/api/admin/users/{user_id}/memories")
def admin_list_user_memories(
    user_id: int,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    """Lista la memoria de un usuario para la pestaña administrativa."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    rows = db.query(UserMemory).filter(UserMemory.user_id == user_id).order_by(UserMemory.updated_at.desc()).all()
    return {
        "personal": [_memory_json(row) for row in rows if row.kind == "personal"],
        "operational": [_memory_json(row) for row in rows if row.kind == "operational"],
        "graph": {
            "summary": graph_summary(db, user_id),
            "relations": graph_audit(db, user_id, limit=50),
        },
    }


@router.post("/api/admin/users/{user_id}/memories", status_code=status.HTTP_201_CREATED)
def admin_create_user_memory(
    user_id: int,
    body: MemoryCreateIn,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    """Crea un recuerdo en nombre del usuario seleccionado por el administrador."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    duplicate = db.query(UserMemory).filter(
        UserMemory.user_id == user_id,
        UserMemory.kind == body.kind,
        UserMemory.content == body.content,
    ).first()
    if duplicate:
        return _memory_json(duplicate)
    memory = UserMemory(user_id=user_id, kind=body.kind, content=body.content, source="admin")
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return _memory_json(memory)


@router.put("/api/admin/users/{user_id}/memories/{memory_id}")
def admin_update_user_memory(
    user_id: int,
    memory_id: int,
    body: MemoryUpdateIn,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    """Edita un recuerdo verificando usuario e id para evitar cruces de cuentas."""
    memory = db.query(UserMemory).filter(
        UserMemory.id == memory_id,
        UserMemory.user_id == user_id,
    ).first()
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró ese recuerdo")
    duplicate = db.query(UserMemory).filter(
        UserMemory.user_id == user_id,
        UserMemory.kind == memory.kind,
        UserMemory.content == body.content,
        UserMemory.id != memory.id,
    ).first()
    if duplicate:
        db.delete(memory)
        db.commit()
        return _memory_json(duplicate)
    memory.content = body.content
    memory.updated_at = datetime.utcnow()
    memory.source = "admin"
    db.commit()
    db.refresh(memory)
    return _memory_json(memory)


@router.delete("/api/admin/users/{user_id}/memories/{memory_id}")
def admin_delete_user_memory(
    user_id: int,
    memory_id: int,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    """Borra un recuerdo del usuario seleccionado."""
    memory = db.query(UserMemory).filter(
        UserMemory.id == memory_id,
        UserMemory.user_id == user_id,
    ).first()
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró ese recuerdo")
    db.query(MemoryLink).filter(
        MemoryLink.user_id == user_id,
        (MemoryLink.from_memory_id == memory.id) | (MemoryLink.to_memory_id == memory.id),
    ).delete(synchronize_session=False)
    db.delete(memory)
    db.commit()
    return {"status": "ok"}


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


# ============= MEMORIA DEL USUARIO =============


@router.get("/api/user/knowledge-graph/summary")
def summarize_user_graph(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return graph_summary(db, user.id)


@router.get("/api/user/knowledge-graph/export")
def export_user_graph(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return export_graph(db, user.id)


@router.post("/api/user/knowledge-graph/validate")
def validate_user_graph(body: GraphImportIn, user: User = Depends(require_user)):
    try:
        validate_graph_payload(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "nodes": len(body.nodes), "relations": len(body.relations)}


@router.post("/api/user/knowledge-graph/preview")
def preview_user_graph_import(
    body: GraphImportIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return preview_graph_import(db, user.id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/user/knowledge-graph/import")
def import_user_graph(
    body: GraphImportIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return import_graph(db, user.id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/user/knowledge-graph/confirm")
def confirm_user_graph_relation(
    body: GraphRelationConfirmIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not confirm_graph_relation(db, user.id, body.relation_id):
        raise HTTPException(status_code=404, detail="No se encontró esa relación activa")
    return {"ok": True, "relation_id": body.relation_id}


@router.post("/api/user/knowledge-graph/status")
def update_user_graph_relation_status(
    body: GraphRelationStatusIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not set_graph_relation_status(db, user.id, body.relation_id, body.status):
        raise HTTPException(status_code=404, detail="No se encontró una relación gestionable")
    return {"ok": True, "relation_id": body.relation_id, "status": body.status}


@router.get("/api/user/knowledge-graph")
def list_user_graph(
    node_id: int | None = None,
    q: str | None = None,
    audit: bool = False,
    stale: bool = False,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Consulta entidades y vecinos del grafo propio, sin exponer otras cuentas."""
    if q:
        return {"nodes": search_graph_nodes(db, user.id, q)}
    if stale:
        return {"relations": stale_graph_relations(db, user.id)}
    if audit:
        return {"relations": graph_audit(db, user.id, node_id=node_id)}
    if node_id is not None:
        node = db.query(KnowledgeNode).filter(
            KnowledgeNode.id == node_id,
            KnowledgeNode.user_id == user.id,
            KnowledgeNode.status == "active",
        ).first()
        if node is None:
            raise HTTPException(status_code=404, detail="No se encontró esa entidad")
        return {
            "node": {"id": node.id, "type": node.node_type, "name": node.name, "description": node.description},
            "neighbors": graph_neighbors(db, user.id, node.id),
        }
    nodes = db.query(KnowledgeNode).filter(
        KnowledgeNode.user_id == user.id,
        KnowledgeNode.status == "active",
    ).order_by(KnowledgeNode.updated_at.desc()).limit(100).all()
    return {"nodes": [{"id": n.id, "type": n.node_type, "name": n.name, "description": n.description} for n in nodes]}


def _memory_json(memory: UserMemory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "kind": memory.kind,
        "content": memory.content,
        "source": memory.source,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }


@router.get("/api/user/memories")
def list_user_memories(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Lista los recuerdos propios, separados por memoria personal y operativa."""
    rows = db.query(UserMemory).filter(UserMemory.user_id == user.id).order_by(
        UserMemory.updated_at.desc(), UserMemory.id.desc()
    ).all()
    return {
        "personal": [_memory_json(row) for row in rows if row.kind == "personal"],
        "operational": [_memory_json(row) for row in rows if row.kind == "operational"],
    }


@router.post("/api/user/memories", status_code=status.HTTP_201_CREATED)
def create_user_memory(
    body: MemoryCreateIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Crea un recuerdo propio desde el panel de memoria."""
    duplicate = db.query(UserMemory).filter(
        UserMemory.user_id == user.id,
        UserMemory.kind == body.kind,
        UserMemory.content == body.content,
    ).first()
    if duplicate:
        return _memory_json(duplicate)
    memory = UserMemory(user_id=user.id, kind=body.kind, content=body.content, source="panel")
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return _memory_json(memory)


@router.put("/api/user/memories/{memory_id}")
def update_user_memory(
    memory_id: int,
    body: MemoryUpdateIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Edita un recuerdo sin permitir acceder a otro usuario."""
    memory = db.query(UserMemory).filter(
        UserMemory.id == memory_id,
        UserMemory.user_id == user.id,
    ).first()
    if memory is None:
        raise HTTPException(status_code=404, detail="No se encontró ese recuerdo")
    duplicate = db.query(UserMemory).filter(
        UserMemory.user_id == user.id,
        UserMemory.kind == memory.kind,
        UserMemory.content == body.content,
        UserMemory.id != memory.id,
    ).first()
    if duplicate:
        db.delete(memory)
        db.commit()
        return _memory_json(duplicate)
    memory.content = body.content
    memory.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(memory)
    return _memory_json(memory)


@router.delete("/api/user/memories/{memory_id}")
def delete_user_memory(
    memory_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Borra un recuerdo propio."""
    memory = db.query(UserMemory).filter(
        UserMemory.id == memory_id,
        UserMemory.user_id == user.id,
    ).first()
    if memory is None:
        raise HTTPException(status_code=404, detail="No se encontró ese recuerdo")
    db.query(MemoryLink).filter(
        MemoryLink.user_id == user.id,
        (MemoryLink.from_memory_id == memory.id) | (MemoryLink.to_memory_id == memory.id),
    ).delete(synchronize_session=False)
    db.delete(memory)
    db.commit()
    return {"status": "ok"}


# ============= PROACTIVIDAD CONTROLADA =============

@router.get("/api/user/proactive-alerts")
def user_proactive_alerts(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Devuelve avisos de recordatorios próximos o vencidos, sin ejecutar acciones."""
    now = datetime.utcnow()
    horizon = now + timedelta(hours=24)
    rows = db.query(Reminder).filter(
        Reminder.user_id == user.id,
        Reminder.status == "pendiente",
        Reminder.due_at <= horizon,
    ).order_by(Reminder.due_at).limit(12).all()
    alerts = []
    for row in rows:
        late = row.due_at < now
        alerts.append({
            "key": f"reminder:{row.id}:{row.due_at.isoformat()}",
            "kind": "reminder_overdue" if late else "reminder_upcoming",
            "title": "Recordatorio vencido" if late else "Recordatorio próximo",
            "text": row.text,
            "due_at": row.due_at.isoformat() if row.due_at else None,
        })
    return {"alerts": alerts, "generated_at": now.isoformat()}


# ============= PERCEPCIÓN EN MODO LECTURA =============

@router.get("/api/user/perception")
async def user_perception(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Resume pendientes propios y conexiones, sin ejecutar cambios."""
    caps = admin_capabilities() if user.is_admin else capabilities_from_user(user)
    now = datetime.utcnow()
    reminders = []
    notes = []
    if caps.has("reminders"):
        reminders = [
            {
                "id": row.id,
                "text": row.text,
                "due_at": row.due_at.isoformat() if row.due_at else None,
                "repeat": row.repeat,
            }
            for row in db.query(Reminder).filter(
                Reminder.user_id == user.id,
                Reminder.status == "pendiente",
            ).order_by(Reminder.due_at).limit(8).all()
        ]
    if caps.has("notes"):
        notes = [
            {
                "id": row.id,
                "text": row.text[:240],
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in db.query(Note).filter(
                Note.user_id == user.id,
            ).order_by(Note.created_at.desc(), Note.id.desc()).limit(8).all()
        ]

    google = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    telegram = db.query(TelegramLink).filter(TelegramLink.user_id == user.id).first()
    result = {
        "generated_at": now.isoformat(),
        "reminders": reminders,
        "notes": notes,
        "calendar": [],
        "emails": [],
        "google_connected": google is not None,
        "google_email": google.email if google else None,
        "telegram_connected": bool(telegram and telegram.chat_id),
        "errors": [],
    }

    if _sessions is None:
        result["errors"].append("El chat no está disponible para consultar Google.")
        return result

    session = _sessions.get(_session_key(user.id, "perception"))
    _bind_identity(session, user, db)
    google_tasks = []
    if caps.has("calendar") and google is not None:
        google_tasks.append(("calendar", gcalendar.list_events(days=7, _session=session)))
    if caps.has("email") and google is not None:
        google_tasks.append(("emails", gmail.list_emails(unread_only=True, max_results=5, _session=session)))
    if google_tasks:
        values = await asyncio.gather(*(task for _, task in google_tasks), return_exceptions=True)
        for (name, _), value in zip(google_tasks, values):
            if isinstance(value, Exception):
                result["errors"].append(f"No se pudo consultar {name}.")
            elif isinstance(value, dict) and value.get("error"):
                result["errors"].append(value["error"])
            elif name == "calendar":
                result["calendar"] = value.get("eventos", [])
            elif name == "emails":
                result["emails"] = value.get("correos", [])
    return result


# ============= CHAT Y VOZ DEL USUARIO =============

def _session_key(user_id: int, client_sub: Optional[str]) -> str:
    """Clave de sesión del chat, construida SIEMPRE en el servidor.

    El identificador que manda el navegador solo separa conversaciones propias:
    se limpia de caracteres raros y se prefija con el id del token, de modo que
    un valor falso no puede alcanzar la sesión de otro usuario.
    """
    sub = re.sub(r"[^A-Za-z0-9_-]", "", client_sub or "")[:64]
    return f"user:{user_id}:{sub or 'default'}"


def _bind_identity(session, user: User, db: Session, query: str | None = None) -> None:
    """Fija en la sesión QUIÉN es el usuario y QUÉ puede hacer.

    Se hace en cada mensaje, no solo al crear la sesión: si el administrador
    cambia los permisos o el usuario conecta su Google, el siguiente mensaje ya lo
    nota, sin tener que esperar a que caduque la sesión (que dura 2 horas).

    La sesión es la única fuente que ven las herramientas, y las herramientas no
    la reciben del modelo: por eso un usuario no puede actuar como otro.
    """
    session.user_id = user.id
    session.capabilities = (
        admin_capabilities(user.id) if user.is_admin else capabilities_from_user(user)
    )
    session.addressing_instruction = user.addressing_instruction or ""

    account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    session.google_linked = account.email if account is not None else None
    spotify_account = db.query(SpotifyAccount).filter(SpotifyAccount.user_id == user.id).first()
    session.spotify_linked = (spotify_account.display_name or spotify_account.email) if spotify_account is not None else None

    link = db.query(TelegramLink).filter(TelegramLink.user_id == user.id).first()
    session.telegram_linked = bool(link and link.chat_id)

    link_memories(db, user.id)
    session.personal_memory = load_memories(db, user.id, "personal")
    session.operational_memory = load_memories(db, user.id, "operational")
    session.linked_memory = linked_memories_block(db, user.id)
    session.graph_memory = graph_context(db, user.id, query=query)
    session.neural_memory = neural_memory_context(db, user.id, query or "")


@router.get("/api/user/neural-network")
async def neural_network_status(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Estado de la red neuronal propia y su autoaprendizaje controlado."""
    return model_status(db, user.id)


@router.post("/api/user/neural-network/train")
async def neural_network_train(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Reentrena la red local con las experiencias aprobadas del usuario."""
    result = train_user_model(db, user.id)
    status_data = model_status(db, user.id)
    status_data.update(result)
    return status_data


@router.post("/api/user/voice-profile")
async def register_voice_profile(
    audio: list[UploadFile] = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Registra o reemplaza la huella de voz del usuario."""
    samples = [await item.read() for item in audio]
    samples = [item for item in samples if len(item) >= 10_000]
    if len(samples) < 6:
        raise HTTPException(status_code=422, detail="Necesitas 6 muestras de voz válidas")
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
    """Transcribe y ejecuta la orden; si hay perfil de voz, valida al hablante primero."""
    data = await audio.read()
    if len(data) < 1_000:
        raise HTTPException(status_code=422, detail="El audio está vacío o es demasiado corto")

    profile = db.query(Profile).filter(
        Profile.user_id == user.id,
        Profile.name == "Voz principal",
        Profile.is_authorized.is_(True),
    ).first()
    score: float | None = None
    if profile is None or not profile.voice_print or not profile.is_authorized:
        raise HTTPException(status_code=403, detail="Registra tu perfil de voz antes de usar comandos por voz")
    try:
        verified, score = await asyncio.to_thread(voice.verify, data, profile.voice_print, ".webm")
    except ValueError as exc:
        # Audio silencioso o sin voz: no es un fallo del servidor.
        logger.warning("Audio sin voz para usuario %s: %s", user.id, exc)
        raise HTTPException(status_code=422, detail="No se detectó voz en la grabación")
    except Exception as exc:
        logger.exception("Falló la verificación de voz")
        raise HTTPException(status_code=500, detail=f"No se pudo verificar la voz: {exc}")
    if not verified:
        logger.warning("Voz no reconocida para usuario %s: score=%.4f threshold=%s", user.id, score, os.getenv("IGRIS_VOICE_THRESHOLD", "0.40"))
        raise HTTPException(status_code=403, detail=f"Voz no reconocida (similitud {score:.2f})")

    try:
        text = await transcribe_user_audio(data, audio.content_type or "audio/webm")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"No se pudo transcribir el audio: {exc}")
    if not text:
        raise HTTPException(status_code=422, detail="No se entendió la orden")

    if _sessions is None:
        return {"status": "error", "message": "El chat no está disponible en este momento."}
    session = _sessions.get(_session_key(user.id, session_id))
    _bind_identity(session, user, db, query=text)
    remember_from_text(db, user.id, text, session_key=_session_key(user.id, session_id))
    session.neural_memory = neural_memory_context(db, user.id, text)
    try:
        reply = await session.say(text)
        learn_from_assistant(db, user.id, reply, source="chat", session_key=_session_key(user.id, session_id))
        result = {"status": "ok", "text": text, "reply": reply}
        if score is not None:
            result["voice_score"] = round(score, 3)
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.websocket("/api/user/voice-ws")
async def user_voice_ws(websocket: WebSocket) -> None:
    """Canal de voz por fragmentos para el área de usuarios.

    El primer mensaje debe ser JSON ``hello`` con el JWT, session_id y mime_type.
    Los siguientes mensajes binarios son fragmentos WebM; ``end`` inicia la
    verificación, transcripción y respuesta. El POST /voice-chat se conserva
    como respaldo para navegadores o proxies sin WebSocket.
    """
    await websocket.accept()
    # Ninguna conexión del pool se retiene durante el socket. Un socket abierto
    # puede durar minutos esperando a que el usuario hable; si guardara su sesión
    # de BD todo ese tiempo, cada oyente ocuparía una conexión del pool y unos
    # pocos usuarios concurrentes agotarían el pool para toda la aplicación.
    # Cada bloque abre su sesión y la cierra al terminar.
    try:
        hello = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=10))
        if hello.get("type") != "hello":
            await websocket.send_json({"type": "error", "message": "Se esperaba la inicialización de voz."})
            await websocket.close(code=1008)
            return

        try:
            with SessionLocal() as db:
                user = _user_from_bearer(f"Bearer {hello.get('token', '')}", db)
                db.expunge(user)
        except HTTPException as exc:
            await websocket.send_json({"type": "error", "message": str(exc.detail)})
            await websocket.close(code=1008)
            return

        mime_type = str(hello.get("mime_type") or "audio/webm")[:100]
        session_id = str(hello.get("session_id") or "")[:64]
        await websocket.send_json({"type": "ready"})
        audio_parts: list[bytes] = []
        audio_size = 0
        max_audio_bytes = 12 * 1024 * 1024
        deepgram_socket = None
        deepgram_reader = None
        deepgram_transcripts: list[str] = []
        # Deepgram Live cierra la conexión si no recibe audio en ~10 s. El hello y
        # la comprobación del token pueden tardar, y el usuario aún no ha hablado,
        # así que la conexión se abre con el PRIMER fragmento, no al aceptar.
        live_params = None
        configured_stt = get_settings().get_stt_config()
        deepgram_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if configured_stt.get("provider") == "deepgram" and deepgram_key:
            live_params = {
                "model": configured_stt.get("cloud_model") or os.getenv("DEEPGRAM_MODEL", "nova-3"),
                "language": configured_stt.get("language") or os.getenv("DEEPGRAM_LANGUAGE", "es"),
                "smart_format": "true", "punctuate": "true", "interim_results": "false",
                "container": "webm" if "webm" in mime_type.lower() else "ogg",
            }

        async def open_deepgram() -> None:
            nonlocal deepgram_socket, deepgram_reader
            import websockets
            live_url = f"{DEEPGRAM_LIVE_URL}?{httpx.QueryParams(live_params)}"
            try:
                deepgram_socket = await websockets.connect(
                    live_url,
                    extra_headers={"Authorization": f"Token {deepgram_key}"},
                    open_timeout=10,
                    close_timeout=5,
                )
            except Exception:
                logger.exception("No se pudo abrir Deepgram Live; se usará STT por lotes")
                deepgram_socket = None
                return

            async def read_deepgram():
                try:
                    async for raw_result in deepgram_socket:
                        result = json.loads(raw_result)
                        if result.get("is_final"):
                            alternatives = result.get("channel", {}).get("alternatives", [])
                            phrase = (alternatives[0].get("transcript") or "").strip() if alternatives else ""
                            if phrase:
                                deepgram_transcripts.append(phrase)
                except Exception:
                    # Un cierre de Deepgram no debe propagarse como tarea huérfana:
                    # la transcripción por lotes sigue disponible al final.
                    logger.warning("Deepgram Live se cerró antes de terminar el audio")

            deepgram_reader = asyncio.create_task(read_deepgram())

        while True:
            message = await websocket.receive()
            if message.get("bytes") is not None:
                chunk = message["bytes"]
                audio_size += len(chunk)
                if audio_size > max_audio_bytes:
                    await websocket.send_json({"type": "error", "message": "La grabación supera el límite permitido."})
                    await websocket.close(code=1009)
                    return
                audio_parts.append(chunk)
                # La conexión con Deepgram se abre aquí, con audio real en cola.
                if live_params is not None and deepgram_socket is None and deepgram_reader is None:
                    await open_deepgram()
                if deepgram_socket is not None:
                    try:
                        await deepgram_socket.send(chunk)
                    except Exception:
                        logger.exception("Falló el envío de audio a Deepgram Live")
                        await deepgram_socket.close()
                        deepgram_socket = None
                continue

            raw = message.get("text")
            if raw is None:
                continue
            event = json.loads(raw)
            if event.get("type") == "cancel":
                await websocket.send_json({"type": "cancelled"})
                return
            if event.get("type") != "end":
                continue
            break

        if deepgram_socket is not None:
            try:
                await deepgram_socket.send(json.dumps({"type": "CloseStream"}))
            except Exception:
                logger.exception("Falló el cierre de Deepgram Live")
        if deepgram_reader is not None:
            try:
                await asyncio.wait_for(deepgram_reader, timeout=3)
            except Exception:
                deepgram_reader.cancel()
        if deepgram_socket is not None:
            try:
                await deepgram_socket.close()
            except Exception:
                pass
        audio = b"".join(audio_parts)
        if len(audio) < 1_000:
            await websocket.send_json({"type": "error", "message": "El audio está vacío o es demasiado corto."})
            return

        with SessionLocal() as db:
            profile = db.query(Profile).filter(
                Profile.user_id == user.id,
                Profile.name == "Voz principal",
                Profile.is_authorized.is_(True),
            ).first()
            voice_print = profile.voice_print if profile is not None else None
        if not voice_print:
            await websocket.send_json({"type": "error", "message": "Registra tu perfil de voz antes de usar comandos por voz."})
            return

        await websocket.send_json({"type": "state", "state": "processing"})
        try:
            verified, score = await asyncio.to_thread(voice.verify, audio, voice_print, ".webm")
        except ValueError:
            logger.warning("Audio sin voz en WebSocket para usuario %s", user.id)
            await websocket.send_json({"type": "error", "reason": "no_audio", "message": "No se detectó voz en la grabación."})
            return
        except Exception:
            logger.exception("Falló la verificación de voz por WebSocket")
            await websocket.send_json({"type": "error", "message": "No se pudo verificar la voz."})
            return
        if not verified:
            await websocket.send_json({"type": "error", "reason": "voice", "message": f"Voz no reconocida (similitud {score:.2f})."})
            return

        try:
            text = " ".join(deepgram_transcripts).strip()
            if not text:
                text = await transcribe_user_audio(audio, mime_type)
        except Exception:
            logger.exception("Falló la transcripción de voz por WebSocket")
            await websocket.send_json({"type": "error", "message": "No se pudo transcribir el audio."})
            return
        if not text:
            await websocket.send_json({"type": "error", "message": "No se entendió la orden."})
            return

        await websocket.send_json({"type": "transcript", "text": text, "voice_score": round(score, 3)})
        if _sessions is None:
            await websocket.send_json({"type": "error", "message": "El chat no está disponible en este momento."})
            return

        session_key = _session_key(user.id, session_id)
        session = _sessions.get(session_key)
        # Todo el trabajo de base de datos del turno va en un bloque corto: la
        # conexión vuelve al pool antes de llamar al modelo, que es lo lento.
        with SessionLocal() as db:
            _bind_identity(session, user, db, query=text)
            remember_from_text(db, user.id, text, session_key=session_key)

        # Cada frase se sintetiza y se envía en cuanto el modelo la termina: no se
        # espera a la respuesta completa. El texto también se envía por frases para
        # que el cliente pueda mostrarlo mientras IGRIS habla.
        tts_mime = "audio/wav" if tts.TTS_PROVIDER == "local" else "audio/mpeg"
        limited = {"chars": 0}

        async def speak(sentence: str) -> None:
            sentence = sentence.strip()
            if not sentence:
                return
            # Tope global de caracteres para no sintetizar respuestas enormes.
            room = TTS_MAX_CHARS - limited["chars"]
            if room <= 0:
                return
            sentence = sentence[:room]
            limited["chars"] += len(sentence)
            await websocket.send_json({"type": "sentence", "text": sentence})
            try:
                if tts.TTS_PROVIDER == "edge" and getattr(tts, "_edge_available", False):
                    voice_name = os.environ.get("IGRIS_TTS_VOICE", tts._TTS_CFG.get("voice", "es-ES-AlvaroNeural"))
                    communicator = tts.edge_tts.Communicate(
                        sentence, voice_name, rate=tts.TTS_RATE, pitch=tts.TTS_PITCH, volume="+0%",
                    )
                    buffer = bytearray()
                    async for frame in communicator.stream():
                        if frame.get("type") == "audio" and frame.get("data"):
                            buffer.extend(frame["data"])
                    if not buffer:
                        return
                    await websocket.send_bytes(bytes(buffer))
                else:
                    await websocket.send_bytes(await tts.synthesize(sentence))
                await websocket.send_json({"type": "tts_chunk"})
            except Exception:
                logger.exception("Falló el TTS de una frase")

        # Buzón secuencial: el texto llega más rápido que el audio, así que las
        # frases se encolan y se sintetizan en orden sin bloquear al modelo.
        queue: asyncio.Queue = asyncio.Queue()
        buffer_text = ""

        async def worker() -> None:
            while True:
                sentence = await queue.get()
                if sentence is None:
                    queue.task_done()
                    return
                await speak(sentence)
                queue.task_done()

        async def on_delta(fragment: str) -> None:
            nonlocal buffer_text
            buffer_text += fragment
            # Cortar en fin de frase cuando el fragmento ya la contiene.
            while True:
                match = _SENTENCE_END.search(buffer_text)
                if not match:
                    return
                sentence, buffer_text = buffer_text[:match.end()], buffer_text[match.end():]
                queue.put_nowait(sentence)

        speaker = asyncio.create_task(worker())
        await websocket.send_json({"type": "tts_start", "mime_type": tts_mime})
        try:
            reply = await session.say_stream(text, on_delta)
        except Exception as exc:
            logger.exception("Falló el chat de voz por WebSocket (stream)")
            queue.put_nowait(None)
            await speaker
            # El mensaje distingue la causa: antes todo acababa como "no se pudo
            # procesar", y el frontend lo confundía con un fallo de voz.
            await websocket.send_json({
                "type": "error",
                "reason": "model",
                "message": f"Los proveedores de IA no respondieron: {exc}",
            })
            return

        # Resto sin puntuación final.
        if buffer_text.strip():
            queue.put_nowait(buffer_text)
        queue.put_nowait(None)
        await speaker

        try:
            with SessionLocal() as db:
                learn_from_assistant(db, user.id, reply, source="chat", session_key=session_key)
        except Exception:
            logger.exception("No se pudo guardar el aprendizaje de la respuesta de voz")
        await websocket.send_json({"type": "reply", "reply": reply})
        await websocket.send_json({"type": "tts_end"})
    except (WebSocketDisconnect, asyncio.TimeoutError, json.JSONDecodeError):
        return
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


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
    chat_started = time.perf_counter()
    chat_id = secrets.token_hex(4)
    logger.info("CHAT_START id=%s user=%s text_chars=%d", chat_id, user.id, len(text))
    session = _sessions.get(_session_key(user.id, payload.session_id))
    session.trace_id = chat_id
    # Identidad y permisos SIEMPRE frescos, y la instrucción de trato: si el admin
    # la cambió en caliente, el próximo mensaje ya refleja el nuevo trato.
    prep_started = time.perf_counter()
    _bind_identity(session, user, db, query=text)
    remember_from_text(db, user.id, text, session_key=_session_key(user.id, payload.session_id))
    session.neural_memory = neural_memory_context(db, user.id, text)
    logger.info("CHAT_PREP_END id=%s elapsed_ms=%.1f", chat_id, (time.perf_counter() - prep_started) * 1000)
    try:
        model_started = time.perf_counter()
        reply = await session.say(text, {"image_data": payload.image_data, "image_mime": payload.image_mime})
        logger.info("CHAT_MODEL_END id=%s elapsed_ms=%.1f reply_chars=%d", chat_id, (time.perf_counter() - model_started) * 1000, len(reply or ""))
        learn_from_assistant(db, user.id, reply, source="chat", session_key=_session_key(user.id, payload.session_id))
        # La interfaz muestra la ruta que confirmó el agente local.
        created = list(getattr(session, "documents", []) or [])
        session.documents = []
        logger.info("CHAT_END id=%s total_ms=%.1f", chat_id, (time.perf_counter() - chat_started) * 1000)
        return {"status": "ok", "reply": reply, "documents": created}
    except Exception as e:
        logger.exception("CHAT_ERROR id=%s total_ms=%.1f", chat_id, (time.perf_counter() - chat_started) * 1000)
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
_spotify_oauth_states: dict[str, tuple] = {}
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


def _consume_spotify_oauth_state(state: str) -> Optional[int]:
    with _oauth_lock:
        now = time.time()
        for key, (_, created) in list(_spotify_oauth_states.items()):
            if now - created > OAUTH_STATE_TTL:
                _spotify_oauth_states.pop(key, None)
        entry = _spotify_oauth_states.pop(state or "", None)
    if entry is None or time.time() - entry[1] > OAUTH_STATE_TTL:
        return None
    return entry[0]


def _issue_spotify_oauth_state(user_id: int) -> str:
    state = secrets.token_urlsafe(32)
    with _oauth_lock:
        _spotify_oauth_states[state] = (user_id, time.time())
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
    account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    spotify_account = db.query(SpotifyAccount).filter(SpotifyAccount.user_id == user.id).first()
    from core.tools import google_client, spotify

    tv_boxes = db.query(TvBoxToken).filter(
        TvBoxToken.user_id == user.id,
        TvBoxToken.revoked.is_(False),
    ).order_by(TvBoxToken.created_at.desc()).all()
    return {
        "features": sorted(caps.features, key=FEATURE_ORDER.index),
        "google": _google_status(user, db),
        "youtube": {
            "app_configured": google_client.oauth_configured(),
            "connected": account is not None,
            "email": account.email if account is not None else None,
            "error": account.last_error if account is not None else None,
            "needs_youtube": caps.has("youtube"),
        },
        "spotify": {
            "app_configured": spotify.oauth_configured(),
            "connected": spotify_account is not None,
            "email": spotify_account.email if spotify_account is not None else None,
            "display_name": spotify_account.display_name if spotify_account is not None else None,
            "error": spotify_account.last_error if spotify_account is not None else None,
            "needs_spotify": caps.has("spotify"),
        },
        "telegram": {
            "linked": bool(link and link.chat_id),
            "username": link.username if link else None,
            "bot_url": None,  # lo rellena el frontend con la variable de build
        },
        "tv_boxes": [{
            "id": row.id,
            "device_name": row.device_name,
            "model": row.model,
            "android_version": row.android_version,
            "online": row.id in _connections,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        } for row in tv_boxes],
    }


class UserTvBoxPairingCode(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    expires_minutes: int = Field(default=10, ge=1, le=30)


class UserTvBoxCommand(BaseModel):
    action: str = Field(pattern="^(launch_app|key|volume|device_info)$")
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/user/tvbox/pairing-codes")
def create_user_tvbox_pairing_code(
    payload: UserTvBoxPairingCode,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Crea un código temporal enlazado al usuario autenticado, nunca a otro."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    expires_at = datetime.utcnow() + timedelta(minutes=payload.expires_minutes)
    db.query(TvBoxPairingCode).filter(
        TvBoxPairingCode.user_id == user.id,
        TvBoxPairingCode.used.is_(False),
        TvBoxPairingCode.expires_at < datetime.utcnow(),
    ).update({TvBoxPairingCode.used: True})
    db.add(TvBoxPairingCode(
        code_hash=_digest(code),
        user_id=user.id,
        device_name=payload.device_name.strip(),
        expires_at=expires_at,
    ))
    db.commit()
    return {
        "code": code,
        "device_name": payload.device_name.strip(),
        "expires_at": expires_at.isoformat(),
        "websocket_url": "wss://igris.zottagroup.com/api/tvbox/ws",
    }


@router.post("/api/user/tvbox/{device_id}/command")
async def send_user_tvbox_command(
    device_id: int,
    payload: UserTvBoxCommand,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.query(TvBoxToken).filter(
        TvBoxToken.id == device_id,
        TvBoxToken.user_id == user.id,
        TvBoxToken.revoked.is_(False),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="TV Box no encontrado")
    websocket = _connections.get(device_id)
    if websocket is None:
        raise HTTPException(status_code=409, detail="El TV Box no está conectado")
    await websocket.send_json({"type": "command", "action": payload.action, **payload.params})
    return {"ok": True, "device_id": device_id}


@router.delete("/api/user/tvbox/{device_id}")
def delete_user_tvbox(
    device_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.query(TvBoxToken).filter(
        TvBoxToken.id == device_id,
        TvBoxToken.user_id == user.id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="TV Box no encontrado")
    db.delete(row)
    db.commit()
    _connections.pop(device_id, None)
    return {"ok": True}


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
    if not any(caps.has(f) for f in ("email", "calendar", "calendar_write", "youtube")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No tienes ninguna función de Google habilitada. "
                "Pídele al administrador que te active correo, calendario o YouTube."
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
<meta http-equiv="refresh" content="3;url=https://webigris.zottagroup.com/?open=connections">
<script>setTimeout(()=>{window.location.replace('https://webigris.zottagroup.com/?open=connections')},3000)</script>"""
        return HTMLResponse(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Igris</title>{redirect_snippet}</head>
<body style="margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
             display:flex;align-items:center;justify-content:center;height:100vh">
  <div style="text-align:center;max-width:32rem;padding:2rem">
    <h1 style="color:{color};font-size:1.25rem;margin:0 0 .75rem">{escape(title)}</h1>
    <p style="color:#94a3b8;line-height:1.6;margin:0">{escape(detail)}</p>
    {'<p style="color:#64748b;font-size:.875rem;margin-top:1.5rem">Redirigiendo a Igris en unos segundos… <a href="https://webigris.zottagroup.com/" style="color:#6366f1;text-decoration:none">Ir ahora</a></p>' if ok else '<p style="color:#64748b;font-size:.875rem;margin-top:1.5rem">Puedes cerrar esta pestaña y volver a Igris.</p>'}
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
    return _page("Cuenta conectada", f"Ya puedes pedirle a Igris administrar tu correo, calendario y listas de YouTube.", True)


@router.get("/api/user/youtube/start")
def youtube_start(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Inicia el mismo consentimiento OAuth con el alcance de YouTube habilitado."""
    caps = admin_capabilities() if user.is_admin else capabilities_from_user(user)
    if not caps.has("youtube"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="YouTube no está habilitado para tu usuario.")
    return google_start(user, db)


@router.delete("/api/user/youtube")
def youtube_disconnect(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Desconecta la cuenta de Google usada por YouTube y las demás funciones Google."""
    return google_disconnect(user, db)


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


@router.get("/api/user/spotify/start")
def spotify_start(user: User = Depends(require_user)):
    from core.tools import spotify
    caps = admin_capabilities() if user.is_admin else capabilities_from_user(user)
    if not caps.has("spotify"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Spotify no está habilitado para tu usuario.")
    if not spotify.oauth_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Spotify no está configurado en el servidor.")
    return {"auth_url": spotify.authorization_url(_issue_spotify_oauth_state(user.id))}


@router.get("/api/user/spotify/callback")
async def spotify_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None, db: Session = Depends(get_db)):
    from core import crypto
    from core.tools import spotify
    from fastapi.responses import HTMLResponse
    from html import escape

    def page(title: str, detail: str, ok: bool):
        redirect = "" if not ok else '<meta http-equiv="refresh" content="3;url=https://webigris.zottagroup.com/?open=connections">'
        return HTMLResponse(f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>IGRIS</title>{redirect}</head><body style='font-family:system-ui;background:#0f172a;color:#e2e8f0;display:flex;justify-content:center;align-items:center;height:100vh'><main style='text-align:center;max-width:32rem'><h1>{escape(title)}</h1><p>{escape(detail)}</p></main></body></html>")
    if error:
        return page("No se conectó Spotify", error, False)
    user_id = _consume_spotify_oauth_state(state or "")
    if not code or user_id is None:
        return page("Solicitud caducada", "Vuelve a intentarlo desde Conexiones.", False)
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        return page("Cuenta no válida", "Tu usuario ya no está disponible.", False)
    client_id, client_secret = spotify.client_config()
    basic = __import__("base64").b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(spotify.TOKEN_URL, data={"grant_type": "authorization_code", "code": code, "redirect_uri": spotify.redirect_uri()}, headers={"Authorization": f"Basic {basic}"})
            payload = response.json()
            if response.status_code != 200:
                return page("Spotify rechazó la autorización", payload.get("error_description") or payload.get("error") or str(response.status_code), False)
            access = payload.get("access_token")
            profile = await client.get("https://api.spotify.com/v1/me", headers={"Authorization": f"Bearer {access}"})
            profile_data = profile.json() if profile.status_code == 200 else {}
    except Exception as exc:
        logger.exception("Fallo al conectar Spotify")
        return page("No hubo conexión con Spotify", str(exc), False)
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        return page("Spotify no entregó refresh token", "Vuelve a autorizar la aplicación desde Spotify.", False)
    try:
        encrypted = crypto.encrypt(refresh_token)
    except Exception:
        return page("No se pudo guardar la conexión", "El servidor no pudo cifrar el permiso de Spotify.", False)
    account = db.query(SpotifyAccount).filter(SpotifyAccount.user_id == user.id).first()
    if account is None:
        account = SpotifyAccount(user_id=user.id, refresh_token_enc=encrypted)
        db.add(account)
    else:
        account.refresh_token_enc = encrypted
        account.last_error = None
    account.email = profile_data.get("email")
    account.display_name = profile_data.get("display_name")
    account.spotify_user_id = profile_data.get("id")
    account.scopes = payload.get("scope", spotify.SCOPES)
    db.commit()
    spotify.forget_token(user.id)
    return page("Spotify conectado", "Ya puedes pedirle a Igris buscar música y administrar tus playlists.", True)


@router.delete("/api/user/spotify")
def spotify_disconnect(user: User = Depends(require_user), db: Session = Depends(get_db)):
    from core.tools import spotify
    account = db.query(SpotifyAccount).filter(SpotifyAccount.user_id == user.id).first()
    if account is not None:
        db.delete(account)
        db.commit()
    spotify.forget_token(user.id)
    return {"success": True, "message": "Cuenta de Spotify desconectada"}


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

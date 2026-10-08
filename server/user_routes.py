"""
IGRIS — Área de usuarios (/u) y panel de administración de usuarios.

Dos superficies de autenticación que NO se mezclan:

  /api/admin/*  ->  header X-Igris-Key, exactamente el mismo mecanismo que la
                    pantalla /acceso (se reutiliza require_key de main.py, con
                    su comparación en tiempo constante y su límite de intentos).
  /api/user/*   ->  header Authorization: Bearer <JWT> con role="user".

Un token de usuario NUNCA sirve en /api/admin, y la clave de admin NUNCA sirve
en /api/user. El rol va firmado dentro del token, así que el navegador no puede
añadirlo ni modificarlo.

El chat de cada usuario se aísla por una clave construida en el servidor:
    user:<id del token>:<identificador de conversación>
El identificador que envía el navegador solo separa las conversaciones propias
de ese usuario; no puede alcanzar la sesión de otro.
"""
from __future__ import annotations

import hmac
import re
import secrets
import time
from collections import deque
from datetime import timedelta
from threading import Lock
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
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
from core.database import User, get_db

router = APIRouter()

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
) -> None:
    """Exige la clave única de la pantalla /acceso.

    Reutiliza require_key de main.py para que el mecanismo sea idéntico al que
    ya funciona: misma comparación en tiempo constante, mismo límite de
    intentos por IP y mismo mensaje de error. La importación es local para
    evitar una dependencia circular (main.py importa este módulo).
    """
    from server.main import require_key

    await require_key(request, x_igris_key)


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


class ChatIn(BaseModel):
    text: str
    session_id: Optional[str] = None


class TtsIn(BaseModel):
    text: str


def _public_user(u: User) -> dict[str, Any]:
    """Serializa un usuario SIN exponer nunca el hash de la contraseña."""
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "is_admin": bool(u.is_admin),
        "is_active": bool(u.is_active),
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ============= ADMINISTRACIÓN DE USUARIOS =============

@router.get("/api/admin/users")
def list_users(
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.id.asc()).all()
    return {"users": [_public_user(u) for u in users]}


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
    db.add(user)
    db.commit()
    db.refresh(user)
    return _public_user(user)


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

    db.commit()
    db.refresh(user)
    return _public_user(user)


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
        "user": _public_user(user),
    }


@router.get("/api/user/me")
def user_me(user: User = Depends(require_user)):
    """Comprueba que la sesión sigue viva y devuelve los datos del usuario."""
    return _public_user(user)


# ============= CHAT Y VOZ DEL USUARIO =============

def _session_key(user_id: int, client_sub: Optional[str]) -> str:
    """Clave de sesión del chat, construida SIEMPRE en el servidor.

    El identificador que manda el navegador solo separa conversaciones propias:
    se limpia de caracteres raros y se prefija con el id del token, de modo que
    un valor falso no puede alcanzar la sesión de otro usuario.
    """
    sub = re.sub(r"[^A-Za-z0-9_-]", "", client_sub or "")[:64]
    return f"user:{user_id}:{sub or 'default'}"


@router.post("/api/user/chat")
async def user_chat(payload: ChatIn, user: User = Depends(require_user)):
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


# ============= UTILIDAD =============

def generate_secret_key() -> str:
    """Genera una SECRET_KEY válida para pegar en Coolify."""
    return secrets.token_urlsafe(48)


def constant_time_check(a: str, b: str) -> bool:
    """Comparación en tiempo constante (por si se necesita en el futuro)."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

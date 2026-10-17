"""
IGRIS - Servidor FastAPI simplificado para solo chat con Igris
"""
import asyncio
import logging
import os
import secrets
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from jose import JWTError, jwt

from core import Brain, config, stt          # ← añadido stt
from core import database, telegram_links
from core.capabilities import admin_capabilities, capabilities_from_user
from core.database import GoogleAccount, Profile, TelegramLink, User
from core.auth import ALGORITHM, SECRET_KEY, hash_password
from core.settings_manager import get_settings
from core.memory import load_memories, remember_from_text
from core import tts, voice
from core.database import init_db, engine
from core.session_store import SessionStore
from core.scheduler import run_reminder_loop

# Telegram imports
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes

# Sin esto, los logger.info de core/ (brain, tools) no aparecen en los logs de Coolify
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Inicializar BD: crea la base de datos si falta, espera a PostgreSQL si aún
# está arrancando y crea las tablas que falten (recordatorios y notas incluidas).
init_db()


def _ensure_bootstrap_admin() -> None:
    """Crea el primer administrador si Coolify proporciona sus credenciales."""
    username = os.getenv("IGRIS_ADMIN_USERNAME", "").strip()
    email = os.getenv("IGRIS_ADMIN_EMAIL", "").strip()
    password = os.getenv("IGRIS_ADMIN_PASSWORD", "")
    if not username or not email or not password:
        logger.info(
            "No se creó administrador inicial: define IGRIS_ADMIN_USERNAME, "
            "IGRIS_ADMIN_EMAIL e IGRIS_ADMIN_PASSWORD si la base está vacía."
        )
        return

    db = database.SessionLocal()
    try:
        if db.query(User).filter(User.is_admin.is_(True)).first():
            return
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            existing.is_admin = True
            existing.is_active = True
            db.commit()
            logger.info("Usuario existente promovido a administrador: %s", existing.username)
            return
        admin = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.info("Administrador inicial creado: %s", username)
    finally:
        db.close()


_ensure_bootstrap_admin()

app = FastAPI(
    title="IGRIS Chat",
    description="Servidor de chat simple con Igris",
    version="1.0.0"
)

# CORS - solo el frontend (y el servidor de desarrollo local).
# Sin allow_credentials: ni la clave ni el token viajan en cookies.
# El preflight (OPTIONS) lo responde este middleware antes de llegar a las rutas,
# así que nunca pasa por require_key.
#
# IMPORTANTE: todo header que envíe el frontend tiene que estar en allow_headers,
# y todo método que use tiene que estar en allow_methods. Si falta uno, el
# navegador bloquea la petición ANTES de enviarla y el error que se ve en
# pantalla es un fallo de CORS, no el error real del servidor.
#   - X-Igris-Key  -> pantalla de acceso y panel (una sola clave)
#   - Authorization -> área de usuarios (/u), token Bearer
#   - DELETE        -> borrar usuarios desde el panel
origins = [
    "https://webigris.zottagroup.com",
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Igris-Key", "Authorization"],
)

# ============= ACCESO CON CLAVE ÚNICA =============
# La clave vive solo en la variable de entorno IGRIS_ACCESS_KEY (Coolify).
# Falla cerrado: si la variable no existe o está vacía, TODAS las rutas
# protegidas responden 401.
ACCESS_KEY = os.getenv("IGRIS_ACCESS_KEY", "").strip()
if not ACCESS_KEY:
    logger.error(
        "IGRIS_ACCESS_KEY no está definida o está vacía: "
        "todas las rutas protegidas rechazarán las peticiones."
    )

# La SECRET_KEY firma los tokens de los usuarios del área /u. Si no está
# definida, core/auth.py genera una temporal: el área de usuarios funciona,
# pero cada reinicio invalida las sesiones abiertas.
if not os.getenv("SECRET_KEY", "").strip():
    logger.warning(
        "SECRET_KEY no está definida: los usuarios tendrán que volver a "
        "iniciar sesión en cada reinicio del backend. Defínela en Coolify."
    )

# Límite de intentos fallidos por IP (en memoria, se reinicia con el servicio)
FAIL_LIMIT = 10        # fallos permitidos...
FAIL_WINDOW = 300      # ...dentro de esta ventana (segundos)
_MAX_TRACKED_IPS = 10000
_failures: dict[str, deque] = {}


def _client_ip(request: Request) -> str:
    """IP del cliente detrás del proxy (Coolify/Traefik).

    Se usa el ÚLTIMO valor de X-Forwarded-For: lo añade el proxy más cercano y
    el cliente no puede falsificarlo (el primero sí podría venir inventado).
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "desconocida"


def _recent_failures(ip: str, now: float) -> Optional[deque]:
    """Devuelve los fallos vigentes de la IP (descarta los vencidos)."""
    attempts = _failures.get(ip)
    if attempts is None:
        return None
    while attempts and now - attempts[0] > FAIL_WINDOW:
        attempts.popleft()
    if not attempts:
        del _failures[ip]
        return None
    return attempts


def _register_failure(ip: str, now: float) -> None:
    # Evita que el diccionario crezca sin límite
    if len(_failures) >= _MAX_TRACKED_IPS:
        for known_ip in list(_failures):
            _recent_failures(known_ip, now)
    _failures.setdefault(ip, deque()).append(now)


def _admin_user_from_bearer(authorization: Optional[str]) -> Optional[User]:
    """Devuelve el usuario admin del Bearer, o None si no es válido."""
    if not isinstance(authorization, str) or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("role") != "user":
        return None
    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        return None
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active or not user.is_admin:
            return None
        db.expunge(user)
        return user


def _valid_admin_bearer(authorization: Optional[str]) -> bool:
    """Acepta un JWT de usuario solo si pertenece a una cuenta admin activa."""
    return _admin_user_from_bearer(authorization) is not None


async def require_key(
    request: Request,
    x_igris_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """Dependencia: exige la clave X-Igris-Key o un JWT de usuario admin."""
    now = time.monotonic()
    ip = _client_ip(request)

    # 1) ¿IP bloqueada por demasiados fallos de acceso admin?
    attempts = _recent_failures(ip, now)
    if attempts is not None and len(attempts) >= FAIL_LIMIT:
        retry_after = max(1, int(FAIL_WINDOW - (now - attempts[0])) + 1)
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos fallidos. Espera unos minutos.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2) Clave histórica del panel. `not expected` => fail closed para la clave.
    expected = ACCESS_KEY.encode("utf-8")
    provided = (x_igris_key if isinstance(x_igris_key, str) else "").encode("utf-8")
    if expected and secrets.compare_digest(provided, expected):
        _failures.pop(ip, None)
        return

    # 3) Alternativa segura: usuario logueado y marcado como administrador.
    if _valid_admin_bearer(authorization):
        _failures.pop(ip, None)
        return

    _register_failure(ip, now)
    raise HTTPException(status_code=401, detail="Acceso de administrador inválido")


def _bind_admin_identity_from_bearer(session, authorization: Optional[str], text: Optional[str] = None) -> None:
    """Si el panel admin se abrió con usuario admin, ata la sesión a ese usuario.

    Mantiene la clave histórica sin usuario como antes, pero cuando existe un JWT
    admin válido permite que /api/chat y /api/voice-chat tengan memoria, notas y
    recordatorios del administrador autenticado.
    """
    user = _admin_user_from_bearer(authorization)
    if user is None:
        return

    session.user_id = user.id
    session.capabilities = admin_capabilities()
    session.addressing_instruction = user.addressing_instruction or ""
    with database.SessionLocal() as db:
        account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
        session.google_linked = account.email if account is not None else None
        link = db.query(TelegramLink).filter(TelegramLink.user_id == user.id).first()
        session.telegram_linked = bool(link and link.chat_id)
        if text:
            remember_from_text(db, user.id, text)
        session.personal_memory = load_memories(db, user.id, "personal")
        session.operational_memory = load_memories(db, user.id, "operational")

# Instancia global del cerebro y almacén de sesiones (historial por conversación)
brain = Brain()
sessions = SessionStore(brain)
NODE_TOKEN = os.environ.get("NODE_TOKEN", "")

def valid_node_token(token) -> bool:
    """Compara el NODE_TOKEN en tiempo constante."""
    if not token or not NODE_TOKEN:
        return False
    return secrets.compare_digest(token, NODE_TOKEN)

# ============= ÁREA DE USUARIOS (/u) =============
# Rutas de gestión de usuarios y del chat de usuarios. Comparten el mismo Brain
# y el mismo SessionStore que el panel, y el historial queda aislado por usuario
# con la clave "user:<id>:<conversación>" que construye user_routes.
import server.user_routes as user_routes
user_routes.bind_sessions(sessions)
app.include_router(user_routes.router)

# ------------------- CONFIGURACIÓN DE TELEGRAM -------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_TELEGRAM_IDS_STR = os.getenv("ALLOWED_TELEGRAM_IDS", "")
ALLOWED_TELEGRAM_IDS = {
    int(uid.strip()) for uid in ALLOWED_TELEGRAM_IDS_STR.split(",") if uid.strip().isdigit()
}
# Opcional: secret para validar que la petición realmente viene de Telegram (cuando usas webhook)
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")  # puede estar vacío
# Opcional: URL pública donde estará el webhook (para configurarlo automáticamente al iniciar)
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")      # ej: https://igris.zottagroup.com/telegram/webhook

# --- Telegram bot setup (no se inicia polling, solo se prepara para procesar updates) ---
if TELEGRAM_TOKEN:
    telegram_bot = Bot(token=TELEGRAM_TOKEN)
    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
else:
    telegram_bot = None
    telegram_app = None

# ============= HEALTH & STATUS (Sin autenticación) =============

@app.get("/health")
async def health():
    """Health check - disponible sin autenticación"""
    return {"status": "ok", "name": "igris"}


@app.get("/status")
async def status():
    """Status del sistema: proveedor activo, disponibles, etc."""
    return {
        "status": "ok",
        "name": "igris",
        "active_provider": config.get_active_provider(),
        "available_providers": config.get_available_providers(),
        "fallback_chain": config.get_fallback_chain(),
        "stt": {
            "provider": get_settings().get_stt_config().get("provider", "local"),
            "enabled": True,
        },
        "tts": {
            "provider": os.environ.get("IGRIS_TTS_PROVIDER", "local"),
            "enabled": True,  # Simplified
        },
    }


# ============= VALIDACIÓN DE LA CLAVE (pantalla de acceso) =============

@app.get("/api/auth/check", dependencies=[Depends(require_key)])
async def auth_check():
    """La pantalla de acceso usa este endpoint para validar la clave."""
    return {"ok": True}


# ============= CHAT VÍA HTTP (requiere clave) =============
from pydantic import BaseModel

class ChatRequest(BaseModel):
    text: str
    session_id: Optional[str] = None  # opcional: si el frontend no lo envía, se usa una sesión única

@app.post("/api/voice-profile", dependencies=[Depends(require_key)])
async def register_admin_voice(audio: UploadFile = File(...)):
    """Registra la voz del primer usuario administrador autorizado."""
    data = await audio.read()
    if len(data) < 10_000:
        raise HTTPException(status_code=422, detail="La muestra de voz es demasiado corta")
    try:
        vector = await asyncio.to_thread(voice.average_embedding, [data], ".webm")
        encoded = voice.serialize(vector)
        with database.SessionLocal() as db:
            user = db.query(User).filter(User.is_admin.is_(True)).order_by(User.id.asc()).first()
            if user is None:
                raise HTTPException(status_code=404, detail="No existe usuario administrador")
            profile = db.query(Profile).filter(
                Profile.user_id == user.id, Profile.name == "Voz principal"
            ).first()
            if profile is None:
                profile = Profile(user_id=user.id, name="Voz principal")
                db.add(profile)
            profile.voice_print = encoded
            profile.is_authorized = True
            db.commit()
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("No se pudo registrar la voz del administrador")
        raise HTTPException(status_code=500, detail=f"No se pudo registrar la voz: {exc}")


@app.post("/api/voice-chat", dependencies=[Depends(require_key)])
async def admin_voice_chat(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    authorization: Optional[str] = Header(default=None),
):
    """Transcribe y ejecuta; si hay perfil admin registrado, valida la voz primero."""
    data = await audio.read()
    if len(data) < 1_000:
        raise HTTPException(status_code=422, detail="El audio está vacío o es demasiado corto")
    score: float | None = None
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.is_admin.is_(True)).order_by(User.id.asc()).first()
        profile = db.query(Profile).filter(
            Profile.user_id == user.id if user else False,
            Profile.name == "Voz principal",
            Profile.is_authorized.is_(True),
        ).first() if user else None
        if profile is not None and profile.voice_print:
            try:
                verified, score = await asyncio.to_thread(voice.verify, data, profile.voice_print, ".webm")
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"No se pudo verificar la voz: {exc}")
            if not verified:
                raise HTTPException(status_code=403, detail="Voz no reconocida")
        else:
            logger.info("Orden por voz admin sin perfil registrado")
    text = (await asyncio.to_thread(stt.transcribe, data, ".webm")).strip()
    if not text:
        raise HTTPException(status_code=422, detail="No se entendió la orden")
    sid = "".join(c for c in (session_id or "") if c.isalnum() or c in "-_")[:64] or "default"
    session = sessions.get(f"web:{sid}")
    _bind_admin_identity_from_bearer(session, authorization, text)
    reply = await session.say(text)
    result = {"status": "ok", "text": text, "reply": reply}
    if score is not None:
        result["voice_score"] = round(score, 3)
    return result


@app.post("/api/chat", dependencies=[Depends(require_key)])
async def http_chat(req: ChatRequest, authorization: Optional[str] = Header(default=None)):
    """Endpoint de chat simple - requiere X-Igris-Key"""
    try:
        # Se limpia el id y se prefija "web:"; sin id se usa una sesión única
        # (uso personal con una sola clave de acceso).
        sid = "".join(c for c in (req.session_id or "") if c.isalnum() or c in "-_")[:64] or "default"
        session = sessions.get(f"web:{sid}")
        _bind_admin_identity_from_bearer(session, authorization, req.text)
        reply = await session.say(req.text)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============= CONFIGURACIÓN DE IA (requiere clave) =============
from pydantic import BaseModel
from typing import List, Optional

class AIConfigUpdate(BaseModel):
    primary_provider: Optional[str] = None
    fallback_chain: Optional[List[str]] = None

class AIConfigResponse(BaseModel):
    status: str
    primary_provider: str
    fallback_chain: List[str]
    message: Optional[str] = None


class STTConfigUpdate(BaseModel):
    provider: str
    cloud_model: Optional[str] = None
    local_engine: Optional[str] = None
    local_model: Optional[str] = None
    language: Optional[str] = None


class STTConfigResponse(BaseModel):
    status: str
    provider: str
    cloud_model: str
    local_engine: str
    local_model: str
    language: str
    cloud_ready: bool = False
    message: Optional[str] = None


@app.get("/api/stt-config", dependencies=[Depends(require_key)])
async def get_stt_config():
    settings = get_settings().get_stt_config()
    return STTConfigResponse(
        status="ok",
        provider=settings.get("provider", "local"),
        cloud_model=settings.get("cloud_model", "whisper-1"),
        local_engine=settings.get("local_engine", "whisper"),
        local_model=settings.get("local_model", "tiny"),
        language=settings.get("language", "es"),
        cloud_ready=bool(os.getenv("IGRIS_STT_API_KEY")),
    )


@app.put("/api/stt-config", dependencies=[Depends(require_key)])
async def update_stt_config(update: STTConfigUpdate):
    try:
        settings = get_settings()
        current = settings.get_stt_config()
        provider = update.provider.strip().lower()
        if provider not in {"local", "openai"}:
            raise ValueError("Proveedor STT no válido. Usa local u openai.")
        if provider == "openai" and not os.getenv("IGRIS_STT_API_KEY"):
            raise ValueError("Falta IGRIS_STT_API_KEY en el backend para activar Whisper OpenAI.")
        data = {
            "provider": provider,
            "cloud_model": update.cloud_model or current.get("cloud_model", "whisper-1"),
            "local_engine": update.local_engine or current.get("local_engine", "whisper"),
            "local_model": update.local_model or current.get("local_model", "tiny"),
            "language": update.language or current.get("language", "es"),
        }
        if not settings.set_stt_config(data):
            raise RuntimeError("No se pudo guardar la configuración STT")
        result = settings.get_stt_config()
        return STTConfigResponse(
            status="ok", provider=result["provider"], cloud_model=result.get("cloud_model", "whisper-1"),
            local_model=result.get("local_model", "tiny"), language=result.get("language", "es"),
            cloud_ready=bool(os.getenv("IGRIS_STT_API_KEY")),
            message="Configuración de transcripción guardada; aplica inmediatamente.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Error guardando configuración STT")
        raise HTTPException(status_code=500, detail="No se pudo guardar la configuración STT") from exc


@app.get("/api/ai-config", dependencies=[Depends(require_key)])
async def get_ai_config():
    """Obtener configuración actual de IA"""
    try:
        settings = get_settings()
        ai_config = settings.get_ai_config() or {}
        # Use config module to get defaults (from env or hardcoded defaults)
        from core import config
        defaults = config.get_active_provider_config()
        primary_provider = ai_config.get("primary_provider")
        fallback_chain = ai_config.get("fallback_chain")
        if primary_provider is None:
            primary_provider = defaults.get("active_provider")
        if fallback_chain is None:
            fallback_chain = defaults.get("fallback_chain", [])
        # Ensure fallback_chain is a list
        if not isinstance(fallback_chain, list):
            fallback_chain = []
        # Ensure primary provider is in fallback chain (fixes 'not in list' error)
        if primary_provider is not None and primary_provider not in fallback_chain:
            fallback_chain.insert(0, primary_provider)
        # If fallback_chain is empty, use default from config
        if not fallback_chain:
            fallback_chain = defaults.get("fallback_chain", [])
        return AIConfigResponse(
            status="ok",
            primary_provider=primary_provider,
            fallback_chain=fallback_chain,
            message="Configuración cargada correctamente"
        )
    except Exception as e:
        # Fallback to config defaults on error
        from core import config
        defaults = config.get_active_provider_config()
        return AIConfigResponse(
            status="error",
            primary_provider=defaults.get("active_provider", "nemotron"),
            fallback_chain=defaults.get("fallback_chain", []),
            message=f"Error al cargar configuración: {str(e)}"
        )


@app.put("/api/ai-config", dependencies=[Depends(require_key)])
async def update_ai_config(config_update: AIConfigUpdate):
    """Actualizar configuración de IA"""
    try:
        settings = get_settings()
        current_ai_config = settings.get_ai_config()
        from core import config
        defaults = config.get_active_provider_config()

        # Rechaza proveedores que no existen (ej. groq)
        valid = config.get_available_providers()
        requested = ([config_update.primary_provider] if config_update.primary_provider else []) \
            + (config_update.fallback_chain or [])
        invalid = [p for p in requested if p.strip() and p.strip() not in valid]
        if invalid:
            return AIConfigResponse(
                status="error",
                primary_provider=current_ai_config.get("primary_provider") or defaults.get("active_provider", "nemotron"),
                fallback_chain=current_ai_config.get("fallback_chain") or defaults.get("fallback_chain", []),
                message=f"Proveedor no válido: {', '.join(invalid)}. Disponibles: {', '.join(valid)}",
            )

        # Update only the fields that were provided
        if config_update.primary_provider is not None:
            current_ai_config["primary_provider"] = config_update.primary_provider
        if config_update.fallback_chain is not None:
            # Ensure it's a list and filter out empty strings
            fallback_list = [p.strip() for p in config_update.fallback_chain if p.strip()]
            if fallback_list:
                current_ai_config["fallback_chain"] = fallback_list

        # Ensure primary provider is in fallback chain (fixes 'not in list' error)
        primary = current_ai_config.get("primary_provider")
        if primary is not None:
            fallback_chain = current_ai_config.get("fallback_chain", [])
            if not isinstance(fallback_chain, list):
                fallback_chain = []
            if primary not in fallback_chain:
                fallback_chain.insert(0, primary)
            current_ai_config["fallback_chain"] = fallback_chain
        # Save the updated configuration
        if settings.set_ai_config(current_ai_config):
            # Reload brain configuration to take effect immediately
            brain.reload_settings()
            return AIConfigResponse(
                status="ok",
                primary_provider=current_ai_config.get("primary_provider", defaults.get("active_provider")),
                fallback_chain=current_ai_config.get("fallback_chain", defaults.get("fallback_chain", [])),
                message="Configuración actualizada correctamente. Los cambios toman efecto inmediatamente para nuevos chats."
            )
        else:
            return AIConfigResponse(
                status="error",
                primary_provider=current_ai_config.get("primary_provider", defaults.get("active_provider")),
                fallback_chain=current_ai_config.get("fallback_chain", defaults.get("fallback_chain", [])),
                message="Error al guardar la configuración"
            )
    except Exception as e:
        # Fallback to config defaults on error
        from core import config
        defaults = config.get_active_provider_config()
        return AIConfigResponse(
            status="error",
            primary_provider=defaults.get("active_provider", "nemotron"),
            fallback_chain=defaults.get("fallback_chain", []),
            message=f"Error al actualizar configuración: {str(e)}"
        )

# ============= TTS ENDPOINT (requiere clave) =============
from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts", dependencies=[Depends(require_key)])
async def tts_endpoint(req: TTSRequest):
    """Convertir texto a voz usando la configuración de TTS"""
    try:
        # Usar la función existente de core/tts.py
        audio_bytes = await tts.synthesize(req.text)

        # Devolver como respuesta binaria con tipo de contenido correcto
        from fastapi.responses import Response
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",  # Asumimos MP3 (funciona para Piper, edge-tts, OpenAI)
            headers={
                "Content-Disposition": "inline; filename=iris_response.mp3"
            }
        )
    except Exception as e:
        print(f"Error en TTS endpoint: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Error generating speech: {str(e)}")

# ----------------------------------------------------------------------
# Transcripción de audio de Telegram
# ----------------------------------------------------------------------
async def _transcribe_telegram_file(file_id: str, user: User | None) -> str:
    """Verifica al hablante y después transcribe el audio de Telegram."""
    tg_file = await telegram_bot.get_file(file_id)
    audio_bytes = bytes(await tg_file.download_as_bytearray())
    if user is None:
        raise PermissionError("No hay un usuario asociado a esta voz")
    with database.SessionLocal() as db:
        profile = db.query(Profile).filter(
            Profile.user_id == user.id,
            Profile.name == "Voz principal",
            Profile.is_authorized.is_(True),
        ).first()
        if profile is None or not profile.voice_print:
            raise PermissionError("Registra tu voz antes de usar órdenes por voz")
        verified, _ = await asyncio.to_thread(voice.verify, audio_bytes, profile.voice_print, ".ogg")
    if not verified:
        raise PermissionError("Voz no reconocida")
    return await asyncio.to_thread(stt.transcribe, audio_bytes, ".ogg")


# ----------------------------------------------------------------------
# Procesamiento de actualizaciones entrantes de Telegram
# ----------------------------------------------------------------------
async def process_telegram_update(update_dict: dict):
    """
    Recibe el dict que Telegram envía en el webhook, lo valida,
    verifica la autorización y responde según corresponda.
    Ahora también maneja notas de voz y archivos de audio.
    """
    if not telegram_bot or not telegram_app:
        # Si no se configuró el token, simplemente salimos (no debería pasar en prod)
        return

    try:
        update = Update.de_json(update_dict, telegram_bot)
    except Exception as e:
        # No podemos parsear el update
        print(f"[Telegram] Error al parsear update: {e}")
        return

    user = update.effective_user
    if user is None:
        # Updates como canal_posts, chat_member, etc. no tienen usuario → los ignoramos.
        return

    # ------------------- Autorización -------------------
    # Dos formas de estar autorizado:
    #   a) El chat está VINCULADO a una cuenta de Igris (/start <código> desde /u).
    #      Entonces se atiende como ESE usuario, con sus permisos y sus datos.
    #   b) El id está en ALLOWED_TELEGRAM_IDS: la lista de siempre, del dueño de la
    #      instalación. Se mantiene para no romper el uso personal, y esas sesiones
    #      conservan todos los permisos.
    linked_user = await asyncio.to_thread(telegram_links.resolve_user, user.id)
    is_env_allowed = user.id in ALLOWED_TELEGRAM_IDS

    if linked_user is None and not is_env_allowed:
        # Antes de rechazar, puede ser alguien intentando vincularse: se mira si
        # mandó /start con un código válido.
        message = update.effective_message
        text = (message.text or "").strip() if message and message.text else ""
        parts = text.split()
        if len(parts) >= 2 and parts[0].lower().startswith("/start"):
            linked_id, respuesta = await asyncio.to_thread(
                telegram_links.link_chat, parts[1], user.id, user.username
            )
            if linked_id is not None:
                await message.reply_text(
                    "¡Listo! Tu Telegram quedó vinculado a tu cuenta de Igris. "
                    "Ya puedes escribirme por aquí y tus recordatorios te llegarán a este chat."
                )
                return
            await message.reply_text(respuesta)
            return

        try:
            await telegram_bot.send_message(
                chat_id=user.id,
                text=(
                    "🚫 No reconozco este chat. Si tienes cuenta en Igris, entra en tu "
                    "página, abre «Conexiones», pide un código y envíamelo así: "
                    "/start <código>"
                ),
            )
        except Exception:
            pass  # No podemos hacer mucho si falla el envío
        return

    # ------------------- Mensaje de texto o voz -------------------
    if linked_user is None and is_env_allowed:
        with database.SessionLocal() as db:
            linked_user = db.query(User).filter(User.is_admin.is_(True)).order_by(User.id.asc()).first()
    message = update.effective_message
    if not message:
        # No hay mensaje (puede ser un update de otro tipo)
        return

    # Determinar si es texto o voz/audio
    user_text = None

    if message.text:
        user_text = message.text.strip()
    elif message.voice or message.audio:
        # ----- Nota de voz o archivo de audio -----
        media = message.voice or message.audio
        try:
            await message.chat.send_action(action="typing")
            user_text = (await _transcribe_telegram_file(media.file_id, linked_user)).strip()
        except PermissionError as e:
            await message.reply_text(f"🚫 {e}")
            return
        except Exception as e:
            logger.exception("Fallo al transcribir audio de Telegram")
            await message.reply_text(
                "Lo siento, mi señor, no pude transcribir el audio. "
                f"Detalle técnico: {e}"
            )
            return

        if not user_text:
            await message.reply_text(
                "Lo siento, mi señor, no logré entender el audio. ¿Puede repetirlo?"
            )
            return
    else:
        # Otros tipos de mensaje (sticker, foto, video, etc.) los ignoramos por ahora.
        return

    # ----- Comandos -----
    if user_text.startswith("/"):
        parts = user_text.split()
        cmd = parts[0].lower()

        if cmd in ("/start", "/help"):
            if len(parts) >= 2 and cmd == "/start":
                # Un chat YA autorizado que manda un código nuevo quiere vincularse a
                # OTRA cuenta (por ejemplo, el dueño prestó el teléfono). Un chat de
                # ALLOWED_TELEGRAM_IDS no está vinculado a ninguna cuenta, así que
                # puede vincularse sin más.
                if linked_user is not None:
                    nuevo_id, respuesta = await asyncio.to_thread(
                        telegram_links.link_chat, parts[1], user.id, user.username
                    )
                    if nuevo_id is not None:
                        await message.reply_text(
                            "Listo: este chat quedó vinculado a la nueva cuenta de Igris."
                        )
                    else:
                        await message.reply_text(respuesta)
                    return
                await message.reply_text(
                    "Este chat ya está autorizado. Envíeme su orden."
                )
                return
            await message.reply_text(
                "¡Saludos, mi señor! Soy Igris. Envíeme su orden."
            )
            return

        # Los comandos de configuración cambian los ajustes de TODA la instalación
        # (qué proveedor de IA se usa). Solo el dueño —los chats de
        # ALLOWED_TELEGRAM_IDS— puede tocarlos: un usuario vinculado tiene su propio
        # chat, pero no es el administrador de Igris.
        if cmd in ("/config", "/setprovider", "/setfallback") and not is_env_allowed:
            await message.reply_text(
                "Eso cambia la configuración de Igris para todos, y solo puede hacerlo "
                "el administrador."
            )
            return

        if cmd == "/config":
            cfg = await _get_igris_ai_config()
            txt = (
                f"Configuración actual de Igris:\n"
                f"• Proveedor activo: {cfg['primary_provider']}\n"
                f"• Cadena de fallback: {', '.join(cfg['fallback_chain'])}"
            )
            await message.reply_text(txt)
            return

        if cmd == "/setprovider":
            if len(parts) < 2:
                await message.reply_text("Uso: /setprovider <nombre>")
                return
            provider = parts[1]
            result = await _set_igris_ai_config(primary=provider)
            await message.reply_text(
                f"Proveedor activo cambiado a **{provider}**."
                if result.get("status") == "ok"
                else f"Error: {result.get('message')}"
            )
            return

        if cmd == "/setfallback":
            if len(parts) < 2:
                await message.reply_text("Uso: /setfallback <proveedor1,proveedor2,...>")
                return
            fallback_list = [p.strip() for p in " ".join(parts[1:]).split(",") if p.strip()]
            result = await _set_igris_ai_config(fallback=fallback_list)
            await message.reply_text(
                f"Cadena de fallback actualizada a: {', '.join(fallback_list)}"
                if result.get("status") == "ok"
                else f"Error: {result.get('message')}"
            )
            return

        # Comando desconocido
        await message.reply_text("Comando no reconocido. Use /help para ver las opciones disponibles.")
        return

    # ----- Mensaje libre (se envía a Igris) -----
    await message.chat.send_action(action="typing")  # opcional: muestra "escribiendo..."
    reply = await _get_igris_reply(user_text, f"tg:{user.id}")
    await message.reply_text(reply)


# ----------------------------------------------------------------------
# Funciones reutilizables de Igris (evitan hacer llamadas HTTP a sí mismas)
# ----------------------------------------------------------------------
async def _get_igris_reply(text: str, session_key: Optional[str] = None) -> str:
    """Envía el texto al cerebro de Igris y devuelve la respuesta de Igris."""
    try:
        session = sessions.get(session_key)
        if session_key and session_key.startswith("tg:"):
            chat_id = int(session_key[3:])  # los recordatorios avisarán a este chat
            session.telegram_id = chat_id
            # Identidad y permisos del chat vinculado. Se resuelven en cada mensaje:
            # si el usuario se desvincula o el admin le cambia los permisos, el
            # siguiente mensaje ya lo refleja.
            linked_user = await asyncio.to_thread(telegram_links.resolve_user, chat_id)
            if linked_user is not None:
                session.user_id = linked_user.id
                session.capabilities = (
                    admin_capabilities()
                    if linked_user.is_admin
                    else capabilities_from_user(linked_user)
                )
                session.addressing_instruction = linked_user.addressing_instruction or ""
                session.telegram_linked = True
                with database.SessionLocal() as db:
                    account = db.query(GoogleAccount).filter(
                        GoogleAccount.user_id == linked_user.id
                    ).first()
                    session.google_linked = account.email if account is not None else None
                    remember_from_text(db, linked_user.id, text)
                    session.personal_memory = load_memories(db, linked_user.id, "personal")
                    session.operational_memory = load_memories(db, linked_user.id, "operational")
            else:
                # Chat autorizado por la lista del entorno (uso personal del dueño):
                # sin límites, como antes.
                session.user_id = None
                session.capabilities = admin_capabilities()
                session.addressing_instruction = ""
                session.telegram_linked = True
                session.google_linked = None
        reply = await session.say(text)
        return reply
    except Exception as e:
        return f"Lo siento, mi señor, ocurrió un error al consultar a Igris: {e}"


async def _get_igris_ai_config() -> dict:
    """Devuelve la configuración actual de IA (igual que el endpoint /api/ai-config)."""
    from core import config
    try:
        settings = get_settings()
        ai_config = settings.get_ai_config() or {}
        defaults = config.get_active_provider_config()
        primary = ai_config.get("primary_provider") or defaults.get("active_provider")
        fallback = ai_config.get("fallback_chain")
        if fallback is None:
            fallback = defaults.get("fallback_chain", [])
        if not isinstance(fallback, list):
            fallback = []
        # Garantizar que el primary esté en la fallback chain
        if primary and primary not in fallback:
            fallback.insert(0, primary)
        if not fallback:
            fallback = defaults.get("fallback_chain", [])
        return {
            "primary_provider": primary,
            "fallback_chain": fallback,
        }
    except Exception:
        # En caso de error, devolvemos los valores por defecto
        defaults = config.get_active_provider_config()
        return {
            "primary_provider": defaults.get("active_provider", "nemotron"),
            "fallback_chain": defaults.get("fallback_chain", []),
        }


async def _set_igris_ai_config(primary: Optional[str] = None,
                                fallback: Optional[list[str]] = None) -> dict:
    """Actualiza la configuración de IA (igual que el endpoint PUT /api/ai-config)."""
    from core import config
    try:
        settings = get_settings()
        current = settings.get_ai_config() or {}
        defaults = config.get_active_provider_config()

        # Rechaza proveedores que no existen (ej. groq)
        valid = config.get_available_providers()
        bad = [p for p in ([primary] if primary else []) + (fallback or []) if p.strip() and p.strip() not in valid]
        if bad:
            return {"status": "error",
                    "message": f"Proveedor no válido: {', '.join(bad)}. Disponibles: {', '.join(valid)}"}

        if primary is not None:
            current["primary_provider"] = primary
        if fallback is not None:
            # limpiar posibles cadenas vacías
            current["fallback_chain"] = [p.strip() for p in fallback if p.strip()]

        # Asegurar que el primary esté en la fallback chain
        prim = current.get("primary_provider") or defaults.get("active_provider")
        if prim is not None:
            fb = current.get("fallback_chain", [])
            if not isinstance(fb, list):
                fb = []
            if prim not in fb:
                fb.insert(0, prim)
            current["fallback_chain"] = fb

        if not settings.set_ai_config(current):
            return {"status": "error", "message": "No se pudo guardar la configuración"}

        # Hacer que los cambios tengan efecto inmediato
        brain.reload_settings()
        return {
            "status": "ok",
            "primary_provider": prim,
            "fallback_chain": current.get("fallback_chain", []),
            "message": "Configuración actualizada correctamente."
        }
    except Exception as e:
        return {"status": "error", "message": f"Error al actualizar configuración: {e}"}


# ============= WEBHOOK DE TELEGRAM =============
@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    """
    Webhook de Telegram. Valida el token secreto (si se configuró) y procesa el update.
    """
    # 1️⃣ Validar el secret (si se definió TELEGRAM_WEBHOOK_SECRET)
    if TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret token")

    # 2️⃣ Obtener el JSON que Telegram envió
    try:
        update_dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 3️⃣ Procesar el update en segundo plano: así respondemos 200 a Telegram de
    # inmediato y evitamos que reintente el envío si la transcripción o la IA
    # tardan (lo que duplicaría las respuestas).
    background_tasks.add_task(process_telegram_update, update_dict)

    # Telegram espera una respuesta 200 OK para considerar que el update fue procesado.
    return {"status": "ok"}


# ============= RECORDATORIOS: ENVÍO Y ARRANQUE =============
async def _send_telegram(chat_id: int, text: str) -> None:
    """Función de envío que usa el planificador de recordatorios."""
    if telegram_bot is None:
        raise RuntimeError("Telegram no configurado")
    await telegram_bot.send_message(chat_id=chat_id, text=text)


@app.on_event("startup")
async def on_startup():
    """Inicia el planificador de recordatorios y configura el webhook de Telegram."""
    # El planificador arranca siempre, aunque no haya webhook configurado
    if telegram_bot is not None:
        app.state.reminder_task = asyncio.create_task(
            run_reminder_loop(_send_telegram, ALLOWED_TELEGRAM_IDS)
        )
    else:
        logger.warning("TELEGRAM_TOKEN no definido: los recordatorios NO se enviarán")

    if not TELEGRAM_TOKEN or not TELEGRAM_WEBHOOK_URL:
        # No hacemos nada más si faltan datos; el usuario puede configurar el webhook manualmente.
        return

    try:
        await telegram_bot.set_webhook(
            url=TELEGRAM_WEBHOOK_URL,
            secret_token=TELEGRAM_WEBHOOK_SECRET or None,
            drop_pending_updates=True,  # limpiar updates antiguos
        )
        print(f"[Telegram] Webhook establecido en {TELEGRAM_WEBHOOK_URL}")
    except Exception as e:
        print(f"[Telegram] Error al establecer webhook: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    task = getattr(app.state, "reminder_task", None)
    if task:
        task.cancel()


# ============= ROOT =============
@app.get("/")
async def root():
    """API root"""
    return {
        "name": "IGRIS Chat",
        "version": "1.0.0",
        "status": "operational",
        "debug": "test2",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "auth-check": "/api/auth/check (GET, requiere X-Igris-Key)",
            "chat": "/api/chat (POST, requiere X-Igris-Key)",
            "ai-config": "/api/ai-config (GET/PUT, requiere X-Igris-Key)",
            "tts": "/api/tts (POST, requiere X-Igris-Key)",
            "admin-users": "/api/admin/users (GET/POST/PUT/DELETE, requiere X-Igris-Key)",
            "user-login": "/api/user/login (POST)",
            "user-chat": "/api/user/chat (POST, requiere Bearer token)",
            "telegram-webhook": "/telegram/webhook (POST)"
        }
    }


# Ejecutar con: uvicorn server.main:app --host 0.0.0.0 --port 8000
# Trivial update to force new commit for deployment - 1791253999

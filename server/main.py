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

from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from core import Brain, config, stt          # ← añadido stt
from core.settings_manager import get_settings
from core import tts
from core.database import init_db

# Telegram imports
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes

logger = logging.getLogger(__name__)

# Inicializar BD
init_db()

app = FastAPI(
    title="IGRIS Chat",
    description="Servidor de chat simple con Igris",
    version="1.0.0"
)

# CORS - solo el frontend (y el servidor de desarrollo local).
# Sin allow_credentials: la clave viaja en el header X-Igris-Key, no en cookies.
# El preflight (OPTIONS) lo responde este middleware antes de llegar a las rutas,
# así que nunca pasa por require_key.
origins = [
    "https://webigris.zottagroup.com",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-Igris-Key"],
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


async def require_key(request: Request, x_igris_key: Optional[str] = Header(default=None)):
    """Dependencia: exige el header X-Igris-Key válido.

    Es async a propósito: así corre en el event loop (un solo hilo) y el
    diccionario de intentos no necesita locks.
    """
    now = time.monotonic()
    ip = _client_ip(request)

    # 1) ¿IP bloqueada por demasiados fallos?
    attempts = _recent_failures(ip, now)
    if attempts is not None and len(attempts) >= FAIL_LIMIT:
        retry_after = max(1, int(FAIL_WINDOW - (now - attempts[0])) + 1)
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos fallidos. Espera unos minutos.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2) Comparación en tiempo constante y en bytes.
    #    `not expected` => fail closed (sin clave configurada nunca se entra).
    expected = ACCESS_KEY.encode("utf-8")
    provided = (x_igris_key or "").encode("utf-8")
    if not expected or not secrets.compare_digest(provided, expected):
        _register_failure(ip, now)
        raise HTTPException(status_code=401, detail="Clave de acceso inválida")

    # 3) Clave correcta: se limpian los fallos de esa IP
    _failures.pop(ip, None)

# Instancia global del cerebro
brain = Brain()
NODE_TOKEN = os.environ.get("NODE_TOKEN", "")

def valid_node_token(token) -> bool:
    """Compara el NODE_TOKEN en tiempo constante."""
    if not token or not NODE_TOKEN:
        return False
    return secrets.compare_digest(token, NODE_TOKEN)

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
            "provider": os.environ.get("IGRIS_STT_PROVIDER", "local"),
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

@app.post("/api/chat", dependencies=[Depends(require_key)])
async def http_chat(req: ChatRequest):
    """Endpoint de chat simple - requiere X-Igris-Key"""
    try:
        session = brain.new_session()
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
async def _transcribe_telegram_file(file_id: str) -> str:
    """Descarga un audio/nota de voz de Telegram y lo transcribe a texto."""
    tg_file = await telegram_bot.get_file(file_id)
    audio_bytes = await tg_file.download_as_bytearray()
    # stt.transcribe() es una función síncrona y pesada (Whisper): no se usa
    # `await` directamente; se ejecuta en un hilo para no congelar el servidor.
    return await asyncio.to_thread(stt.transcribe, audio_bytes)


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
    if user.id not in ALLOWED_TELEGRAM_IDS:
        # Usuario no autorizado: respondemos solo para no dejar colgado al remitente.
        try:
            await telegram_bot.send_message(
                chat_id=user.id,
                text="🚫 Lo siento, mi señor, pero no estás autorizado para usar este bot."
            )
        except Exception:
            pass  # No podemos hacer mucho si falla el envío
        return

    # ------------------- Mensaje de texto o voz -------------------
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
            user_text = (await _transcribe_telegram_file(media.file_id)).strip()
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
            await message.reply_text(
                "¡Saludos, mi señor! Soy Igris. Envíeme su orden."
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
    reply = await _get_igris_reply(user_text)
    await message.reply_text(reply)


# ----------------------------------------------------------------------
# Funciones reutilizables de Igris (evitan hacer llamadas HTTP a sí mismas)
# ----------------------------------------------------------------------
async def _get_igris_reply(text: str) -> str:
    """Envía el texto al cerebro de Igris y devuelve la respuesta de Igris."""
    try:
        session = brain.new_session()
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


# ============= CONFIGURAR WEBHOOK AUTOMÁTICAMENTE AL INICIAR (OPCIONAL) =============
@app.on_event("startup")
async def on_startup():
    """Configura el webhook de Telegram si se providieron las variables necesarias."""
    if not TELEGRAM_TOKEN or not TELEGRAM_WEBHOOK_URL:
        # No hacemos nada si faltan datos; el usuario puede configurar el webhook manualmente.
        return

    if telegram_bot is None:
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
            "telegram-webhook": "/telegram/webhook (POST)"
        }
    }


# Ejecutar con: uvicorn server.main:app --host 0.0.0.0 --port 8000
# Trivial update to force new commit for deployment - 1791253999

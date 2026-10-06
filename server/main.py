"""
IGRIS - Servidor FastAPI simplificado para solo chat con Igris
"""
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from core import Brain, config
from core.settings_manager import get_settings
from core import tts
from core.database import init_db

# Telegram imports
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes

# Inicializar BD
init_db()

app = FastAPI(
    title="IGRIS Chat",
    description="Servidor de chat simple con Igris",
    version="1.0.0"
)

# CORS - permitir frontend
origins = [
    "https://webigris.zottagroup.com",
    "https://igris.zottagroup.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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


# ============= CHAT VÍA HTTP (Sin autenticación) =============
from pydantic import BaseModel

class ChatRequest(BaseModel):
    text: str

@app.post("/api/chat")
async def http_chat(req: ChatRequest):
    """Endpoint de chat simple - sin autenticación requerido"""
    try:
        session = brain.new_session()
        reply = await session.say(req.text)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ----------------------------------------------------------------------
# Funciones reutilizables de Igris (evitan hacer llamadas HTTP a sí mismas)
# ----------------------------------------------------------------------
async def _get_igris_reply(text: str) -> str:
    """Envía el texto al cerebro de Igris y devuelve la respuesta de Iris."""
    try:
        session = brain.new_session()
        reply = await session.say(text)
        return reply
    except Exception as e:
        return f"Lo siento, mi señor, ocurrió un error al consultar a Iris: {e}"


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

# ============= CONFIGURACIÓN DE IA (Sin autenticación) =============
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


@app.get("/api/ai-config")
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


@app.put("/api/ai-config")
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

# ============= TTS ENDPOINT =============
from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    """Convertir texto a voz usando la configuración de TTS"""
    try:
        # Usar la función existente de core/tts.py
        audio_bytes = await tts.synthesize(req.text)
         
        # Devolver como respuesta binaria con tipo de contenido correcto
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
# Procesamiento de actualizaciones entrantes de Telegram
# ----------------------------------------------------------------------
async def process_telegram_update(update_dict: dict):
    """
    Recibe el dict que Telegram envía en el webhook, lo valida,
    verifica la autorización y responde según corresponda.
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

    # ------------------- Mensaje de texto -------------------
    message = update.effective_message
    if not message or not message.text:
        # Ignoramos otros tipos de updates (stickers, fotos, etc.) por ahora.
        return

    text = message.text.strip()

    # ----- Comandos -----
    if text.startswith("/"):
        parts = text.split()
        cmd = parts[0].lower()

        if cmd in ("/start", "/help"):
            welcome = (
                "¡Saludos, mi señor! Soy el relay de Iris. Envíeme cualquier orden y la transmitiré a Iris.\n"
                "Comandos disponibles:\n"
                "/config – muestra la configuración actual de IA\n"
                "/setprovider <nombre> – cambia el proveedor activo\n"
                "/setfallback <lista> – establece la cadena de fallback (ej: nemotron,openai,local)"
            )
            await message.reply_text(welcome)
            return

        if cmd == "/config":
            cfg = await _get_igris_ai_config()
            txt = (
                f"Configuración actual de Iris:\n"
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
    reply = await _get_igris_reply(text)
    await message.reply_text(reply)

# ============= WEBHOOK DE TELEGRAM =============
@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
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

    # 3️⃣ Procesar el update
    await process_telegram_update(update_dict)

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
            "chat": "/api/chat (POST)",
            "ai-config": "/api/ai-config (GET/PUT)",
            "tts": "/api/tts (POST)",
            "telegram-webhook": "/telegram/webhook (POST)"
        }
    }


# Ejecutar con: uvicorn server.main:app --host 0.0.0.0 --port 8000
# Trivial update to force new commit for deployment - 1791253999

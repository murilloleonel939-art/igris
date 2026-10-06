#!/usr/bin/env python3
import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import httpx

load_dotenv()  # carga variables desde .env

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
IGRIS_BACKEND = os.getenv("IGRIS_BACKEND_URL").rstrip("/")
if not TELEGRAM_TOKEN or not IGRIS_BACKEND:
    raise RuntimeError("Define TELEGRAM_TOKEN y IGRIS_BACKEND_URL en el entorno o .env")

# ----------  LISTA DE IDs AUTORIZADOS  ----------
_allowed_ids_raw = os.getenv("ALLOWED_TELEGRAM_IDS", "")
ALLOWED_IDS = {
    int(uid.strip())
    for uid in _allowed_ids_raw.split(",")
    if uid.strip().isdigit()
}
if not ALLOWED_IDS:
    raise RuntimeError(
        "Debes definir al menos un ID autorizado en la variable ALLOWED_TELEGRAM_IDS"
    )
logging.info(f"IDs de Telegram autorizados: {ALLOWED_IDS}")

# ----------  LOGGING ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------  FILTRO PERSONALIZADO ----------
async def authorized_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Devuelve True si el usuario está en ALLOWED_IDS.
    Si no lo está, opcionalmente responde con un mensaje de error y retorna False.
    """
    user = update.effective_user
    if user is None:
        # Updates como canal_posts, chat_member, etc. no tienen usuario → los ignoramos.
        return False

    if user.id in ALLOWED_IDS:
        return True

    # Usuario no autorizado: informamos (opcional) y bloqueamos el update.
    logger.warning(
        f"Intento de acceso no autorizado – user_id={user.id}, username={user.username}"
    )
    # Solo enviamos una respuesta si el update proviene de un mensaje (para no spamear en otros tipos).
    if update.effective_message:
        await update.effective_message.reply_text(
            "🚫 Lo siento, mi señor, pero no estás autorizado para usar este bot."
        )
    return False


# ----------  WRAPPER QUE APLICA EL FILTRO A CUALQUIER HANDLER ----------
def authorized_handler(func):
    """
    Decorador que convierte un handler normal en uno que primero verifica la autorización.
    Se puede usar tanto con CommandHandler como MessageHandler.
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await authorized_only(update, context):
            return  # detener la propagación
        return await func(update, context)
    return wrapper


# ----------  FUNCIONES AUXILIARES (llamadas a Igris) ----------
async def call_igris_chat(text: str) -> str:
    """
    Envía el texto al endpoint /api/chat de Igris y devuelve la respuesta de Iris.
    """
    url = f"{IGRIS_BACKEND}/api/chat"
    payload = {"message": text}   # según el README, el endpoint espera JSON con clave "message"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Asumimos que el backend devuelve {"response": "texto de Iris"} o similar.
            # Ajusta la clave según la respuesta real del endpoint.
            return data.get("response", str(data))
        except Exception as e:
            logger.error(f"Error al llamar a Igris: {e}")
            return f"Lo siento, mi señor, ocurrió un error al consultar a Iris: {e}"

async def get_igris_ai_config() -> dict:
    """Obtiene la configuración actual de IA (proveedor activo y fallback)."""
    url = f"{IGRIS_BACKEND}/api/ai-config"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

async def set_igris_ai_config(provider: str, fallback: list[str]) -> bool:
    """Actualiza la configuración de IA en Igris."""
    url = f"{IGRIS_BACKEND}/api/ai-config"
    payload = {"provider": provider, "fallback_chain": fallback}
    async with httpx.AsyncClient() as client:
        resp = await client.put(url, json=payload)
        return resp.status_code == 200


# ----------  HANDLERS (ahora envueltos con el decorador) ----------
@authorized_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Saludos, mi señor! Soy el relay de Iris. Envíeme cualquier orden y la transmitiré a Iris.\n"
        "Comandos disponibles:\n"
        "/config – muestra la configuración actual de IA\n"
        "/setprovider <nombre> – cambia el proveedor activo\n"
        "/setfallback <lista> – establece la cadena de fallback (ej: nemotron,openai,local)"
    )

@authorized_handler
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

@authorized_handler
async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cfg = await get_igris_ai_config()
        txt = (
            f"Configuración actual de Iris:\n"
            f"• Proveedor activo: {cfg.get('provider')}\n"
            f"• Cadena de fallback: {', '.join(cfg.get('fallback_chain', []))}"
        )
        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"No pude obtener la configuración: {e}")

@authorized_handler
async def setprovider_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /setprovider <nombre>")
        return
    provider = context.args[0]
    # Obtener cadena actual para no destruirla
    try:
        cfg = await get_igris_ai_config()
        fallback = cfg.get("fallback_chain", [])
        ok = await set_igris_ai_config(provider, fallback)
        if ok:
            await update.message.reply_text(f"Proveedor activo cambiado a **{provider}**.")
        else:
            await update.message.reply_text("No se pudo actualizar la configuración.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

@authorized_handler
async def setfallback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /setfallback <proveedor1,proveedor2,...>"
        )
        return
    fallback_str = " ".join(context.args)
    fallback = [p.strip() for p in fallback_str.split(",") if p.strip()]
    try:
        cfg = await get_igris_ai_config()
        provider = cfg.get("provider", "nemotron")
        ok = await set_igris_ai_config(provider, fallback)
        if ok:
            await update.message.reply_text(
                f"Cadena de fallback actualizada a: {', '.join(fallback)}"
            )
        else:
            await update.message.reply_text("No se pudo actualizar la configuración.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

@authorized_handler
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para cualquier mensaje de texto (no comandos)."""
    user_text = update.message.text
    if not user_text:
        return
    await update.message.chat.send_action(action="typing")  # opcional: muestra "escribiendo..."
    iris_reply = await call_igris_chat(user_text)
    await update.message.reply_text(iris_reply)


# ----------  MAIN ----------
def main():
    USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Registramos los handlers (ya envueltos con @authorized_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("config", config_cmd))
    application.add_handler(CommandHandler("setprovider", setprovider_cmd))
    application.add_handler(CommandHandler("setfallback", setfallback_cmd))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message)
    )

    if USE_WEBHOOK:
        # Necesitas un dominio público con HTTPS, por ejemplo mediante ngrok o tu propio servidor.
        PORT = int(os.getenv("PORT", 8443))
        URL = os.getenv("WEBHOOK_URL")  # debe ser algo como https://mi-dominio.com/telegram
        if not URL:
            raise RuntimeError("Define WEBHOOK_URL cuando USE_WEBHOOK=true")
        logger.info(f"Iniciando webhook en {URL}:{PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,  # camino secreto recomendado
            webhook_url=f"{URL}/{TELEGRAM_TOKEN}",
        )
    else:
        logger.info("Iniciando en modo polling (ideal para pruebas locales).")
        application.run_polling()


if __name__ == "__main__":
    main()

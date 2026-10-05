"""
IGRIS - Servidor FastAPI con Autenticación, 2FA, y Panel de Control
"""
import os
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from core import Brain, config
from core import stt, tts
from core.settings_manager import get_settings
from core.database import init_db
from server.auth_routes import router as auth_router
from server.profile_routes import router as profile_router

# Inicializar BD
init_db()

app = FastAPI(
    title="IGRIS API",
    description="Plataforma de control IA con autenticación y 2FA",
    version="2.0.0"
)

# CORS - Permitir frontend desde webigris.zottagroup.com
# (sin "*": no es compatible con allow_credentials=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://webigris.zottagroup.com",
        "https://igris.zottagroup.com",
        "wss://igris.zottagroup.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)

# IMPORTANTE: los routers YA traen su prefijo (/auth y /api) definido en
# auth_routes.py y profile_routes.py con APIRouter(prefix=...).
# Por eso aquí NO se vuelve a poner prefix, o se duplicaría (/auth/auth/...).
app.include_router(auth_router)
app.include_router(profile_router)

# Instancia global del cerebro
brain = Brain()
NODE_TOKEN = os.environ.get("NODE_TOKEN", "")


def valid_node_token(token) -> bool:
    """Compara el NODE_TOKEN en tiempo constante."""
    if not token or not NODE_TOKEN:
        return False
    return secrets.compare_digest(token, NODE_TOKEN)


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
            "enabled": tts.TTS_ENABLED,
        },
    }


# ============= CONFIGURACIÓN LEGACY (Compatibilidad con NODE_TOKEN) =============

@app.post("/set-provider/{provider_name}")
async def set_provider(
    provider_name: str,
    x_node_token: str = Header(None)
):
    """Cambiar proveedor AI (requiere NODE_TOKEN)"""

    if not valid_node_token(x_node_token):
        return {"status": "error", "message": "Token no válido"}

    if config.set_active_provider(provider_name):
        return {
            "status": "ok",
            "active_provider": config.get_active_provider(),
            "fallback_chain": config.FALLBACK_CHAIN
        }
    return {"status": "error", "message": f"Proveedor '{provider_name}' no disponible"}


@app.post("/set-fallback-chain")
async def set_fallback_chain(
    chain: list = Body(...),
    x_node_token: str = Header(None)
):
    """Definir orden de fallback (requiere NODE_TOKEN)"""

    if not valid_node_token(x_node_token):
        return {"status": "error", "message": "Token no válido"}

    valid_providers = list(config.PROVIDERS_CONFIG.keys())
    if all(p in valid_providers for p in chain):
        config.FALLBACK_CHAIN = chain
        settings = get_settings()
        settings.update_provider(config.ACTIVE_PROVIDER, chain)
        return {
            "status": "ok",
            "fallback_chain": config.FALLBACK_CHAIN,
            "message": "Cadena de fallback actualizada"
        }
    return {
        "status": "error",
        "message": f"Proveedores inválidos. Válidos: {valid_providers}"
    }


@app.get("/api/config")
async def get_config(x_node_token: str = Header(None)):
    """Obtiene configuración completa (NODE_TOKEN requerido)"""

    if not valid_node_token(x_node_token):
        return {"status": "error", "message": "Token no válido"}

    settings = get_settings()
    return {
        "status": "ok",
        "config": settings.settings,
        "current_state": {
            "active_provider": config.ACTIVE_PROVIDER,
            "fallback_chain": config.FALLBACK_CHAIN,
            "stt_provider": os.environ.get("IGRIS_STT_PROVIDER", "local"),
            "tts_provider": os.environ.get("IGRIS_TTS_PROVIDER", "local"),
        }
    }


@app.post("/api/config")
async def save_config(
    new_config: dict,
    x_node_token: str = Header(None)
):
    """Guarda configuración (NODE_TOKEN requerido)"""

    if not valid_node_token(x_node_token):
        return {"status": "error", "message": "Token no válido"}

    settings = get_settings()
    try:
        settings.settings.update(new_config)
        settings.save()

        if "ai" in new_config:
            config.ACTIVE_PROVIDER = new_config["ai"].get("primary_provider", config.ACTIVE_PROVIDER)
            config.FALLBACK_CHAIN = new_config["ai"].get("fallback_chain", config.FALLBACK_CHAIN)

        return {
            "status": "ok",
            "message": "Configuración guardada",
            "config": settings.settings
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/config/download")
async def download_config(x_node_token: str = Header(None)):
    """Descargar configuración para Raspberry Pi (NODE_TOKEN requerido)"""

    if not valid_node_token(x_node_token):
        return {"status": "error", "message": "Token no válido"}

    settings = get_settings()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": settings.settings
    }


# ============= WEBSOCKET (Chat con voz - requiere NODE_TOKEN) =============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para chat con voz (STT + TTS)"""
    # Log that we've entered the WebSocket endpoint
    print(f"WEBSOCKET ENDPOINT ENTERED: client={websocket.client}")
    
    # Intentar obtener token del parámetro de consulta ?token=...
    token = websocket.query_params.get("token")
    
    # Si no está en query params, intentar obtenerlo del encabezado Sec-WebSocket-Protocol
    if not token:
        protocol_header = websocket.headers.get("sec-websocket-protocol", "")
        if protocol_header.startswith("node-token, "):
            # Formato esperado: "node-token, <actual_token>"
            token = protocol_header[12:]  # Eliminar el prefijo "node-token, "
        elif protocol_header == "node-token":
            # Caso alternativo: solo el protocolo sin token (no debería ocurrir)
            token = ""
        # Si no se encontró el protocolo esperado, token permanece vacío
    
    # Debug: print token and NODE_TOKEN (first and last 4 chars) if validation fails
    if not valid_node_token(token):
        # Only show partial tokens for security in logs
        def _mask(s):
            if not s or len(s) < 8:
                return s
            return s[:4] + "..." + s[-4:]
        token_masked = _mask(token)
        node_token_masked = _mask(NODE_TOKEN)
        print(f"WEBSOCKET DEBUG: token='{token_masked}', NODE_TOKEN='{node_token_masked}', query_params={dict(websocket.query_params)}, headers_sec_websocket_protocol='{websocket.headers.get('sec-websocket-protocol', '')}'")
        await websocket.close(code=4001, reason="Token no válido o formato incorrecto")
        return

    await websocket.accept()
    session = brain.new_session()

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "message":
                text = data.get("text", "")
                response = await session.say(text)

                await websocket.send_json({
                    "type": "response",
                    "text": response,
                    "provider": config.get_active_provider()
                })

            elif data.get("type") == "audio":
                # Procesar audio (futuro)
                pass

    except WebSocketDisconnect:
        print("✅ WebSocket desconectado")
    except Exception as e:
        print(f"❌ Error WebSocket: {e}")
        await websocket.send_json({"error": str(e)})


# CSP Header para WebSocket
@app.middleware("http")
async def add_csp_header(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self' https://igris.zottagroup.com wss://igris.zottagroup.com; script-src 'self';"
    return response
# ============= CHAT VÍA HTTP (alternativa a WebSocket) =============
from pydantic import BaseModel

class ChatRequest(BaseModel):
    text: str

@app.post("/api/chat")
async def http_chat(req: ChatRequest):
    try:
        session = brain.new_session()
        reply = await session.say(req.text)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        return {"status": "error", "message": str(e)}




# ============= ROOT =============

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "IGRIS",
        "version": "2.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "auth": "/auth/register, /auth/login, /auth/me",
            "2fa": "/auth/2fa/setup, /auth/2fa/verify, /auth/2fa/disable",
            "profiles": "/api/profiles, /api/profiles/{id}",
            "ai_config": "/api/ai-config",
            "dashboard": "/api/dashboard",
            "websocket": "/ws (con NODE_TOKEN en header)"
        }
    }


# Ejecutar con: uvicorn server.main:app --host 0.0.0.0 --port 8000



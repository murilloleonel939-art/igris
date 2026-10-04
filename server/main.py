"""
IGRIS - Servidor FastAPI con Autenticación, 2FA, y Panel de Control
"""
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://webigris.zottagroup.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)

# Incluir routers con prefijo /auth
app.include_router(auth_router, prefix="/auth")
app.include_router(profile_router, prefix="/api")

# Instancia global del cerebro
brain = Brain()
NODE_TOKEN = os.environ.get("NODE_TOKEN", "")

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
    
    if not x_node_token or x_node_token != NODE_TOKEN:
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
    
    if not x_node_token or x_node_token != NODE_TOKEN:
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
    
    if not x_node_token or x_node_token != NODE_TOKEN:
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
    
    if not x_node_token or x_node_token != NODE_TOKEN:
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
    
    if not x_node_token or x_node_token != NODE_TOKEN:
        return {"status": "error", "message": "Token no válido"}
    
    settings = get_settings()
    return {
        "status": "ok",
        "timestamp": "2024-10-04T00:00:00Z",
        "config": settings.settings
    }


# ============= WEBSOCKET (Chat con voz - requiere NODE_TOKEN) =============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para chat con voz (STT + TTS)"""
    
    # Verificar NODE_TOKEN en headers
    token = websocket.headers.get("node-token")
    if not token or token != NODE_TOKEN:
        await websocket.close(code=4001, reason="Token no válido")
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

"""
IGRIS - Servidor FastAPI simplificado para solo chat con Igris
"""
import os
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core import Brain, config
from core.settings_manager import get_settings
from core import tts
from core.database import init_db

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
    """Endpoint de chat simple - sin autenticación requerida"""
    try:
        session = brain.new_session()
        reply = await session.say(req.text)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        return {"status": "error", "message": str(e)}
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
            "chat": "/api/chat (POST)"
        }
    }


# Ejecutar con: uvicorn server.main:app --host 0.0.0.0 --port 8000
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

# Trivial update to force new commit for deployment - 1791253999

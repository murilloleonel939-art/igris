"""
IGRIS - Servidor FastAPI simplificado para solo chat con Iris
"""
import os
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core import Brain, config
from core.database import init_db

# Inicializar BD
init_db()

app = FastAPI(
    title="IGRIS Chat",
    description="Servidor de chat simple con Iris",
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


# ============= ROOT =============

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "IGRIS Chat",
        "version": "1.0.0",
        "status": "operational",
        "debug": "test",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "chat": "/api/chat (POST)"
        }
    }


# Ejecutar con: uvicorn server.main:app --host 0.0.0.0 --port 8000
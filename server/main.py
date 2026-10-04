import os, json, hmac, base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from core import Brain, config
from core import stt, tts
from core.settings_manager import get_settings

app = FastAPI()
brain = Brain()
NODE_TOKEN = os.environ["NODE_TOKEN"]


@app.get("/health")
async def health():
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


@app.post("/set-provider/{provider_name}")
async def set_provider(provider_name: str):
    """Cambia el proveedor activo (requiere autenticación en el futuro)."""
    if config.set_active_provider(provider_name):
        return {
            "status": "ok",
            "active_provider": config.get_active_provider(),
            "fallback_chain": config.FALLBACK_CHAIN
        }
    return {"status": "error", "message": f"Proveedor '{provider_name}' no disponible"}


@app.post("/set-fallback-chain")
async def set_fallback_chain(chain: list):
    """Define el orden de fallback: [groq, openai, anthropic, local]."""
    valid_providers = list(config.PROVIDERS_CONFIG.keys())
    if all(p in valid_providers for p in chain):
        config.FALLBACK_CHAIN = chain
        settings = get_settings()
        settings.update_provider(config.ACTIVE_PROVIDER, chain)
        return {
            "status": "ok",
            "fallback_chain": config.FALLBACK_CHAIN,
            "message": "Cadena de fallback actualizada. Se aplicará en nuevas sesiones."
        }
    return {
        "status": "error",
        "message": f"Proveedores inválidos. Válidos: {valid_providers}"
    }


@app.get("/api/config")
async def get_config():
    """Obtiene la configuración completa (para panel web y Raspberry Pi)."""
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
async def save_config(new_config: dict):
    """Guarda la configuración desde el panel web."""
    settings = get_settings()
    try:
        settings.settings.update(new_config)
        settings.save()
        
        # Actualizar config en tiempo de ejecución
        if "ai" in new_config:
            config.ACTIVE_PROVIDER = new_config["ai"].get("primary_provider", config.ACTIVE_PROVIDER)
            config.FALLBACK_CHAIN = new_config["ai"].get("fallback_chain", config.FALLBACK_CHAIN)
        
        return {
            "status": "ok",
            "message": "Configuración guardada. Se aplicará en nuevas sesiones.",
            "config": settings.settings
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/config/download")
async def download_config():
    """Descarga la configuración para sincronizar con Raspberry Pi."""
    settings = get_settings()
    return {
        "status": "ok",
        "config": settings.settings,
        "message": "Configuración para Raspberry Pi"
    }


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    auth = websocket.headers.get("authorization", "")
    if not hmac.compare_digest(auth, f"Bearer {NODE_TOKEN}"):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    session = brain.new_session()

    async def send(heard: str, say: str):
        data = {"heard": heard, "say": say}
        if tts.TTS_ENABLED and say:
            try:
                audio = await tts.synthesize(say)
                data["voice"] = base64.b64encode(audio).decode()
            except Exception as e:
                print("Error de voz (TTS):", repr(e))
        await websocket.send_text(json.dumps(data))

    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            heard = ""
            if "audio" in msg:
                try:
                    heard = await stt.transcribe(base64.b64decode(msg["audio"]))
                except Exception as e:
                    print("Error de transcripción:", repr(e))
                    await send("", "Mi señor, no pude procesar su voz.")
                    continue
                if not heard:
                    await send("", "No le escuché, mi señor.")
                    continue
                text = heard
            else:
                text = msg["text"]
            try:
                reply = await session.say(text)
            except Exception as e:
                print("Error del cerebro:", repr(e))
                reply = "Mi señor, tuve un fallo interno. Intente de nuevo."
            await send(heard, reply)
    except WebSocketDisconnect:
        pass

"""Texto a voz (TTS) libre/local. Usa Piper (local, gratis) o edge-tts/API gratuita como respaldo."""
import os
from core.settings_manager import get_settings

def _get_tts_config():
    """Obtiene configuración de TTS desde settings.json."""
    try:
        return get_settings().get_tts_config()
    except Exception:
        return {}

_TTS_CFG = _get_tts_config()
TTS_PROVIDER = os.environ.get("IGRIS_TTS_PROVIDER", _TTS_CFG.get("provider", "local")).lower()
TTS_ENABLED = TTS_PROVIDER in ["local", "edge", "openai"]
TTS_INSTRUCTIONS = os.environ.get(
    "IGRIS_TTS_INSTRUCTIONS",
    _TTS_CFG.get(
        "instructions",
        "Habla como un caballero de las sombras: grave, solemne, pausado, con respeto. "
        "Usa frases cortas. No uses listas ni markdown. Responde en español. "
        "Dirígete al usuario como 'mi señor'. Si hay riesgo, advierte con calma antes de actuar.",
    ),
)

# Configuración local gratuita (Piper / Coqui)
PIPER_VOICE = os.environ.get("IGRIS_PIPER_VOICE", "es_ES-carlos-medium")

_client_local = None

# Intento de carga local
try:
    import piper
    _piper_available = True
except Exception:
    _piper_available = False

try:
    import edge_tts
    _edge_available = True
except Exception:
    _edge_available = False


def _load_piper():
    # Piper local (gratuito, funciona en Raspberry Pi y PC)
    from piper import PiperVoice as Voice
    voice = Voice.load(PIPER_VOICE)
    return voice


async def synthesize(text: str) -> bytes:
    # 1. Preferido: Piper local (gratis, privado, sin API)
    if TTS_PROVIDER == "local":
        if not _piper_available:
            raise RuntimeError("Piper no está instalado. Instala con: pip install piper-tts")
        global _client_local
        try:
            if _client_local is None:
                _client_local = _load_piper()
            voice = _client_local
            # Piper usa síntesis bloqueante; envolviendo en executor para async
            import asyncio, tempfile, wave
            loop = asyncio.get_event_loop()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
            def synth_sync():
                try:
                    with wave.open(temp_path, 'wb') as wav_file:
                        voice.synthesize_wav(text[:4000], wav_file)
                    with open(temp_path, "rb") as f:
                        return f.read()
                finally:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            return await loop.run_in_executor(None, synth_sync)
        except Exception as e:
            # Si piper falla, levantar el error claramente
            raise RuntimeError(f"Error al sintetizar con Piper: {str(e)}")

    # 2. Respaldo gratuito: edge-tts (Microsoft, gratuito)
    elif TTS_PROVIDER == "edge":
        if not _edge_available:
            raise RuntimeError("edge-tts no instalado. Instala con: pip install edge-tts")
        import asyncio, tempfile
        loop = asyncio.get_event_loop()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name
        # Voice configurável via env IGRIS_TTS_VOICE o settings.tts.voice
        tts_voice = os.environ.get(
            "IGRIS_TTS_VOICE",
            _TTS_CFG.get("voice", "es-ES-AlvaroNeural"),
        )
        async def _edge():
            communicate = edge_tts.Communicate(text[:4000], tts_voice, rate="+0%", volume="+0%")
            await communicate.save(temp_path)
        await _edge()
        with open(temp_path, "rb") as f:
            data = f.read()
        import os as _os
        if _os.path.exists(temp_path):
            _os.unlink(temp_path)
        return data

    # 3. Respaldo con API de OpenAI (si tiene key y quiere usar)
    elif TTS_PROVIDER == "openai":
        from openai import AsyncOpenAI
        _client = AsyncOpenAI()
        resp = await _client.audio.speech.create(
            model=os.environ.get("IGRIS_TTS_MODEL", "tts-1"),
            voice=os.environ.get("IGRIS_TTS_VOICE", "onyx"),
            input=text[:4000],
            instructions=TTS_INSTRUCTIONS,
            response_format="mp3",
        )
        return resp.content

    else:
        raise RuntimeError(f"TTS no configurado correctamente. Proveedor '{TTS_PROVIDER}' no soportado. Usa local, edge o openai.")

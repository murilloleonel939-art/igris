"""Voz a texto (prototipo): usa la API de OpenAI desde el servidor.
Más adelante se moverá a la Raspberry Pi, después de verificar tu voz."""
import io, os
from openai import AsyncOpenAI

STT_MODEL = os.environ.get("IGRIS_STT_MODEL", "whisper-1")
_client = None


async def transcribe(wav_bytes: bytes) -> str:
    global _client
    if _client is None:
        _client = AsyncOpenAI()  # usa OPENAI_API_KEY
    f = io.BytesIO(wav_bytes)
    f.name = "voz.wav"
    r = await _client.audio.transcriptions.create(model=STT_MODEL, file=f, language="es")
    return (r.text or "").strip()

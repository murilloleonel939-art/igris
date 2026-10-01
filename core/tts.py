"""Texto a voz: usa la API de OpenAI desde el servidor y devuelve audio mp3.
Más adelante, en la Raspberry Pi, habrá una versión local (Piper) como respaldo."""
import os
from openai import AsyncOpenAI

TTS_ENABLED = os.environ.get("IGRIS_TTS", "openai").lower() == "openai"
TTS_MODEL = os.environ.get("IGRIS_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.environ.get("IGRIS_TTS_VOICE", "onyx")
TTS_INSTRUCTIONS = os.environ.get(
    "IGRIS_TTS_INSTRUCTIONS",
    "Habla en español con voz grave, solemne y pausada, como un caballero leal "
    "y disciplinado. Tono serio, respetuoso y firme, sin exagerar.",
)
_client = None


async def synthesize(text: str) -> bytes:
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    resp = await _client.audio.speech.create(
        model=TTS_MODEL, voice=TTS_VOICE, input=text[:4000],
        instructions=TTS_INSTRUCTIONS, response_format="mp3",
    )
    return resp.content

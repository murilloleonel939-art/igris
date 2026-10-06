# core/stt.py
import io
import os
import tempfile
from typing import Union

# ---- OPTIONAL: openai (for the cloud API) ----
try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

# ---- OPTIONAL: whisper (for local STT) ----
try:
    import whisper  # type: ignore
except Exception:  # pragma: no cover
    whisper = None  # type: ignore

AudioInput = Union[bytes, bytearray, memoryview, io.BytesIO]

_whisper_model = None


def _to_bytes(audio: AudioInput) -> bytes:
    """Normaliza cualquier entrada de audio a bytes.

    Acepta bytes, bytearray (lo que devuelve download_as_bytearray de Telegram),
    memoryview y objetos tipo archivo (BytesIO, UploadFile.file, etc.).
    """
    if isinstance(audio, (bytes, bytearray, memoryview)):
        return bytes(audio)
    if hasattr(audio, "read"):
        data = audio.read()
        return bytes(data)
    raise TypeError(f"Tipo de audio no soportado: {type(audio).__name__}")


def _load_whisper_model():
    """Carga (y cachea) un modelo de Whisper local la primera vez que se necesita."""
    global _whisper_model
    if _whisper_model is None:
        if whisper is None:
            raise RuntimeError(
                "El paquete 'openai-whisper' no está instalado. "
                "Instálalo con: pip install openai-whisper"
            )
        model_name = os.getenv("IGRIS_WHISPER_MODEL", "base")
        _whisper_model = whisper.load_model(model_name)
    return _whisper_model


def transcribe(audio: AudioInput) -> str:
    """
    Recibe el audio (bytes, bytearray o archivo en memoria; Telegram envía
    normalmente OGG Opus) y devuelve el texto reconocido.

    Es una función bloqueante: desde código async llámala con
    `await asyncio.to_thread(transcribe, audio)`.
    """
    provider = os.getenv("IGRIS_STT_PROVIDER", "local").lower().strip()
    data = _to_bytes(audio)

    if provider == "openai":
        if OpenAI is None:
            raise RuntimeError(
                "El paquete 'openai' no está instalado. "
                "Instálalo con: pip install openai"
            )
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta la variable de entorno OPENAI_API_KEY necesaria para usar Whisper en la nube."
            )
        client = OpenAI(api_key=api_key)
        try:
            resp = client.audio.transcriptions.create(
                model=os.getenv("IGRIS_STT_MODEL", "whisper-1"),
                file=("audio.ogg", data, "audio/ogg"),
                language="es",
            )
            return (resp.text or "").strip()
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"Error al llamar a la API de Whisper de OpenAI: {e}")

    elif provider == "local":
        # openai-whisper trabaja con rutas (usa ffmpeg por debajo): archivo temporal.
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            model = _load_whisper_model()
            result = model.transcribe(tmp_path, fp16=False, language="es")
            return (result.get("text") or "").strip()
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    else:
        raise RuntimeError(
            f"Proveedor de STT desconocido '{provider}'. "
            "Utiliza 'openai' o 'local'."
        )

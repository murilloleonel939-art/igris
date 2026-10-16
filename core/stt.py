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
_whisper_model_name = None


def _settings() -> dict:
    """Configuración STT persistente, con variables de entorno como base."""
    try:
        from core.settings_manager import get_settings
        return get_settings().get_stt_config()
    except Exception:
        return {}


def _language() -> str:
    """Idioma del audio (código ISO-639-1)."""
    lang = (_settings().get("language") or os.getenv("IGRIS_STT_LANGUAGE", "es")).strip().lower().split("-")[0]
    return lang or "es"


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
    """Carga y cachea el modelo local activo; recarga si se cambia desde ajustes."""
    global _whisper_model, _whisper_model_name
    model_name = _settings().get("local_model") or os.getenv("IGRIS_WHISPER_MODEL", "base")
    if _whisper_model is None or _whisper_model_name != model_name:
        if whisper is None:
            raise RuntimeError(
                "El paquete 'openai-whisper' no está instalado. "
                "Instálalo con: pip install openai-whisper"
            )
        _whisper_model = whisper.load_model(model_name)
        _whisper_model_name = model_name
    return _whisper_model


def transcribe(audio: AudioInput, suffix: str = ".ogg") -> str:
    """
    Recibe el audio y su extensión real (por defecto OGG; el navegador usa WebM).
    Devuelve el texto reconocido.

    Es una función bloqueante: desde código async llámala con
    `await asyncio.to_thread(transcribe, audio)`.
    """
    stt_config = _settings()
    provider = (stt_config.get("provider") or os.getenv("IGRIS_STT_PROVIDER", "local")).lower().strip()
    data = _to_bytes(audio)

    if provider == "openai":
        if OpenAI is None:
            raise RuntimeError(
                "El paquete 'openai' no está instalado. "
                "Instálalo con: pip install openai"
            )
        # No usar OPENAI_API_KEY: en despliegues de Igris puede ser la clave Pateway.
        api_key = os.getenv("IGRIS_STT_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta IGRIS_STT_API_KEY (clave OpenAI directa) para usar Whisper en la nube."
            )
        base_url = (os.getenv("IGRIS_STT_API_BASE") or "https://api.openai.com/v1").rstrip("/")
        client = OpenAI(api_key=api_key, base_url=base_url)
        try:
            resp = client.audio.transcriptions.create(
                model=stt_config.get("cloud_model") or os.getenv("IGRIS_STT_MODEL", "whisper-1"),
                file=(f"audio{suffix}", data, "audio/webm" if suffix == ".webm" else "audio/ogg"),
                language=_language(),
            )
            return (resp.text or "").strip()
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"Error al llamar a la API de Whisper de OpenAI: {e}")

    elif provider == "local":
        # openai-whisper trabaja con rutas (usa ffmpeg por debajo): archivo temporal.
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            model = _load_whisper_model()
            result = model.transcribe(tmp_path, fp16=False, language=_language())
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

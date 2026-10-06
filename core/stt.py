# core/stt.py
import os
import io
import tempfile
from typing import Union

# ---- OPTIONAL: openai (for the cloud API) ----
try:
    import openai  # type: ignore
except Exception:  # pragma: no cover
    openai = None  # type: ignore

# ---- OPTIONAL: whisper (for local STT) ----
try:
    import whisper  # type: ignore
except Exception:  # pragma: no cover
    whisper = None  # type: ignore

def _load_whisper_model(model_name: str = "tiny"):
    """
    Carga (y cachea) un modelo de Whisper local.
    Se llama solo la primera vez que se necesita STT local.
    """
    global _whisper_model
    if "_whisper_model" not in globals() or _whisper_model is None:
        if whisper is None:
            raise RuntimeError(
                "El paquete 'openai-whisper' no está instalado. "
                "Instálalo con: pip install openai-whisper"
            )
        # El modelo se descarga automáticamente la primera vez.
        _whisper_model = whisper.load_model(model_name)
    return _whisper_model  # type: ignore


def transcribe(audio_bytes: Union[bytes, io.BytesIO]) -> str:
    """
    Recibe un arreglo de bytes con el audio (formato que Telegram envía:
    normalmente OGG Opus) y devuelve el texto reconocido.
    """
    provider = os.getenv("IGRIS_STT_PROVIDER", "local").lower().strip()

    if provider == "openai":
        if openai is None:
            raise RuntimeError(
                "El paquete 'openai' no está instalado. "
                "Instálalo con: pip install openai"
            )
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta la variable de entorno OPENAI_API_KEY necesaria para usar Whisper en la nube."
            )
        openai.api_key = api_key  # type: ignore

        # Telegram envía OGG Opus; OpenAI acepta muchos formatos.
        audio_file = ("audio.ogg", audio_bytes, "audio/ogg")
        try:
            resp = openai.Audio.transcribe(  # type: ignore
                model=os.getenv("IGRIS_STT_MODEL", "whisper-1"),
                file=audio_file,
            )
            return resp.get("text", "").strip()
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"Error al llamar a la API de Whisper de OpenAI: {e}")

    elif provider == "local":
        # Guardamos los bytes en un archivo temporal porque whisper.load_audio
        # espera una ruta o un file‑like object.
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes if isinstance(audio_bytes, bytes) else audio_bytes.read())
            tmp_path = tmp.name

        try:
            model = _load_whisper_model()
            result = model.transcribe(tmp_path, fp16=False)  # type: ignore
            text = result.get("text", "").strip()
            return text
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

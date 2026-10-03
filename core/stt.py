"""STT (Speech-to-Text) libre/local. Usa Whisper local (faster-whisper) o la API gratuita de OpenAI como respaldo."""
import io, os, sys
STT_PROVIDER = os.environ.get("IGRIS_STT_PROVIDER", "local").lower()  # "local" o "openai"
STT_MODEL = os.environ.get("IGRIS_STT_MODEL", "tiny")  # para local: tiny, base, small, medium, large
STT_LANGUAGE = os.environ.get("IGRIS_STT_LANGUAGE", "es")

_client_local = None

# Intento de carga local libre (faster-whisper / whisper)
try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

try:
    import whisper
except Exception:
    whisper = None


def _load_local_model():
    model_name = STT_MODEL
    if WhisperModel is not None:
        # faster-whisper (más rápido, libre)
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        return model, "faster"
    elif whisper is not None:
        # openai-whisper local
        model = whisper.load_model(model_name)
        return model, "whisper"
    return None, None


async def transcribe(wav_bytes: bytes) -> str:
    # 1. Intentar local/gratuito
    if STT_PROVIDER == "local" and (WhisperModel is not None or whisper is not None):
        global _client_local
        if _client_local is None:
            model, mode = _load_local_model()
            _client_local = (model, mode)
        model, mode = _client_local
        if model is None:
            raise RuntimeError("Modelo local no cargado.")
        # Guardar temporalmente para decodificar (o usar BytesIO si es posible)
        # faster-whisper puede usar audio numpy; simplificamos con archivo temporal
        import tempfile, soundfile as sf
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                temp_path = f.name
            if mode == "faster":
                segments, _ = model.transcribe(temp_path, language=STT_LANGUAGE, task="transcribe")
                text = " ".join([seg.text for seg in segments])
            else:
                result = model.transcribe(temp_path, language=STT_LANGUAGE)
                text = result.get("text", "")
            return text.strip()
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
    # 2. Respaldo con API gratuita de OpenAI (si se configura OPENAI_API_KEY libre)
    if STT_PROVIDER == "openai" or (STT_PROVIDER == "local" and (WhisperModel is None and whisper is None)):
        try:
            import openai
            from openai import AsyncOpenAI
            client = AsyncOpenAI()
            f = io.BytesIO(wav_bytes)
            f.name = "voz.wav"
            r = await client.audio.transcriptions.create(
                model=STT_MODEL, file=f, language=STT_LANGUAGE,
                prompt="Igris, asistente personal. Órdenes para la casa y el trabajo."
            )
            return (r.text or "").strip()
        except Exception as e:
            raise RuntimeError(f"STT falló (openai): {e}")
    raise RuntimeError("STT no configurado. Usa local (faster-whisper/whisper) o openai.")

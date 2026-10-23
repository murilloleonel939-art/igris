# core/stt.py
import io
import os
import subprocess
import tempfile
import threading
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

try:
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover
    WhisperModel = None  # type: ignore

AudioInput = Union[bytes, bytearray, memoryview, io.BytesIO]

_whisper_model = None
_whisper_model_name = None
_faster_whisper_model = None
_faster_whisper_model_name = None
_faster_whisper_compute_type = None
# Cargar Whisper tarda segundos y ocupa cientos de MB. Sin lock, dos órdenes de
# voz simultáneas veían el modelo vacío y lo cargaban dos veces, con el mismo
# pico de memoria que tumbaba el contenedor con TitaNet.
_stt_lock = threading.Lock()


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


def _local_engine(settings: dict) -> str:
    return (settings.get("local_engine") or os.getenv("IGRIS_STT_LOCAL_ENGINE", "whisper")).strip().lower()


def _transcribe_whisper_cpp(tmp_path: str, settings: dict, language: str) -> str:
    """Transcribe con whisper.cpp usando un modelo GGML/GGUF local."""
    binary = settings.get("whisper_cpp_binary") or os.getenv("IGRIS_WHISPER_CPP_BINARY", "whisper-cli")
    model_path = settings.get("whisper_cpp_model") or os.getenv("IGRIS_WHISPER_CPP_MODEL")
    if not model_path:
        raise RuntimeError("Falta IGRIS_WHISPER_CPP_MODEL con la ruta del modelo GGML/GGUF.")
    wav_path = None
    output_prefix = None
    output_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
            wav_path = wav_file.name
        with tempfile.NamedTemporaryFile(prefix="igris-whisper-cpp-", delete=False) as output_file:
            output_prefix = output_file.name
        output_path = f"{output_prefix}.txt"
        os.remove(output_prefix)
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path],
            capture_output=True, text=True, check=True,
        )
        result = subprocess.run(
            [binary, "-m", model_path, "-f", wav_path, "-l", language, "-nt", "-np", "-otxt", "-of", output_prefix],
            capture_output=True, text=True, check=True,
        )
        if os.path.isfile(output_path):
            with open(output_path, encoding="utf-8") as transcript_file:
                transcript = transcript_file.read().strip()
        else:
            transcript = (result.stdout or "").strip()
        if not transcript:
            raise RuntimeError("whisper.cpp terminó sin generar texto. Comprueba el volumen y que el audio contenga voz.")
        return transcript
    except FileNotFoundError as exc:
        raise RuntimeError(f"No se encontró ffmpeg o el binario de whisper.cpp: {exc.filename}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"whisper.cpp no pudo procesar el audio: {detail}") from exc
    finally:
        for temporary_path in (wav_path, output_prefix, output_path):
            if temporary_path:
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass


def _load_whisper_model(model_name: str):
    """Carga y cachea el modelo openai-whisper seleccionado."""
    global _whisper_model, _whisper_model_name
    if _whisper_model is not None and _whisper_model_name == model_name:
        return _whisper_model
    with _stt_lock:
        # Doble comprobación: el primer hilo carga y el resto reutiliza.
        if _whisper_model is None or _whisper_model_name != model_name:
            if whisper is None:
                raise RuntimeError("El paquete 'openai-whisper' no está instalado.")
            _whisper_model = whisper.load_model(model_name)
            _whisper_model_name = model_name
    return _whisper_model


def _load_faster_whisper_model(model_name: str, compute_type: str):
    """Carga y cachea faster-whisper con el tipo de cómputo elegido."""
    global _faster_whisper_model, _faster_whisper_model_name, _faster_whisper_compute_type
    if (
        _faster_whisper_model is not None
        and _faster_whisper_model_name == model_name
        and _faster_whisper_compute_type == compute_type
    ):
        return _faster_whisper_model
    with _stt_lock:
        if _faster_whisper_model is None or _faster_whisper_model_name != model_name or _faster_whisper_compute_type != compute_type:
            if WhisperModel is None:
                raise RuntimeError("El paquete 'faster-whisper' no está instalado.")
            _faster_whisper_model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
            _faster_whisper_model_name = model_name
            _faster_whisper_compute_type = compute_type
    return _faster_whisper_model


def _transcribe_local(tmp_path: str, settings: dict) -> str:
    model_name = settings.get("local_model") or os.getenv("IGRIS_WHISPER_MODEL", "base")
    engine = _local_engine(settings)
    language = _language()
    if engine == "whisper":
        result = _load_whisper_model(model_name).transcribe(tmp_path, fp16=False, language=language)
        return (result.get("text") or "").strip()
    if engine == "faster-whisper":
        compute_type = settings.get("local_compute_type") or os.getenv("IGRIS_STT_COMPUTE_TYPE", "int8")
        segments, _ = _load_faster_whisper_model(model_name, compute_type).transcribe(
            tmp_path,
            language=language,
            beam_size=1,
            best_of=1,
            temperature=0,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
    if engine == "whisper.cpp":
        return _transcribe_whisper_cpp(tmp_path, settings, language)
    raise RuntimeError("Motor local STT desconocido. Usa whisper, faster-whisper o whisper.cpp.")


def transcribe(audio: AudioInput, suffix: str = ".ogg", provider: str = None) -> str:
    """
    Recibe el audio y su extensión real (por defecto OGG; el navegador usa WebM).
    Devuelve el texto reconocido.

    Es una función bloqueante: desde código async llámala con
    `await asyncio.to_thread(transcribe, audio)`.
    
    Si `provider` es None, lee de configuración/env; si se pasa explícitamente, lo usa.
    """
    stt_config = _settings()
    if provider is None:
        provider = (stt_config.get("provider") or os.getenv("IGRIS_STT_PROVIDER", "local")).lower().strip()
    else:
        provider = provider.lower().strip()
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
            return _transcribe_local(tmp_path, stt_config)
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

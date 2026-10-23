"""Verificación local de hablante mediante embeddings NVIDIA NeMo/TitaNet."""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from typing import Iterable

import numpy as np

from core.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)

# Nivel de energía al que se lleva el audio antes de extraer el embedding, y
# ganancia máxima aplicable. 0.06 equivale a una voz cercana y clara; el tope de
# 12x evita que una toma casi muda se convierta en ruido amplificado que el
# modelo interpretaría como habla.
TARGET_RMS = 0.06
MAX_GAIN = 12.0
_encoder = None
# La carga de TitaNet tarda decenas de segundos y consume ~1 GB. Sin este lock,
# dos turnos de voz simultáneos veían _encoder a None y cargaban el modelo dos
# veces (verificado: 2 x 25 s y +1.1 GB de RAM).
_encoder_lock = threading.Lock()


def _get_encoder():
    global _encoder
    if _encoder is not None:
        return _encoder
    with _encoder_lock:
        if _encoder is None:
            started = time.monotonic()
            logger.info("Cargando modelo de voz NeMo/TitaNet (una sola vez por proceso)")
            try:
                from nemo.collections.asr.models import EncDecSpeakerLabelModel
            except ImportError as exc:
                raise RuntimeError(f"No se pudo cargar NVIDIA NeMo: {exc}") from exc
            model_name = os.getenv("IGRIS_VOICE_MODEL", "nvidia/speakerverification_en_titanet_large")
            encoder = EncDecSpeakerLabelModel.from_pretrained(model_name=model_name)
            encoder.eval()
            _encoder = encoder
            logger.info("Modelo de voz cargado en %.1f s", time.monotonic() - started)
    return _encoder


def _wav_bytes(audio: bytes, suffix: str = ".ogg") -> bytes:
    """Convierte audio recibido del navegador o Telegram a WAV mono 16 kHz.

    Solo se recorta el silencio del principio. Antes se usaba
    ``silenceremove=...:stop_periods=-1``, que elimina TODOS los silencios
    internos y empalma los trozos de voz: según dónde cayeran las pausas al
    hablar, el audio resultante cambiaba y TitaNet devolvía un vector distinto
    para la misma persona. Con la huella recién registrada, el mismo hablante
    daba similitudes entre -0.02 y 0.32, oscilando alrededor del umbral.

    También se quitó ``dynaudnorm=g=15``: recomprimía la dinámica de cada sílaba
    y alteraba el timbre con el que trabaja el modelo. Entre el registro y la
    verificación basta con que el audio llegue sin recortes distintos; el nivel
    lo ajusta el propio modelo.
    """
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as source:
        source.write(audio)
        source_path = source.name
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", source_path,
             # start_periods recorta la espera antes de hablar y conserva las
             # pausas internas, que son parte de cómo habla la persona.
             "-af", "silenceremove=start_periods=1:start_duration=0.10:start_threshold=-40dB:detection=peak",
             "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout
    finally:
        try:
            os.remove(source_path)
        except OSError:
            pass


def embedding(audio: bytes, suffix: str = ".ogg") -> np.ndarray:
    import torch
    import torchaudio

    wav = _wav_bytes(audio, suffix)
    signal, sample_rate = torchaudio.load(io.BytesIO(wav))
    signal = signal.mean(dim=0, keepdim=True)
    # El recorte de silencios puede dejar la señal vacía (micro mudo o toma sin
    # voz). Sin esta comprobación NeMo falla con un IndexError poco claro.
    if signal.shape[1] == 0:
        raise ValueError("El audio no contiene voz reconocible")
    # TitaNet necesita unos 2-3 s de voz continua para dar un vector estable.
    # Con tomas más cortas la similitud baja aunque sea la misma persona, así que
    # conviene verlo en el log junto al score, no adivinarlo.
    duration = signal.shape[1] / float(sample_rate or 16000)
    rms = float(signal.abs().mean())
    logger.info("Embedding de voz: %.2f s, nivel medio %.4f", duration, rms)

    # Nivelar la energía antes de la inferencia. El log del 23-10 mostró que el
    # resultado dependía casi por completo del volumen de entrada: las tomas con
    # nivel 0.001-0.02 daban similitudes de 0.06-0.24 con la huella recién
    # registrada, y las de nivel 0.03-0.04 daban 0.35 o más. El autoGainControl
    # del navegador no compensa micrófonos lejanos, así que lo hace el servidor:
    # al comparar siempre contra el mismo nivel, hablar lejos deja de restar.
    # La ganancia se acota para no convertir ruido de fondo en una falsa voz.
    if rms > 1e-5:
        gain = min(TARGET_RMS / rms, MAX_GAIN)
        # Acotar después de amplificar: una toma con picos altos y media baja
        # podría salirse del rango [-1, 1] y distorsionar el timbre.
        signal = (signal * gain).clamp(-1.0, 1.0)
    signal_length = torch.tensor([signal.shape[1]], dtype=torch.long)
    with torch.no_grad():
        _logits, vector = _get_encoder().forward(
            input_signal=signal,
            input_signal_length=signal_length,
        )
    return vector.squeeze().detach().cpu().numpy().astype(np.float32)


def serialize(vector: np.ndarray | list[np.ndarray]) -> str:
    vectors = vector if isinstance(vector, list) else [vector]
    payload = [base64.b64encode(item.astype(np.float32).tobytes()).decode("ascii") for item in vectors]
    return encrypt(json.dumps(payload)) or ""


def deserialize(value: str) -> list[np.ndarray]:
    raw = decrypt(value)
    if not raw:
        raise ValueError("Huella de voz inválida")
    try:
        payload = json.loads(raw)
        if isinstance(payload, str):
            payload = [payload]
    except json.JSONDecodeError:
        payload = [raw]
    return [np.frombuffer(base64.b64decode(item), dtype=np.float32) for item in payload]


def similarity(left: np.ndarray, right: np.ndarray) -> float:
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    return float(np.dot(left, right) / denominator) if denominator else -1.0


def average_embedding(audio_items: Iterable[bytes], suffix: str = ".ogg") -> list[np.ndarray]:
    vectors = [embedding(item, suffix) for item in audio_items]
    if not vectors:
        raise ValueError("Se necesita al menos una muestra de voz")
    return vectors


def verify(audio: bytes, stored: str, suffix: str = ".ogg") -> tuple[bool, float]:
    threshold = float(os.getenv("IGRIS_VOICE_THRESHOLD", "0.40"))
    current = embedding(audio, suffix)
    scores = [similarity(current, sample) for sample in deserialize(stored)]
    score = max(scores) if scores else -1.0
    return score >= threshold, score


def available() -> bool:
    try:
        import nemo.collections.asr  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False

__all__ = ["average_embedding", "serialize", "verify", "available"]

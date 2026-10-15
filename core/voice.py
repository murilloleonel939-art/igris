"""Verificación de hablante mediante embeddings ECAPA-TDNN."""
from __future__ import annotations

import base64
import io
import logging
import os
import subprocess
import tempfile
from typing import Iterable

import numpy as np

from core.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)
_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from speechbrain.inference.speaker import SpeakerRecognition
        except ImportError as exc:
            raise RuntimeError("La verificación de voz requiere speechbrain") from exc
        _encoder = SpeakerRecognition.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=os.getenv("IGRIS_VOICE_MODEL_DIR", "/tmp/igris-voice-model"),
        )
    return _encoder


def _wav_bytes(audio: bytes, suffix: str = ".ogg") -> bytes:
    """Convierte audio recibido del navegador o Telegram a WAV mono 16 kHz."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as source:
        source.write(audio)
        source_path = source.name
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", source_path,
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
    if sample_rate != 16000:
        signal = torchaudio.functional.resample(signal, sample_rate, 16000)
    with torch.no_grad():
        vector = _get_encoder().encode_batch(signal)
    return vector.squeeze().detach().cpu().numpy().astype(np.float32)


def serialize(vector: np.ndarray) -> str:
    return encrypt(base64.b64encode(vector.tobytes()).decode("ascii")) or ""


def deserialize(value: str) -> np.ndarray:
    raw = decrypt(value)
    if not raw:
        raise ValueError("Huella de voz inválida")
    return np.frombuffer(base64.b64decode(raw), dtype=np.float32)


def similarity(left: np.ndarray, right: np.ndarray) -> float:
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    return float(np.dot(left, right) / denominator) if denominator else -1.0


def average_embedding(audio_items: Iterable[bytes], suffix: str = ".ogg") -> np.ndarray:
    vectors = [embedding(item, suffix) for item in audio_items]
    if not vectors:
        raise ValueError("Se necesita al menos una muestra de voz")
    result = np.mean(vectors, axis=0)
    norm = np.linalg.norm(result)
    return result / norm if norm else result


def verify(audio: bytes, stored: str, suffix: str = ".ogg") -> tuple[bool, float]:
    threshold = float(os.getenv("IGRIS_VOICE_THRESHOLD", "0.72"))
    score = similarity(embedding(audio, suffix), deserialize(stored))
    return score >= threshold, score


def available() -> bool:
    try:
        import speechbrain  # noqa: F401
        import torchaudio  # noqa: F401
        return True
    except ImportError:
        return False

__all__ = ["average_embedding", "serialize", "verify", "available"]

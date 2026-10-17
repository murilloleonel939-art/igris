import json
import os
import sys
import time
import queue

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
BLOCK_SIZE = 1600
SILENCE_SECONDS = 1.2
MAX_SECONDS = 15


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def capture_audio():
    chunks = []
    started = False
    last_voice = time.monotonic()
    started_at = time.monotonic()
    audio_queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            emit({"type": "status", "message": str(status)})
        audio_queue.put(indata.copy())

    emit({"type": "state", "state": "listening"})
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=BLOCK_SIZE, callback=callback):
        while time.monotonic() - started_at < MAX_SECONDS:
            data = audio_queue.get()
            rms = float(np.sqrt(np.mean(np.square(data))))
            if rms > 0.012:
                started = True
                last_voice = time.monotonic()
            if started:
                chunks.append(data[:, 0])
                if time.monotonic() - last_voice >= SILENCE_SECONDS:
                    break

    if not chunks:
        return None
    audio = np.concatenate(chunks)
    if len(audio) < SAMPLE_RATE * 0.25:
        return ""

    return audio


def transcribe(audio):
    emit({"type": "state", "state": "transcribing"})
    model_size = os.environ.get("IGRIS_WHISPER_MODEL", "small")
    model = WhisperModel(model_size, device="auto", compute_type="auto")
    segments, _ = model.transcribe(audio, language="es", vad_filter=True, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()


if __name__ == "__main__":
    try:
        for attempt in range(3):
            audio = capture_audio()
            if audio is None:
                emit({"type": "retry", "attempt": attempt + 1, "message": "No detecté voz; repite la orden."})
                continue
            text = transcribe(audio)
            if text:
                emit({"type": "result", "text": text})
                break
            emit({"type": "retry", "attempt": attempt + 1, "message": "No entendí la orden; intenta de nuevo."})
        else:
            emit({"type": "error", "message": "No se detectó una orden después de tres intentos."})
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        sys.exit(1)

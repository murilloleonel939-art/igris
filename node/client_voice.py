"""Nodo de prueba con voz completa: hablas (ENTER) o escribes, e Igris te responde hablando."""
import asyncio, base64, ctypes, io, json, os, tempfile, wave, websockets
import sounddevice as sd
import edge_tts

URL = os.environ["IGRIS_URL"]
TOKEN = os.environ["NODE_TOKEN"]
VOICE = os.environ.get("IGRIS_VOICE", "es-CO-GonzaloNeural")
PITCH = os.environ.get("IGRIS_PITCH", "-15Hz")
RATE = os.environ.get("IGRIS_RATE", "-5%")
SAMPLE_RATE = 16000
MAX_SECONDS = 30


def record() -> bytes:
    """Graba del micrófono hasta que pulses ENTER. Devuelve un WAV."""
    chunks = []
    def callback(indata, frames, time, status):
        chunks.append(bytes(indata))
    with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback):
        input("  Escuchando... habla y pulsa ENTER cuando termines. ")
    pcm = b"".join(chunks)[: SAMPLE_RATE * 2 * MAX_SECONDS]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def play_mp3(path: str):
    mci = ctypes.windll.winmm.mciSendStringW
    mci("close igris", None, 0, None)
    mci(f'open "{path}" type mpegvideo alias igris', None, 0, None)
    mci("play igris wait", None, 0, None)
    mci("close igris", None, 0, None)


async def speak(text: str):
    path = os.path.join(tempfile.gettempdir(), "igris_voz.mp3")
    await edge_tts.Communicate(text, VOICE, pitch=PITCH, rate=RATE).save(path)
    await asyncio.to_thread(play_mp3, path)


async def main():
    async with websockets.connect(
        URL, additional_headers={"Authorization": f"Bearer {TOKEN}"},
        max_size=None,
    ) as ws:
        print("Conectado con Igris.")
        print("Pulsa ENTER solo para hablar, o escribe tu mensaje. 'salir' para terminar.")
        while True:
            entry = await asyncio.to_thread(input, "> ")
            if entry.strip().lower() == "salir":
                break
            if entry.strip():
                payload = {"text": entry}
            else:
                try:
                    wav = await asyncio.to_thread(record)
                except Exception as e:
                    print("No pude usar el micrófono:", repr(e))
                    continue
                payload = {"audio": base64.b64encode(wav).decode()}
            await ws.send(json.dumps(payload))
            reply = json.loads(await ws.recv())
            if reply.get("heard"):
                print("Te escuché:", reply["heard"])
            print("Igris:", reply["say"])
            try:
                await speak(reply["say"])
            except Exception as e:
                print("(No pude reproducir la voz:", repr(e), ")")

asyncio.run(main())

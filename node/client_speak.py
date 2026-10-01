"""Nodo de prueba con VOZ DE SALIDA: tú escribes, Igris responde hablando.
Usa edge-tts (voces gratuitas de Microsoft) y el reproductor integrado de Windows."""
import asyncio, ctypes, json, os, tempfile, websockets
import edge_tts

URL = os.environ["IGRIS_URL"]      # wss://tu-direccion/ws
TOKEN = os.environ["NODE_TOKEN"]
VOICE = os.environ.get("IGRIS_VOICE", "es-CO-GonzaloNeural")
PITCH = os.environ.get("IGRIS_PITCH", "-15Hz")   # más negativo = más grave
RATE = os.environ.get("IGRIS_RATE", "-5%")       # más negativo = más lento


def play_mp3(path: str):
    """Reproduce un mp3 con el motor de audio de Windows (sin instalar nada extra)."""
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
        URL, additional_headers={"Authorization": f"Bearer {TOKEN}"}
    ) as ws:
        print("Conectado con Igris. Escribe 'salir' para terminar.")
        while True:
            text = await asyncio.to_thread(input, "Tú: ")
            if text.strip().lower() == "salir":
                break
            await ws.send(json.dumps({"text": text}))
            reply = json.loads(await ws.recv())["say"]
            print("Igris:", reply)
            try:
                await speak(reply)
            except Exception as e:
                print("(No pude reproducir la voz:", repr(e), ")")

asyncio.run(main())

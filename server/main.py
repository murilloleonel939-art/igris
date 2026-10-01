import os, json, hmac, base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from core import Brain
from core import stt, tts

app = FastAPI()
brain = Brain()
NODE_TOKEN = os.environ["NODE_TOKEN"]


@app.get("/health")
async def health():
    return {"status": "ok", "name": "igris"}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    auth = websocket.headers.get("authorization", "")
    if not hmac.compare_digest(auth, f"Bearer {NODE_TOKEN}"):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    session = brain.new_session()

    async def send(heard: str, say: str):
        data = {"heard": heard, "say": say}
        if tts.TTS_ENABLED and say:
            try:
                audio = await tts.synthesize(say)
                data["voice"] = base64.b64encode(audio).decode()
            except Exception as e:
                print("Error de voz (TTS):", repr(e))
        await websocket.send_text(json.dumps(data))

    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            heard = ""
            if "audio" in msg:
                try:
                    heard = await stt.transcribe(base64.b64decode(msg["audio"]))
                except Exception as e:
                    print("Error de transcripción:", repr(e))
                    await send("", "Mi señor, no pude procesar su voz.")
                    continue
                if not heard:
                    await send("", "No le escuché, mi señor.")
                    continue
                text = heard
            else:
                text = msg["text"]
            try:
                reply = await session.say(text)
            except Exception as e:
                print("Error del cerebro:", repr(e))
                reply = "Mi señor, tuve un fallo interno. Intente de nuevo."
            await send(heard, reply)
    except WebSocketDisconnect:
        pass

import os, json, hmac
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from core import Brain
from core.brain import trim_history

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
    history = []
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            history.append({"role": "user", "content": msg["text"]})
            try:
                reply = await brain.think(history)
            except Exception as e:
                print("Error del cerebro:", repr(e))
                reply = "Mi señor, tuve un fallo interno. Intente de nuevo."
            history[:] = trim_history(history)
            await websocket.send_text(json.dumps({"say": reply}))
    except WebSocketDisconnect:
        pass

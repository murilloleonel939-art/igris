import os, json, hmac
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from core import Brain

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
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            try:
                reply = await session.say(msg["text"])
            except Exception as e:
                print("Error del cerebro:", repr(e))
                reply = "Mi señor, tuve un fallo interno. Intente de nuevo."
            await websocket.send_text(json.dumps({"say": reply}))
    except WebSocketDisconnect:
        pass

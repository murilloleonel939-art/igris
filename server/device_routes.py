"""Canal WebSocket del agente local Windows."""
from __future__ import annotations

import json
import os
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.local_agent import hub

router = APIRouter()


@router.get("/api/device/status")
async def device_status() -> dict:
    return hub.status()


@router.websocket("/api/device/ws")
async def device_ws(websocket: WebSocket) -> None:
    authorization = websocket.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    expected = os.getenv("NODE_TOKEN", "")
    if not expected or not secrets.compare_digest(token, expected):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            command = await hub.next_command()
            await websocket.send_json(command)
            raw = await websocket.receive_text()
            response = json.loads(raw)
            if response.get("id") == command.get("id") and isinstance(response.get("result"), dict):
                hub.complete(command["id"], response["result"])
    except (WebSocketDisconnect, json.JSONDecodeError):
        hub.disconnect()
    except Exception:
        hub.disconnect()
        raise

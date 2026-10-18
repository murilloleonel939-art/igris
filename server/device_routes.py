"""Canal WebSocket del agente local Windows."""
from __future__ import annotations

import json
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect

from core.local_agent import hub

router = APIRouter()


def _require_catalog_access(x_igris_key: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("IGRIS_ACCESS_KEY", "")
    node = os.getenv("NODE_TOKEN", "")
    provided = (x_igris_key or "").strip()
    bearer = (authorization or "").removeprefix("Bearer ").strip()
    if not ((expected and secrets.compare_digest(provided, expected)) or (node and secrets.compare_digest(bearer, node))):
        raise HTTPException(status_code=401, detail="No autorizado")


@router.get("/api/device/status")
async def device_status() -> dict:
    return hub.status()


@router.get("/api/device/programs", dependencies=[Depends(_require_catalog_access)])
async def device_programs(q: str = "") -> dict:
    query = q.strip().lower()
    programs = hub.programs if not query else [item for item in hub.programs if query in item.get("name", "").lower()]
    return {"programs": programs, "count": len(programs), "connected": hub.connected}


@router.post("/api/device/programs/sync", dependencies=[Depends(_require_catalog_access)])
async def sync_device_programs() -> dict:
    if not hub.connected:
        raise HTTPException(status_code=409, detail="El agente Windows no está conectado")
    result = await hub.enqueue("sync_programs")
    return result


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
        hello = json.loads(await websocket.receive_text())
        if hello.get("type") != "hello":
            await websocket.close(code=1008)
            return
        programs = hello.get("programs") if isinstance(hello.get("programs"), list) else []
        hub.update_programs(programs)
        await websocket.send_json({"type": "hello_ack", "agent_version": hello.get("agent_version", "unknown")})
        while True:
            command = await hub.next_command()
            await websocket.send_json(command)
            raw = await websocket.receive_text()
            response = json.loads(raw)
            if response.get("id") == command.get("id") and isinstance(response.get("result"), dict):
                result = response["result"]
                if command.get("action") == "sync_programs":
                    hub.update_programs(result.get("programs", []))
                hub.complete(command["id"], result)
    except (WebSocketDisconnect, json.JSONDecodeError):
        hub.disconnect()
    except Exception:
        hub.disconnect()
        raise

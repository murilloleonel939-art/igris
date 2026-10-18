"""Canal WebSocket del agente local Windows."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from core.database import AgentToken, SessionLocal, User
from core.local_agent import hub


class ProgramAccessUpdate(BaseModel):
    allowed_programs: list[str] = Field(default_factory=list, max_length=500)

router = APIRouter()


class AgentTokenCreate(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    user_id: int | None = None


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _require_catalog_access(
    request: Request,
    x_igris_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """Protege el catálogo con la misma validación que el resto del panel."""
    from server.main import require_key

    await require_key(request, x_igris_key, authorization)


@router.get("/api/device/status")
async def device_status() -> dict:
    return hub.status()


@router.get("/api/device/programs", dependencies=[Depends(_require_catalog_access)])
async def device_programs(q: str = "") -> dict:
    query = q.strip().lower()
    programs = hub.programs if not query else [item for item in hub.programs if query in item.get("name", "").lower()]
    return {"programs": programs, "count": len(programs), "connected": hub.connected}


@router.get("/api/device/programs/access", dependencies=[Depends(_require_catalog_access)])
async def device_program_access() -> dict:
    return {"allowed_programs": sorted(hub.allowed_programs)}


@router.put("/api/device/programs/access", dependencies=[Depends(_require_catalog_access)])
async def update_device_program_access(payload: ProgramAccessUpdate) -> dict:
    return {"allowed_programs": hub.set_allowed_programs(payload.allowed_programs)}


@router.post("/api/device/programs/sync", dependencies=[Depends(_require_catalog_access)])
async def sync_device_programs() -> dict:
    if not hub.connected:
        raise HTTPException(status_code=409, detail="El agente Windows no está conectado")
    result = await hub.enqueue("sync_programs")
    return result


@router.post("/api/device/tokens")
def create_agent_token(payload: AgentTokenCreate, _: None = Depends(_require_catalog_access)) -> dict:
    if payload.user_id is not None:
        with SessionLocal() as db:
            user = db.get(User, payload.user_id)
            if user is None or not user.is_active:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
    token = "igris_" + secrets.token_urlsafe(32)
    with SessionLocal() as db:
        row = AgentToken(token_hash=_token_digest(token), user_id=payload.user_id, device_name=payload.device_name.strip())
        db.add(row)
        db.commit()
    return {"token": token, "device_name": payload.device_name.strip(), "message": "Guarda este token; no volverá a mostrarse."}


@router.get("/api/device/tokens")
def list_agent_tokens(_: None = Depends(_require_catalog_access)) -> dict:
    with SessionLocal() as db:
        rows = db.query(AgentToken).order_by(AgentToken.created_at.desc()).all()
        return {"tokens": [{"id": row.id, "device_name": row.device_name, "user_id": row.user_id, "username": row.user.username if row.user else None, "revoked": row.revoked, "created_at": row.created_at.isoformat(), "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None} for row in rows]}


@router.post("/api/device/tokens/{token_id}/regenerate")
def regenerate_agent_token(token_id: int, _: None = Depends(_require_catalog_access)) -> dict:
    token = "igris_" + secrets.token_urlsafe(32)
    with SessionLocal() as db:
        row = db.get(AgentToken, token_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Agente no encontrado")
        row.token_hash = _token_digest(token)
        row.revoked = False
        db.commit()
        return {"token": token, "device_name": row.device_name, "message": "Guarda este token; no volverá a mostrarse."}


@router.delete("/api/device/tokens/{token_id}")
def delete_agent_token(token_id: int, _: None = Depends(_require_catalog_access)) -> dict:
    with SessionLocal() as db:
        row = db.get(AgentToken, token_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        db.delete(row)
        db.commit()
    if hub.owner_token_id == token_id:
        hub.disconnect()
    return {"ok": True}


@router.post("/api/device/tokens/{token_id}/revoke")
def revoke_agent_token(token_id: int, _: None = Depends(_require_catalog_access)) -> dict:
    with SessionLocal() as db:
        row = db.get(AgentToken, token_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Agente no encontrado")
        row.revoked = True
        db.commit()
    return {"ok": True}


@router.websocket("/api/device/ws")
async def device_ws(websocket: WebSocket) -> None:
    authorization = websocket.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    expected = os.getenv("NODE_TOKEN", "")
    agent_row = None
    if token.startswith("igris_"):
        with SessionLocal() as db:
            agent_row = db.query(AgentToken).filter(AgentToken.token_hash == _token_digest(token), AgentToken.revoked.is_(False)).first()
            if agent_row:
                agent_row.last_seen_at = _now()
                db.commit()
    valid_legacy = bool(expected and secrets.compare_digest(token, expected))
    if agent_row is None and not valid_legacy:
        await websocket.close(code=1008)
        return
    hub.owner_user_id = agent_row.user_id if agent_row is not None else None
    hub.owner_token_id = agent_row.id if agent_row is not None else None
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
            if agent_row is not None:
                with SessionLocal() as db:
                    current = db.get(AgentToken, agent_row.id)
                    if current is None or current.revoked:
                        await websocket.close(code=1008)
                        hub.disconnect()
                        return
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

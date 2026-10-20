"""Canal independiente para agentes Android TV Box."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from core.database import SessionLocal, TvBoxPairingCode, TvBoxToken, User

router = APIRouter()
_connections: dict[int, WebSocket] = {}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _require_catalog_access(
    request: Request,
    x_igris_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    from server.main import require_key
    await require_key(request, x_igris_key, authorization)


class PairingCodeCreate(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    user_id: int | None = None
    expires_minutes: int = Field(default=10, ge=1, le=30)


@router.post("/api/tvbox/pairing-codes", dependencies=[Depends(_require_catalog_access)])
def create_pairing_code(payload: PairingCodeCreate) -> dict[str, Any]:
    if payload.user_id is not None:
        with SessionLocal() as db:
            user = db.get(User, payload.user_id)
            if user is None or not user.is_active:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # Alfabeto sin caracteres ambiguos para escribirlo fácilmente en el TV Box.
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
    expires_at = _now() + timedelta(minutes=payload.expires_minutes)
    with SessionLocal() as db:
        db.query(TvBoxPairingCode).filter(
            TvBoxPairingCode.used.is_(False), TvBoxPairingCode.expires_at < _now()
        ).update({TvBoxPairingCode.used: True})
        db.add(TvBoxPairingCode(
            code_hash=_digest(code), user_id=payload.user_id,
            expires_at=expires_at,
        ))
        db.commit()
    return {"ok": True, "code": code, "device_name": payload.device_name.strip(), "expires_at": expires_at.isoformat()}


@router.get("/api/tvbox/status", dependencies=[Depends(_require_catalog_access)])
def tvbox_status() -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.query(TvBoxToken).order_by(TvBoxToken.created_at.desc()).all()
        return {"devices": [{
            "id": row.id, "device_name": row.device_name, "model": row.model,
            "android_version": row.android_version, "user_id": row.user_id,
            "revoked": row.revoked, "online": row.id in _connections,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        } for row in rows]}


@router.websocket("/api/tvbox/ws")
async def tvbox_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    token_row: TvBoxToken | None = None
    try:
        initial = json.loads(await websocket.receive_text())
        device = initial.get("device") if isinstance(initial.get("device"), dict) else {}
        token = ""
        with SessionLocal() as db:
            if initial.get("type") == "auth":
                token = str(initial.get("token", "")).strip()
                token_row = db.query(TvBoxToken).filter(
                    TvBoxToken.token_hash == _digest(token), TvBoxToken.revoked.is_(False)
                ).first()
                if token_row is None:
                    await websocket.send_json({"type": "error", "error": "Credencial inválida o revocada."})
                    await websocket.close(code=1008)
                    return
            elif initial.get("type") == "pair":
                code = str(initial.get("code", "")).strip().upper()
                if len(code) < 6:
                    await websocket.send_json({"type": "error", "error": "El código debe tener al menos 6 caracteres."})
                    await websocket.close(code=1008)
                    return
                pairing = db.query(TvBoxPairingCode).filter(
                    TvBoxPairingCode.code_hash == _digest(code),
                    TvBoxPairingCode.used.is_(False),
                    TvBoxPairingCode.expires_at > _now(),
                ).first()
                if pairing is None:
                    await websocket.send_json({"type": "error", "error": "Código inválido o expirado."})
                    await websocket.close(code=1008)
                    return
                token = "tvbox_" + secrets.token_urlsafe(32)
                token_row = TvBoxToken(
                    token_hash=_digest(token), user_id=pairing.user_id,
                    device_name=str(pairing.device_name or device.get("name") or "Android TV Box")[:120],
                    model=str(device.get("model") or "")[:120] or None,
                    android_version=str(device.get("android_version") or "")[:40] or None,
                )
                pairing.used = True
                db.add(token_row)
                db.commit()
                db.refresh(token_row)
            else:
                await websocket.close(code=1008)
                return
            token_row.last_seen_at = _now()
            db.commit()
        _connections[token_row.id] = websocket
        if initial.get("type") == "pair":
            await websocket.send_json({"type": "paired", "token": token, "device_id": token_row.id})
        else:
            await websocket.send_json({"type": "authenticated", "device_id": token_row.id})
        while True:
            message = json.loads(await websocket.receive_text())
            if message.get("type") == "heartbeat":
                with SessionLocal() as db:
                    row = db.get(TvBoxToken, token_row.id)
                    if row is not None:
                        row.last_seen_at = _now()
                        db.commit()
            elif message.get("type") == "hello":
                await websocket.send_json({"type": "hello_ack", "agent_version": message.get("agent_version", "unknown")})
    except (WebSocketDisconnect, json.JSONDecodeError):
        pass
    finally:
        if token_row is not None:
            _connections.pop(token_row.id, None)


class TvBoxCommand(BaseModel):
    action: str = Field(min_length=1, max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/tvbox/{device_id}/command", dependencies=[Depends(_require_catalog_access)])
async def send_tvbox_command(device_id: int, payload: TvBoxCommand) -> dict[str, Any]:
    websocket = _connections.get(device_id)
    if websocket is None:
        raise HTTPException(status_code=409, detail="El TV Box no está conectado")
    await websocket.send_json({"type": "command", "action": payload.action, **payload.params})
    return {"ok": True, "device_id": device_id}


@router.delete("/api/tvbox/{device_id}", dependencies=[Depends(_require_catalog_access)])
def delete_tvbox(device_id: int) -> dict[str, bool]:
    with SessionLocal() as db:
        row = db.get(TvBoxToken, device_id)
        if row is None:
            raise HTTPException(status_code=404, detail="TV Box no encontrado")
        db.delete(row)
        db.commit()
    _connections.pop(device_id, None)
    return {"ok": True}

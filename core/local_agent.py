"""Cola de órdenes para un agente local conectado por sondeo HTTPS."""
from __future__ import annotations

import asyncio
import contextvars
import secrets
import json
from typing import Any

_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("igris_agent_user_id", default=None)

from core.database import GlobalSetting, SessionLocal


class LocalAgentHub:
    def __init__(self) -> None:
        self._commands: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self.connected = False
        self.programs: list[dict[str, str]] = []
        self.owner_user_id: int | None = None
        self.owner_token_id: int | None = None

    async def enqueue(self, action: str, **params: Any) -> dict[str, Any]:
        requested_user = params.pop("user_id", None)
        if self.owner_user_id is not None and requested_user not in {None, self.owner_user_id}:
            return {"ok": False, "error": "El agente está vinculado a otro usuario."}
        command_id = secrets.token_urlsafe(18)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[command_id] = future
        await self._commands.put({"id": command_id, "action": action, "params": params})
        try:
            return await asyncio.wait_for(future, timeout=45)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "El computador no respondió. Comprueba que el agente esté iniciado."}
        finally:
            self._pending.pop(command_id, None)

    def update_programs(self, programs: list[dict[str, str]]) -> None:
        clean = []
        for item in programs[:500]:
            if isinstance(item, dict) and item.get("name") and item.get("path"):
                clean.append({"name": str(item["name"])[:120], "path": str(item["path"])[:1000]})
        self.programs = clean
        db = None
        try:
            db = SessionLocal()
            row = db.get(GlobalSetting, "windows.programs")
            encoded = json.dumps(clean, ensure_ascii=False)
            if row is None:
                db.add(GlobalSetting(key="windows.programs", value=encoded))
            else:
                row.value = encoded
            db.commit()
            db.close()
        except Exception:
            if db is not None:
                try:
                    db.rollback()
                    db.close()
                except Exception:
                    pass

    async def next_command(self) -> dict[str, Any]:
        self.connected = True
        return await self._commands.get()

    def complete(self, command_id: str, result: dict[str, Any]) -> bool:
        future = self._pending.get(command_id)
        if future is None or future.done():
            return False
        future.set_result(result)
        return True

    def disconnect(self) -> None:
        self.connected = False
        self.owner_user_id = None
        self.owner_token_id = None
        while not self._commands.empty():
            try:
                self._commands.get_nowait()
            except asyncio.QueueEmpty:
                break

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "queued": self._commands.qsize(),
            "programs": self.programs,
            "program_count": len(self.programs),
        }

    def restore_programs(self) -> None:
        db = None
        try:
            db = SessionLocal()
            row = db.get(GlobalSetting, "windows.programs")
            if row:
                saved = json.loads(row.value)
                if isinstance(saved, list):
                    self.programs = saved
            db.close()
        except Exception:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


hub = LocalAgentHub()
hub.restore_programs()


def set_agent_user(user_id: int | None):
    return _current_user_id.set(user_id)


def reset_agent_user(token) -> None:
    _current_user_id.reset(token)


async def run_local_action(action: str, **params: Any) -> dict[str, Any]:
    return await hub.enqueue(action, user_id=_current_user_id.get(), **params)

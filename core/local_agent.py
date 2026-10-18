"""Cola de órdenes para un agente local conectado por sondeo HTTPS."""
from __future__ import annotations

import asyncio
import secrets
from typing import Any


class LocalAgentHub:
    def __init__(self) -> None:
        self._commands: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self.connected = False

    async def enqueue(self, action: str, **params: Any) -> dict[str, Any]:
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
        while not self._commands.empty():
            try:
                self._commands.get_nowait()
            except asyncio.QueueEmpty:
                break

    def status(self) -> dict[str, Any]:
        return {"connected": self.connected, "queued": self._commands.qsize()}


hub = LocalAgentHub()


async def run_local_action(action: str, **params: Any) -> dict[str, Any]:
    return await hub.enqueue(action, **params)

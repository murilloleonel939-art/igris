"""Cola de órdenes para un agente local conectado por sondeo HTTPS."""
from __future__ import annotations

import asyncio
import contextvars
import secrets
import json
from typing import Any

_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("igris_agent_user_id", default=None)

from core.database import GlobalSetting, SessionLocal

FIXED_PROGRAM_NAMES = {
    "excel", "word", "powerpoint", "chrome", "firefox", "microsoft edge",
    "calculadora", "bloc de notas", "notepad", "steam", "windows powershell",
    "telegram", "whatsapp", "spotify", "google drive", "one drive", "onedrive",
}


class LocalAgentHub:
    def __init__(self) -> None:
        self._commands: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._command_websockets: dict[str, Any] = {}
        self._command_actions: dict[str, str] = {}
        self.connected = False
        self.programs: list[dict[str, str]] = []
        self.owner_user_id: int | None = None
        self.owner_token_id: int | None = None
        self.active_websocket = None
        self.allowed_programs: set[str] = set()

    async def enqueue(self, action: str, **params: Any) -> dict[str, Any]:
        requested_user = params.pop("user_id", None)
        if not self.connected or self.active_websocket is None:
            return {"ok": False, "error": "El agente local no está conectado."}
        if action == "launch_program":
            program = str(params.get("program", "")).strip().lower()
            allowed = {name.lower() for name in self.allowed_programs}
            aliases = {"edge": "microsoft edge", "powerpoint": "powerpoint", "onedrive": "onedrive", "calculator": "calculator", "notepad": "notepad"}
            if program not in allowed and aliases.get(program, program) not in allowed:
                return {"ok": False, "error": "La aplicación no está autorizada en la configuración del equipo."}
        if action == "create_document" and requested_user is None:
            return {"ok": False, "error": "No se pudo identificar al usuario para crear el documento."}
        if action == "create_document" and self.owner_user_id is None:
            return {"ok": False, "error": "El agente no está vinculado a un usuario."}
        if self.owner_user_id is not None and requested_user != self.owner_user_id:
            return {"ok": False, "error": "El agente está vinculado a otro usuario."}
        if self.active_websocket is None:
            return {"ok": False, "error": "El agente local no está conectado."}
        command_id = secrets.token_urlsafe(18)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[command_id] = future
        websocket = self.active_websocket
        self._command_websockets[command_id] = websocket
        self._command_actions[command_id] = action
        await self._commands.put({"id": command_id, "action": action, "params": params})
        try:
            return await asyncio.wait_for(future, timeout=45)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "El computador no respondió. Comprueba que el agente esté iniciado."}
        finally:
            self._pending.pop(command_id, None)
            self._command_websockets.pop(command_id, None)
            self._command_actions.pop(command_id, None)

    def update_programs(self, programs: list[dict[str, str]]) -> None:
        clean = []
        for item in programs[:500]:
            if isinstance(item, dict) and item.get("name") and item.get("path"):
                clean.append({"name": str(item["name"])[:120], "path": str(item["path"])[:1000]})
        self.programs = clean
        # La lista autorizable es fija y no depende del catálogo detectado.
        # Nunca eliminar permisos guardados porque el agente reporte otro catálogo.
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

    def set_allowed_programs(self, names: list[str]) -> list[str]:
        self.allowed_programs = {str(name) for name in names if str(name).strip().lower() in FIXED_PROGRAM_NAMES}
        db = None
        try:
            db = SessionLocal()
            row = db.get(GlobalSetting, "windows.allowed_programs")
            value = json.dumps(sorted(self.allowed_programs), ensure_ascii=False)
            if row is None:
                db.add(GlobalSetting(key="windows.allowed_programs", value=value))
            else:
                row.value = value
            db.commit()
        finally:
            if db is not None:
                db.close()
        return sorted(self.allowed_programs)

    async def next_command(self, websocket=None) -> dict[str, Any]:
        if websocket is not None and websocket is not self.active_websocket:
            raise RuntimeError("El agente ya no es la conexión activa")
        return await self._commands.get()

    def complete(self, command_id: str, result: dict[str, Any], websocket=None) -> bool:
        future = self._pending.get(command_id)
        expected_websocket = self._command_websockets.get(command_id)
        if websocket is not None and websocket is not expected_websocket:
            return False
        if future is None or future.done():
            return False
        future.set_result(result)
        return True

    def disconnect(self, websocket=None) -> None:
        if websocket is not None and websocket is not self.active_websocket:
            return
        disconnected_websocket = self.active_websocket
        self.connected = False
        self.owner_user_id = None
        self.owner_token_id = None
        self.active_websocket = None
        retained_commands = []
        while not self._commands.empty():
            try:
                command = self._commands.get_nowait()
            except asyncio.QueueEmpty:
                break
            command_id = command.get("id")
            if self._command_websockets.get(command_id) is not disconnected_websocket:
                retained_commands.append(command)
                continue
            future = self._pending.get(command_id)
            if future is not None and not future.done():
                action = self._command_actions.get(command_id, command.get("action"))
                message = (
                    "El agente se desconectó antes de crear el documento."
                    if action == "create_document"
                    else "El agente se desconectó antes de completar la acción."
                )
                future.set_result({"ok": False, "error": message})
        for command in retained_commands:
            self._commands.put_nowait(command)
        for command_id, future in list(self._pending.items()):
            if (
                self._command_websockets.get(command_id) is disconnected_websocket
                and not future.done()
            ):
                message = (
                    "El agente se desconectó antes de crear el documento."
                    if self._command_actions.get(command_id) == "create_document"
                    else "El agente se desconectó antes de completar la acción."
                )
                future.set_result({"ok": False, "error": message})

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
            permissions = db.get(GlobalSetting, "windows.allowed_programs")
            if permissions:
                saved_permissions = json.loads(permissions.value)
                if isinstance(saved_permissions, list):
                    self.allowed_programs = {str(name) for name in saved_permissions if str(name).strip().lower() in FIXED_PROGRAM_NAMES}
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

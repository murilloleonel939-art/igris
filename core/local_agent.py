"""Cola de órdenes para los agentes Windows conectados por WebSocket.

Cada equipo abre su propia conexión y tiene su propia cola: una orden para el
PC de Ana nunca puede terminar en el PC de Luis. El hub indexa las conexiones
por token de equipo y elige a cuál enviar según el usuario de la conversación.

El token es la identidad del equipo, no del usuario: dos equipos pueden estar
vinculados a la misma cuenta y un equipo sin vincular solo puede abrir
aplicaciones, nunca crear archivos.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import secrets
from typing import Any

_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("igris_agent_user_id", default=None)

from core.database import GlobalSetting, SessionLocal

FIXED_PROGRAM_NAMES = {
    "excel", "word", "powerpoint", "chrome", "firefox", "microsoft edge",
    "calculadora", "bloc de notas", "notepad", "steam", "windows powershell",
    "telegram", "whatsapp", "spotify", "google drive", "one drive", "onedrive",
}

LEGACY_KEY = "legacy"


def _key_for(token_id: int | None) -> str:
    return LEGACY_KEY if token_id is None else f"token:{token_id}"


class AgentConnection:
    """Una conexión WebSocket con un equipo concreto, con su propia cola."""

    def __init__(self, token_id: int | None, user_id: int | None, websocket: Any) -> None:
        self.token_id = token_id
        self.user_id = user_id
        self.websocket = websocket
        self.key = _key_for(token_id)
        self.programs: list[dict[str, str]] = []
        self.connected = True
        self._commands: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._command_actions: dict[str, str] = {}

    async def enqueue(self, action: str, **params: Any) -> dict[str, Any]:
        if not self.connected or self.websocket is None:
            return {"ok": False, "error": "El equipo se desconectó antes de ejecutar la orden."}
        command_id = secrets.token_urlsafe(18)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[command_id] = future
        self._command_actions[command_id] = action
        await self._commands.put({"id": command_id, "action": action, "params": params})
        try:
            return await asyncio.wait_for(future, timeout=45)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "El computador no respondió. Comprueba que el agente esté iniciado."}
        finally:
            self._pending.pop(command_id, None)
            self._command_actions.pop(command_id, None)

    async def next_command(self) -> dict[str, Any]:
        if not self.connected:
            raise RuntimeError("El agente ya no está conectado")
        return await self._commands.get()

    def complete(self, command_id: str, result: dict[str, Any]) -> bool:
        future = self._pending.get(command_id)
        if future is None or future.done():
            return False
        future.set_result(result)
        return True

    def close(self) -> None:
        """Cierra la conexión y libera las órdenes que quedaran en curso."""
        if not self.connected:
            return
        self.connected = False
        while not self._commands.empty():
            try:
                self._commands.get_nowait()
            except asyncio.QueueEmpty:
                break
        for command_id, future in list(self._pending.items()):
            if future.done():
                continue
            action = self._command_actions.get(command_id)
            message = (
                "El agente se desconectó antes de crear el documento."
                if action == "create_document"
                else "El agente se desconectó antes de completar la acción."
            )
            future.set_result({"ok": False, "error": message})
        self._pending.clear()
        self._command_actions.clear()


class LocalAgentHub:
    def __init__(self) -> None:
        self._agents: dict[str, AgentConnection] = {}
        self.allowed_programs: set[str] = set()

    # ---------- estado ----------
    @property
    def connected(self) -> bool:
        """True si hay al menos un equipo conectado."""
        return any(agent.connected for agent in self._agents.values())

    @property
    def programs(self) -> list[dict[str, str]]:
        """Catálogo visto por los equipos conectados (sin duplicados por nombre)."""
        merged: dict[str, dict[str, str]] = {}
        for agent in self._agents.values():
            for item in agent.programs:
                merged.setdefault(item["name"].lower(), item)
        return list(merged.values())

    def live_agents(self) -> list[AgentConnection]:
        return [agent for agent in self._agents.values() if agent.connected]

    def connection_for_token(self, token_id: int | None) -> AgentConnection | None:
        return self._agents.get(_key_for(token_id))

    def connection_for_user(self, user_id: int | None) -> AgentConnection | None:
        """Equipo de ese usuario; si tiene varios, el último que conectó."""
        if user_id is None:
            return None
        matches = [agent for agent in self.live_agents() if agent.user_id == user_id]
        return matches[-1] if matches else None

    def status(self) -> dict[str, Any]:
        agents = self.live_agents()
        return {
            "connected": self.connected,
            "devices": [
                {
                    "token_id": agent.token_id,
                    "user_id": agent.user_id,
                    "program_count": len(agent.programs),
                }
                for agent in agents
            ],
            "device_count": len(agents),
            "queued": sum(agent._commands.qsize() for agent in agents),
            "programs": self.programs,
            "program_count": len(self.programs),
        }

    # ---------- registro de conexiones ----------
    def register(self, token_id: int | None, user_id: int | None, websocket: Any) -> AgentConnection:
        """Registra un equipo. Si ya estaba conectado con el mismo token, lo reemplaza."""
        previous = self._agents.get(_key_for(token_id))
        if previous is not None:
            previous.close()
        agent = AgentConnection(token_id, user_id, websocket)
        self._agents[agent.key] = agent
        return agent

    def drop(self, agent: AgentConnection) -> None:
        """Quita la conexión solo si sigue siendo la vigente para ese token."""
        if self._agents.get(agent.key) is agent:
            del self._agents[agent.key]
        agent.close()

    def set_connection_user(self, token_id: int, user_id: int | None) -> bool:
        """Cambia el dueño de un equipo conectado sin reconectar ni regenerar token."""
        agent = self.connection_for_token(token_id)
        if agent is None:
            return False
        agent.user_id = user_id
        return True

    # ---------- envío de órdenes ----------
    def resolve(self, user_id: int | None) -> tuple[AgentConnection | None, str | None]:
        """Elige el equipo que debe ejecutar la orden.

        Con usuario, solo se acepta un equipo suyo. Sin usuario (panel con clave
        maestra) se exige que haya exactamente uno para no adivinar el destino.
        """
        live = self.live_agents()
        if user_id is not None:
            agent = self.connection_for_user(user_id)
            if agent is not None:
                return agent, None
            if not live:
                return None, (
                    "El computador no está conectado. Inicia IGRIS Windows Agent "
                    "en tu PC y vuelve a intentarlo."
                )
            return None, (
                "Ninguno de los equipos conectados está vinculado a tu cuenta. "
                "Vincúlalo en Panel admin → Conexiones → Tokens por equipo."
            )
        if not live:
            return None, "El agente local no está conectado."
        if len(live) > 1:
            return None, (
                "Hay varios equipos conectados. Indica el usuario desde cuya cuenta "
                "se debe ejecutar la orden."
            )
        return live[0], None

    async def enqueue(self, action: str, **params: Any) -> dict[str, Any]:
        requested_user = params.pop("user_id", None)
        agent, error = self.resolve(requested_user)
        if agent is None:
            return {"ok": False, "error": error}
        if action == "launch_program":
            program = str(params.get("program", "")).strip().lower()
            allowed = {name.lower() for name in self.allowed_programs}
            aliases = {
                "edge": "microsoft edge", "powerpoint": "powerpoint",
                "onedrive": "onedrive", "calculator": "calculadora",
                "notepad": "notepad",
            }
            if program not in allowed and aliases.get(program, program) not in allowed:
                return {"ok": False, "error": "La aplicación no está autorizada en la configuración del equipo."}
        if action == "create_document":
            if requested_user is None:
                return {"ok": False, "error": "No se pudo identificar al usuario para crear el archivo."}
            if agent.user_id is None:
                return {"ok": False, "error": "El equipo no está vinculado a un usuario."}
            if agent.user_id != requested_user:
                return {"ok": False, "error": "El equipo está vinculado a otro usuario."}
        return await agent.enqueue(action, **params)

    async def sync_programs(self) -> dict[str, Any]:
        """Pide a cada equipo conectado su catálogo de aplicaciones."""
        agents = self.live_agents()
        if not agents:
            return {"ok": False, "error": "El agente Windows no está conectado"}
        results = await asyncio.gather(
            *(agent.enqueue("sync_programs") for agent in agents), return_exceptions=True
        )
        ok = False
        for agent, result in zip(agents, results):
            if isinstance(result, Exception) or not isinstance(result, dict):
                continue
            programs = result.get("programs", [])
            if result.get("ok") and isinstance(programs, list):
                self._store_programs(agent, programs)
                ok = True
        return {"ok": ok, "devices": len(agents)}

    # ---------- catálogo y permisos ----------
    def _store_programs(self, agent: AgentConnection | None, programs: list) -> None:
        clean = []
        for item in programs[:500]:
            if isinstance(item, dict) and item.get("name") and item.get("path"):
                clean.append({"name": str(item["name"])[:120], "path": str(item["path"])[:1000]})
        if agent is not None:
            agent.programs = clean
        self._persist_programs(clean)

    def _persist_programs(self, clean: list[dict[str, str]]) -> None:
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
        except Exception:
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    def update_programs(self, programs: list[dict[str, str]], agent: AgentConnection | None = None) -> None:
        self._store_programs(agent, programs)

    def set_allowed_programs(self, names: list[str]) -> list[str]:
        self.allowed_programs = {
            str(name) for name in names if str(name).strip().lower() in FIXED_PROGRAM_NAMES
        }
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

    def restore_programs(self) -> None:
        db = None
        try:
            db = SessionLocal()
            row = db.get(GlobalSetting, "windows.programs")
            if row:
                saved = json.loads(row.value)
                if isinstance(saved, list):
                    self._cache_programs = saved
            permissions = db.get(GlobalSetting, "windows.allowed_programs")
            if permissions:
                saved_permissions = json.loads(permissions.value)
                if isinstance(saved_permissions, list):
                    self.allowed_programs = {
                        str(name) for name in saved_permissions
                        if str(name).strip().lower() in FIXED_PROGRAM_NAMES
                    }
        except Exception:
            pass
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    def cached_programs(self) -> list[dict[str, str]]:
        """Catálogo guardado, útil cuando no hay ningún equipo conectado."""
        live = self.programs
        if live:
            return live
        return list(getattr(self, "_cache_programs", []) or [])


hub = LocalAgentHub()
hub.restore_programs()


def set_agent_user(user_id: int | None):
    return _current_user_id.set(user_id)


def reset_agent_user(token) -> None:
    _current_user_id.reset(token)


async def run_local_action(action: str, **params: Any) -> dict[str, Any]:
    return await hub.enqueue(action, user_id=_current_user_id.get(), **params)

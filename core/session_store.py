"""Almacén de sesiones de conversación de IGRIS (en memoria).

Cada clave (por ejemplo "web:<id>" o "tg:<id de Telegram>") conserva su
BrainSession, y con ella el historial de la conversación.

- Las sesiones expiran tras TTL segundos sin uso.
- Hay un máximo de sesiones; al llenarse se descartan las menos recientes.
- Viven en memoria: se pierden al reiniciar o redesplegar el backend.
  (Funciona con un solo worker de Uvicorn, igual que el límite de intentos de la clave.)
"""

import time
from collections import OrderedDict
from typing import Optional


class SessionStore:
    def __init__(self, brain, ttl: int = 7200, max_sessions: int = 200):
        self.brain = brain
        self.ttl = ttl
        self.max_sessions = max_sessions
        # Ordenado por último uso: el primero es el menos reciente.
        self._sessions: "OrderedDict[str, tuple]" = OrderedDict()

    def _purge(self) -> None:
        now = time.monotonic()
        while self._sessions:
            key, (last_used, _) = next(iter(self._sessions.items()))
            if now - last_used <= self.ttl:
                break
            del self._sessions[key]

    def get(self, key: Optional[str]):
        """Devuelve la sesión de esa clave (la crea si no existe).

        Sin clave devuelve una sesión efímera: comportamiento anterior (sin memoria).
        """
        if not key:
            return self.brain.new_session()

        self._purge()
        entry = self._sessions.pop(key, None)
        session = entry[1] if entry else self.brain.new_session()
        self._sessions[key] = (time.monotonic(), session)  # queda como la más reciente

        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)
        return session

    def reset(self, key: str) -> None:
        """Olvida la conversación de esa clave."""
        self._sessions.pop(key, None)

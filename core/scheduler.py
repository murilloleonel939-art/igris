"""Planificador de recordatorios de IGRIS.

Una tarea en segundo plano revisa cada POLL_SECONDS los recordatorios vencidos y envía el
aviso por Telegram. No importa nada de main.py: recibe la función de envío.

Garantías:
- Sin duplicados: cada recordatorio se "reclama" con un UPDATE condicional atómico
  (solo uno gana, aunque hubiera dos procesos) ANTES de enviar. Si el envío falla, se libera
  y se reintenta en el siguiente ciclo. Contrapartida: si el servidor muriera justo entre
  reclamar y enviar, ese aviso se perdería (preferimos eso a avisar dos veces).
- Recuperación: la condición es "due_at <= ahora", así que lo vencido durante una caída se
  envía al arrancar (con una nota de retraso si pasaron más de LATE_NOTICE).
- Resistente: cualquier error se registra y el ciclo continúa.
- Repetición: los diarios/semanales avanzan su fecha (saltando las ocurrencias perdidas).
- No se escribe el texto del recordatorio en los logs, solo su id.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Iterable, Optional

from sqlalchemy import update

from core import database
from core.database import Reminder, utcnow
from core.tools._common import format_local
from core.tools.reminders import REPEATS

logger = logging.getLogger(__name__)

POLL_SECONDS = 30
BATCH = 20                           # máximo de avisos por ciclo
SEND_TIMEOUT = 20                    # segundos por envío
LATE_NOTICE = timedelta(minutes=10)  # a partir de aquí el aviso menciona el retraso


# ----------------------------- lógica pura -----------------------------
def next_due(old_due: datetime, repeat: str, now: datetime) -> datetime:
    """Siguiente ocurrencia estrictamente posterior a 'now' (salta las perdidas)."""
    step = REPEATS[repeat]
    n = (now - old_due) // step + 1
    return old_due + step * max(n, 1)


def build_message(text: str, due_at: datetime, now: datetime) -> str:
    text = text.strip().rstrip(".")
    if now - due_at > LATE_NOTICE:
        return f"Mi señor, le recuerdo con retraso: {text}. Estaba previsto para {format_local(due_at)}."
    return f"Mi señor, le recuerdo: {text}."


# ----------------------------- acceso a BD (síncrono) -----------------------------
def _claim_due(now: datetime) -> list:
    """Reclama (atómicamente) los recordatorios vencidos y los devuelve como dicts."""
    claims = []
    with database.SessionLocal() as db:
        rows = (
            db.query(Reminder)
            .filter(Reminder.status == "pendiente", Reminder.due_at <= now)
            .order_by(Reminder.due_at)
            .limit(BATCH)
            .all()
        )
        for r in rows:
            old_due, repeat = r.due_at, r.repeat
            if repeat in REPEATS:
                new_due = next_due(old_due, repeat, now)
                values = {"due_at": new_due}
            else:
                new_due = None
                values = {"status": "enviado", "sent_at": now}
            res = db.execute(
                update(Reminder)
                .where(Reminder.id == r.id, Reminder.status == "pendiente", Reminder.due_at == old_due)
                .values(**values)
            )
            db.commit()
            if res.rowcount == 1:  # solo si ganamos la reclamación
                claims.append({
                    "id": r.id, "text": r.text, "chat_id": r.chat_id,
                    "old_due": old_due, "new_due": new_due, "attempts": r.attempts or 0,
                })
    return claims


def _confirm(claim: dict) -> None:
    """Envío correcto: reinicia el contador de fallos."""
    if not claim["attempts"]:
        return
    with database.SessionLocal() as db:
        db.execute(update(Reminder).where(Reminder.id == claim["id"]).values(attempts=0))
        db.commit()


def _release(claim: dict) -> None:
    """Envío fallido: devuelve el recordatorio a pendiente para reintentarlo."""
    with database.SessionLocal() as db:
        if claim["new_due"] is None:
            cond = (Reminder.id == claim["id"], Reminder.status == "enviado")
            values = {"status": "pendiente", "sent_at": None}
        else:
            cond = (Reminder.id == claim["id"], Reminder.status == "pendiente",
                    Reminder.due_at == claim["new_due"])
            values = {"due_at": claim["old_due"]}
        db.execute(
            update(Reminder).where(*cond).values(attempts=Reminder.attempts + 1, **values)
        )
        db.commit()


# ----------------------------- envío y ciclo -----------------------------
SendFn = Callable[[int, str], Awaitable[None]]


async def _deliver(send: SendFn, claim: dict, targets: list, message: str) -> bool:
    """True si el aviso llegó al menos a un destino (así un fallo parcial no duplica avisos)."""
    delivered = 0
    for chat_id in targets:
        try:
            await asyncio.wait_for(send(chat_id, message), timeout=SEND_TIMEOUT)
            delivered += 1
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Aviso del recordatorio {claim['id']} no llegó a un destino: {type(e).__name__}")
    return delivered > 0


async def process_due(send: SendFn, default_chat_ids: Iterable[int], now: Optional[datetime] = None) -> int:
    """Un ciclo: reclama lo vencido y lo envía. Devuelve cuántos avisos se enviaron."""
    now = now or utcnow()
    claims = await asyncio.to_thread(_claim_due, now)
    sent = 0
    for claim in claims:
        targets = [claim["chat_id"]] if claim["chat_id"] else sorted(default_chat_ids)
        message = build_message(claim["text"], claim["old_due"], now)
        if targets and await _deliver(send, claim, targets, message):
            await asyncio.to_thread(_confirm, claim)
            sent += 1
            logger.info(f"Recordatorio {claim['id']} enviado")
        else:
            if not targets:
                logger.error(f"Recordatorio {claim['id']}: no hay a quién avisar (ALLOWED_TELEGRAM_IDS vacío)")
            await asyncio.to_thread(_release, claim)
            logger.warning(f"Recordatorio {claim['id']} devuelto a pendiente; se reintentará")
    return sent


async def run_reminder_loop(send: SendFn, default_chat_ids: Iterable[int], poll: float = POLL_SECONDS) -> None:
    """Bucle infinito del planificador (se lanza con asyncio.create_task en el startup)."""
    logger.info(f"Planificador de recordatorios iniciado (cada {poll:g} s)")
    while True:
        try:
            await process_due(send, default_chat_ids)
        except asyncio.CancelledError:
            logger.info("Planificador de recordatorios detenido")
            raise
        except Exception:
            logger.exception("Error en el ciclo de recordatorios; se reintenta")
        await asyncio.sleep(poll)

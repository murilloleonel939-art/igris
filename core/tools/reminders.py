"""Recordatorios de IGRIS: crear, listar y cancelar.

Los avisos los envía el planificador (core/scheduler.py) por Telegram.
Fechas: el usuario habla en hora de Colombia; en la base de datos se guarda UTC.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from core import database
from core.database import Reminder
from core.tools._common import (
    THIRD_PARTY_NOTICE, TZ, check_delete, format_local, local_to_utc, register_delete,
)

logger = logging.getLogger(__name__)

MAX_PENDING = 100   # tope de recordatorios pendientes
MAX_LISTED = 10     # cuántos se listan (para decirlos en voz alta)
REPEATS = {"diaria": timedelta(days=1), "semanal": timedelta(days=7)}
_NO_REPEAT = {"", "ninguna", "ninguno", "no", "una vez", "none", "null"}
_TIME_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S")


def _parse_when(when) -> Optional[datetime]:
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(str(when).strip(), fmt).replace(tzinfo=TZ)
        except ValueError:
            continue
    return None


def _normalize_repeat(repeat) -> tuple:
    """(valor, error). valor es None, 'diaria' o 'semanal'."""
    r = (str(repeat).strip().lower() if repeat is not None else "")
    if r in _NO_REPEAT:
        return None, None
    if r in REPEATS:
        return r, None
    return None, "La repetición solo puede ser 'diaria' o 'semanal'"


async def create_reminder(text: str, when: str, repeat: Optional[str] = None, _session=None) -> dict:
    """Crea un recordatorio. 'when' en hora de Colombia, formato AAAA-MM-DDTHH:MM."""
    text = (text or "").strip()[:200]
    if not text:
        return {"error": "Falta el texto del recordatorio"}

    local = _parse_when(when)
    if local is None:
        return {"error": "Fecha u hora inválida. Formato esperado: AAAA-MM-DDTHH:MM (hora de Colombia)"}
    if local < datetime.now(TZ) - timedelta(minutes=1):
        return {"error": "Esa fecha y hora ya pasaron"}

    rep, err = _normalize_repeat(repeat)
    if err:
        return {"error": err}

    due_utc = local_to_utc(local)
    # Si se pidió desde Telegram, el aviso va a ese chat; desde la web, a todos los autorizados.
    chat_id = getattr(_session, "telegram_id", None)

    def _save():
        with database.SessionLocal() as db:
            pending = db.query(Reminder).filter(Reminder.status == "pendiente").count()
            if pending >= MAX_PENDING:
                return None
            r = Reminder(text=text, due_at=due_utc, status="pendiente",
                         channel="telegram", chat_id=chat_id, repeat=rep)
            db.add(r)
            db.commit()
            return r.id

    new_id = await asyncio.to_thread(_save)
    if new_id is None:
        return {"error": f"Ya hay {MAX_PENDING} recordatorios pendientes; hay que cancelar alguno"}

    logger.info(f"Recordatorio {new_id} creado (repite={rep}, chat={'telegram' if chat_id else 'todos'})")
    return {
        "estado": "creado",
        "id": new_id,
        "texto": text,
        "aviso_el": format_local(due_utc),
        "repite": rep,
        "canal": "El aviso llegará por Telegram.",
    }


async def list_reminders() -> dict:
    """Recordatorios pendientes, del más próximo al más lejano."""

    def _load():
        with database.SessionLocal() as db:
            q = db.query(Reminder).filter(Reminder.status == "pendiente")
            total = q.count()
            rows = q.order_by(Reminder.due_at).limit(MAX_LISTED).all()
            return total, [(r.id, r.text, r.due_at, r.repeat) for r in rows]

    total, rows = await asyncio.to_thread(_load)
    if not total:
        return {"total": 0, "mensaje": "No hay recordatorios pendientes"}
    return {
        "total": total,
        "mostrados": len(rows),
        "recordatorios": [
            {"id": rid, "texto": text, "cuando": format_local(due), "repite": rep}
            for rid, text, due, rep in rows
        ],
        "aviso": THIRD_PARTY_NOTICE,
    }


async def delete_reminder(id: int, _session=None) -> dict:
    """Cancela UN recordatorio pendiente por su id (no se borra la fila: queda 'cancelado')."""
    blocked = check_delete(_session)
    if blocked:
        return blocked
    try:
        rid = int(id)
    except (TypeError, ValueError):
        return {"error": "El id del recordatorio debe ser un número"}

    def _cancel():
        with database.SessionLocal() as db:
            r = db.query(Reminder).filter(Reminder.id == rid, Reminder.status == "pendiente").first()
            if r is None:
                return None
            text, due = r.text, r.due_at
            r.status = "cancelado"
            db.commit()
            return text, due

    res = await asyncio.to_thread(_cancel)
    if res is None:
        return {"error": "No hay un recordatorio pendiente con ese número. Revisa la lista con list_reminders"}
    register_delete(_session)
    text, due = res
    logger.info(f"Recordatorio {rid} cancelado")
    return {"estado": "cancelado", "id": rid, "texto": text, "era_para": format_local(due)}

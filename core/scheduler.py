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
from core.database import Reminder, TelegramLink, utcnow
from core.tools._common import format_local
from core.tools.reminders import MONTHLY, REPEATS

logger = logging.getLogger(__name__)

POLL_SECONDS = 30
BATCH = 20                           # máximo de avisos por ciclo
SEND_TIMEOUT = 20                    # segundos por envío
LATE_NOTICE = timedelta(minutes=10)  # a partir de aquí el aviso menciona el retraso


# ----------------------------- lógica pura -----------------------------
def _add_months(dt: datetime, months: int) -> datetime:
    """Suma meses a una fecha; si el día no existe en el mes destino, usa el último."""
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    # datetime no acepta día 31 en un mes de 30: se recorta al último válido.
    day = dt.day
    while day > 28:
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return dt.replace(year=year, month=month, day=day)


def next_due(old_due: datetime, repeat: str, now: datetime) -> datetime:
    """Siguiente ocurrencia estrictamente posterior a 'now' (salta las perdidas)."""
    if repeat == MONTHLY:
        candidate = _add_months(old_due, 1)
        while candidate <= now:
            candidate = _add_months(candidate, 1)
        return candidate
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
    """Reclama (atómicamente) los recordatorios vencidos y los devuelve como dicts.

    Se saltan los de usuarios que todavía NO han vinculado su Telegram: no hay a
    quién avisar y su texto es privado, así que se quedan pendientes sin gastar
    ciclos. En cuanto el usuario vincule, la siguiente consulta ya los ve y salen.
    """
    claims = []
    with database.SessionLocal() as db:
        linked_ids = {
            link.user_id
            for link in db.query(TelegramLink).filter(TelegramLink.chat_id.isnot(None)).all()
        }
        # Un recordatorio es "entregable" si:
        #   - ya lleva chat guardado (se creó desde ese mismo Telegram), o
        #   - su usuario tiene un chat vinculado, o
        #   - no tiene usuario (fila antigua, de antes de los permisos): entonces
        #     se avisa a los chats autorizados de la instalación, como siempre.
        # Los de WhatsApp no dependen de Telegram: el número sale de Conexiones,
        # así que son entregables aunque el usuario no haya vinculado nada.
        entregable = (
            Reminder.chat_id.isnot(None)
            | Reminder.user_id.is_(None)
            | (Reminder.channel == "whatsapp")
        )
        if linked_ids:
            entregable = entregable | Reminder.user_id.in_(linked_ids)

        rows = (
            db.query(Reminder)
            .filter(Reminder.status == "pendiente", Reminder.due_at <= now, entregable)
            .order_by(Reminder.due_at)
            .limit(BATCH)
            .all()
        )
        for r in rows:
            old_due, repeat = r.due_at, r.repeat
            if repeat in REPEATS or repeat == MONTHLY:
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
                    "user_id": r.user_id, "channel": r.channel or "telegram",
                    "old_due": old_due, "new_due": new_due, "attempts": r.attempts or 0,
                })
    return claims


def _linked_chats() -> dict:
    """{user_id: chat_id} de los Telegram vinculados.

    Se consulta en cada ciclo: así un usuario que vincula su Telegram DESPUÉS de
    crear el recordatorio recibe igualmente el aviso.
    """
    from core.database import TelegramLink

    with database.SessionLocal() as db:
        rows = db.query(TelegramLink).filter(TelegramLink.chat_id.isnot(None)).all()
        return {link.user_id: link.chat_id for link in rows}


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
WhatsAppFn = Callable[[str], Awaitable[None]]


async def _configured_whatsapp_destination() -> str:
    """Número de WhatsApp guardado en Conexiones (sin '+'), o '' si no hay."""
    from core.settings_manager import get_settings

    def _read() -> str:
        phone = (get_settings().get_whatsapp_config().get("phone_number") or "").strip()
        return phone.lstrip("+").strip()

    try:
        return await asyncio.to_thread(_read)
    except Exception as e:
        logger.warning("No se pudo leer el número de WhatsApp configurado: %s", e)
        return ""


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


async def process_due(
    send: SendFn,
    default_chat_ids: Iterable[int],
    now: Optional[datetime] = None,
    send_whatsapp: Optional[WhatsAppFn] = None,
) -> int:
    """Un ciclo: reclama lo vencido y lo envía. Devuelve cuántos avisos se enviaron."""
    now = now or utcnow()
    claims = await asyncio.to_thread(_claim_due, now)
    linked = await asyncio.to_thread(_linked_chats) if claims else {}
    whatsapp_to = ""
    if claims and any(c.get("channel") == "whatsapp" for c in claims):
        whatsapp_to = await _configured_whatsapp_destination()
    sent = 0
    for claim in claims:
        message = build_message(claim["text"], claim["old_due"], now)

        if claim.get("channel") == "whatsapp":
            if send_whatsapp is None or not whatsapp_to:
                # Sin canal de WhatsApp disponible (o sin número en Conexiones) el
                # aviso se queda pendiente y se reintenta: no se pierde.
                if claim["attempts"] % 20 == 0:
                    logger.info(
                        f"Recordatorio {claim['id']} espera: WhatsApp sin número configurado"
                    )
                await asyncio.to_thread(_release, claim)
                continue
            try:
                await asyncio.wait_for(send_whatsapp(message), timeout=SEND_TIMEOUT)
                await asyncio.to_thread(_confirm, claim)
                sent += 1
                logger.info(f"Recordatorio {claim['id']} enviado por WhatsApp")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await asyncio.to_thread(_release, claim)
                logger.warning(
                    f"Recordatorio {claim['id']} no salió por WhatsApp ({type(e).__name__}); "
                    "se reintentará"
                )
            continue

        targets = _targets_for(claim, default_chat_ids, linked)
        if not targets:
            # Recordatorio de un usuario que aún no ha vinculado su Telegram. NO se
            # manda a los chats por defecto: el texto es suyo y no tiene por qué
            # leerlo nadie más. Se queda pendiente y saldrá en cuanto lo vincule.
            if claim["attempts"] % 20 == 0:
                logger.info(
                    f"Recordatorio {claim['id']} espera: su usuario no tiene Telegram vinculado"
                )
            await asyncio.to_thread(_release, claim)
            continue

        if await _deliver(send, claim, targets, message):
            await asyncio.to_thread(_confirm, claim)
            sent += 1
            logger.info(f"Recordatorio {claim['id']} enviado")
        else:
            await asyncio.to_thread(_release, claim)
            logger.warning(f"Recordatorio {claim['id']} devuelto a pendiente; se reintentará")
    return sent


def _targets_for(claim: dict, default_chat_ids: Iterable[int], linked: dict) -> list:
    """A qué chats va este aviso, en orden de preferencia.

    1. El chat guardado al crearlo (lo puso el usuario desde su Telegram).
    2. El chat que el usuario tenga vinculado AHORA (por si lo vinculó después).
    3. Sin usuario (recordatorio antiguo, de antes de los permisos): los chats
       autorizados de la instalación, como se hacía siempre.
    """
    if claim["chat_id"]:
        return [claim["chat_id"]]
    if claim["user_id"] is not None:
        chat_id = linked.get(claim["user_id"])
        return [chat_id] if chat_id else []
    return sorted(default_chat_ids)


async def run_reminder_loop(
    send: SendFn,
    default_chat_ids: Iterable[int],
    poll: float = POLL_SECONDS,
    send_whatsapp: Optional[WhatsAppFn] = None,
) -> None:
    """Bucle infinito del planificador (se lanza con asyncio.create_task en el startup)."""
    logger.info(f"Planificador de recordatorios iniciado (cada {poll:g} s)")
    while True:
        try:
            await process_due(send, default_chat_ids, send_whatsapp=send_whatsapp)
        except asyncio.CancelledError:
            logger.info("Planificador de recordatorios detenido")
            raise
        except Exception:
            logger.exception("Error en el ciclo de recordatorios; se reintenta")
        await asyncio.sleep(poll)

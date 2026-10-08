"""Crear eventos en Google Calendar con confirmación obligatoria.

Seguridad (se hace cumplir en el servidor, no solo con el prompt):
  1. propose_event NO crea nada: guarda una propuesta pendiente en la sesión.
  2. confirm_event solo crea el evento si:
       - hay una propuesta pendiente y no ha caducado,
       - se llama en el turno INMEDIATAMENTE SIGUIENTE a la propuesta, y
       - el último mensaje REAL del usuario es una afirmación ("sí", "agéndalo"...).
     Así, un texto malicioso dentro de un correo o evento no puede agendar nada,
     porque no puede fabricar un mensaje del usuario.
  3. No se invita a nadie (no se envían correos a terceros).

Requiere el permiso OAuth https://www.googleapis.com/auth/calendar.events, que
el usuario concede al conectar su cuenta de Google con la función «Agendar
eventos» habilitada.
"""

import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from core.tools._common import google_credentials, google_error_message
from core.tools.gcalendar import EVENTS_URL
from core.tools.google_client import (
    GoogleNotConfigured, GoogleReauthNeeded, google_get, google_post,
)
from core.tools.time_tools import DEFAULT_TZ, _format

logger = logging.getLogger(__name__)

PENDING_TTL = 600  # segundos que vive una propuesta sin confirmar


def _fmt(dt: datetime) -> str:
    f = _format(dt)
    return f"{f['fecha']}, {f['hora']}"


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", text).strip()


_AFFIRM = re.compile(
    r"^(si|claro|confirmo|confirmado|confirma|hazlo|dale|adelante|ok|okay|vale|perfecto|"
    r"correcto|de acuerdo|esta bien|agendalo|agenda|agendala|crealo|crea|guardalo|programalo)\b"
)
_BLOCKERS = re.compile(r"\b(no|pero|cambia|cambialo|mejor|espera|cancela|cancelar|otra)\b")


def is_affirmative(text: str) -> bool:
    """True si el mensaje del usuario es una confirmación clara y sin reservas."""
    t = _normalize(text or "")
    if not t or len(t) > 60:
        return False
    return bool(_AFFIRM.match(t)) and not _BLOCKERS.search(t)


async def propose_event(
    title: str,
    start: str,
    end: Optional[str] = None,
    duration_minutes: int = 60,
    location: Optional[str] = None,
    description: Optional[str] = None,
    _session=None,
) -> dict:
    """Prepara un evento (hora de Colombia) y lo deja pendiente de confirmación. No crea nada."""
    if _session is None:
        return {"error": "No hay sesión de conversación; no se puede preparar el evento"}

    tz = ZoneInfo(DEFAULT_TZ)
    title = (title or "").strip()[:100]
    if not title:
        return {"error": "Falta el título del evento"}

    try:
        start_dt = datetime.strptime(start.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
        if end and end.strip():
            end_dt = datetime.strptime(end.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
        else:
            minutes = max(5, min(int(duration_minutes or 60), 24 * 60))
            end_dt = start_dt + timedelta(minutes=minutes)
    except (ValueError, AttributeError):
        return {"error": "Fecha u hora inválida. Formato esperado: AAAA-MM-DDTHH:MM (hora de Colombia)"}

    if end_dt <= start_dt:
        return {"error": "La hora de fin debe ser posterior a la de inicio"}
    if start_dt < datetime.now(tz) - timedelta(minutes=5):
        return {"error": "Esa fecha y hora ya pasaron"}

    # Choques con eventos existentes (solo lectura, en el calendario del usuario)
    creds, error = await google_credentials(_session)
    if error:
        return error

    conflicts = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            data = await google_get(
                client,
                creds,
                EVENTS_URL,
                {
                    "timeMin": start_dt.isoformat(),
                    "timeMax": end_dt.isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "maxResults": 5,
                },
            )
        for ev in data.get("items", []):
            if ev.get("status") != "cancelled":
                conflicts.append((ev.get("summary") or "(sin título)")[:80])
    except Exception as e:
        logger.warning(f"No se pudo revisar choques de agenda: {e}")

    _session.pending_event = {
        "turn": _session.turn_no,
        "created": time.monotonic(),
        "body": {
            "summary": title,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": DEFAULT_TZ},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": DEFAULT_TZ},
            **({"location": location.strip()[:100]} if location and location.strip() else {}),
            **({"description": description.strip()[:500]} if description and description.strip() else {}),
        },
    }

    return {
        "estado": "pendiente_de_confirmacion",
        "titulo": title,
        "inicio": _fmt(start_dt),
        "fin": _format(end_dt)["hora"],
        "lugar": location or None,
        "choques_con": conflicts,
        "instruccion": (
            "AÚN NO se ha creado nada. Lee al usuario el título, el día de la semana, la fecha y la "
            "hora, menciona los choques si los hay, y pregúntale si lo agendas. Llama a confirm_event "
            "solo si en su siguiente mensaje responde que sí."
        ),
    }


async def confirm_event(_session=None) -> dict:
    """Crea el evento pendiente, solo si el usuario acaba de confirmarlo."""
    if _session is None:
        return {"error": "No hay sesión de conversación"}

    pending = getattr(_session, "pending_event", None)
    if not pending:
        return {"error": "No hay ningún evento pendiente de confirmar"}

    if time.monotonic() - pending["created"] > PENDING_TTL:
        _session.pending_event = None
        return {"error": "La propuesta caducó. Hay que prepararla de nuevo con propose_event"}

    if _session.turn_no != pending["turn"] + 1:
        _session.pending_event = None
        return {"error": "No se puede agendar sin que el usuario confirme. Hay que preparar el evento de nuevo"}

    if not is_affirmative(_session.last_user_text):
        return {
            "error": (
                "El usuario todavía no ha confirmado con claridad. Pregúntale si agenda el evento "
                "y espera su respuesta; no insistas con esta herramienta."
            )
        }

    body = pending["body"]
    _session.pending_event = None  # un solo uso, pase lo que pase

    creds, error = await google_credentials(_session)
    if error:
        return error

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            created = await google_post(client, creds, EVENTS_URL, body, params={"sendUpdates": "none"})
    except (GoogleNotConfigured, GoogleReauthNeeded) as e:
        return google_error_message(e)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        logger.error(f"Google Calendar rechazó la creación del evento: {code}")
        if code in (401, 403):
            return {
                "error": (
                    "Google no permitió crear el evento: falta el permiso de escritura del calendario. "
                    "El usuario tiene que volver a conectar su cuenta de Google desde la sección "
                    "«Conexiones» para concederlo."
                )
            }
        return {"error": f"Google no pudo crear el evento (código {code})"}

    start_dt = datetime.fromisoformat(body["start"]["dateTime"])
    return {
        "estado": "creado",
        "titulo": body["summary"],
        "inicio": _fmt(start_dt),
        "enlace": created.get("htmlLink"),
    }


# ---------------------------------------------------------------------------
# Eliminar evento
# ---------------------------------------------------------------------------

async def delete_event(event_id: str, _session=None) -> dict:
    """Elimina UN evento del calendario. La acción no se puede deshacer.

    El event_id se obtiene de list_events. Solo se ejecuta si el usuario lo
    pidió en su último mensaje (check_delete lo verifica).
    """
    from core.tools._common import check_delete, register_delete

    err = check_delete(_session)
    if err:
        return err

    if not event_id or not event_id.strip():
        return {"error": "Falta el id del evento"}

    creds, error = await google_credentials(_session)
    if error:
        return error

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            from core.tools.google_client import get_access_token
            token = await get_access_token(client, creds)
            r = await client.delete(
                f"{EVENTS_URL.rstrip('/')}/{event_id.strip()}",
                headers={"Authorization": f"Bearer {token}"},
            )
            # 204 No Content = borrado correctamente; 404 = ya no existía
            if r.status_code == 404:
                return {"error": "No se encontró el evento con ese id. Puede que ya haya sido eliminado."}
            if r.status_code not in (200, 204):
                r.raise_for_status()
    except (GoogleNotConfigured, GoogleReauthNeeded) as e:
        return google_error_message(e)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        logger.error("Google Calendar rechazó la eliminación del evento: %s", code)
        if code in (401, 403):
            return {
                "error": (
                    "Google no permitió eliminar el evento: falta el permiso de escritura del calendario. "
                    "El usuario tiene que volver a conectar su cuenta de Google desde «Conexiones»."
                )
            }
        return {"error": f"Google no pudo eliminar el evento (código {code})"}

    register_delete(_session)
    return {
        "estado": "eliminado",
        "event_id": event_id,
    }


# ---------------------------------------------------------------------------
# Reagendar evento con confirmación obligatoria
# ---------------------------------------------------------------------------

PENDING_RESCHEDULE_TTL = 600  # segundos que vive una propuesta sin confirmar


async def propose_reschedule(
    event_id: str,
    new_start: str,
    new_end: Optional[str] = None,
    duration_minutes: int = 60,
    _session=None,
) -> dict:
    """Prepara el cambio de fecha/hora de un evento SIN modificarlo todavía.

    Devuelve un resumen para que Igris se lo lea al usuario y le pregunte si
    confirma. Solo cuando diga que sí se llama a confirm_reschedule.
    """
    if _session is None:
        return {"error": "No hay sesión de conversación; no se puede preparar el cambio"}

    if not event_id or not event_id.strip():
        return {"error": "Falta el id del evento"}

    tz = ZoneInfo(DEFAULT_TZ)
    try:
        start_dt = datetime.strptime(new_start.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
        if new_end and new_end.strip():
            end_dt = datetime.strptime(new_end.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
        else:
            minutes = max(5, min(int(duration_minutes or 60), 24 * 60))
            end_dt = start_dt + timedelta(minutes=minutes)
    except (ValueError, AttributeError):
        return {"error": "Fecha u hora inválida. Formato esperado: AAAA-MM-DDTHH:MM (hora de Colombia)"}

    if end_dt <= start_dt:
        return {"error": "La hora de fin debe ser posterior a la de inicio"}
    if start_dt < datetime.now(tz) - timedelta(minutes=5):
        return {"error": "Esa fecha y hora ya pasaron"}

    # Leer el título actual del evento para mostrárselo al usuario
    creds, error = await google_credentials(_session)
    if error:
        return error

    event_title = "(sin título)"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            data = await google_get(client, creds, f"{EVENTS_URL.rstrip('/')}/{event_id.strip()}")
            event_title = (data.get("summary") or event_title)[:100]
    except Exception as e:
        logger.warning("No se pudo leer el título del evento %s: %s", event_id, e)

    # Verificar choques con otros eventos
    conflicts = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            data = await google_get(
                client, creds, EVENTS_URL,
                {
                    "timeMin": start_dt.isoformat(),
                    "timeMax": end_dt.isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "maxResults": 5,
                },
            )
        for ev in data.get("items", []):
            if ev.get("status") != "cancelled" and ev.get("id") != event_id.strip():
                conflicts.append((ev.get("summary") or "(sin título)")[:80])
    except Exception as e:
        logger.warning("No se pudo revisar choques: %s", e)

    _session.pending_reschedule = {
        "turn": _session.turn_no,
        "created": time.monotonic(),
        "event_id": event_id.strip(),
        "patch": {
            "start": {"dateTime": start_dt.isoformat(), "timeZone": DEFAULT_TZ},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": DEFAULT_TZ},
        },
        "titulo": event_title,
    }

    return {
        "estado": "pendiente_de_confirmacion",
        "titulo": event_title,
        "nuevo_inicio": _fmt(start_dt),
        "nuevo_fin": _format(end_dt)["hora"],
        "choques_con": conflicts,
        "instruccion": (
            "AÚN NO se ha modificado nada. Lee al usuario el título del evento, el nuevo día de la "
            "semana, la fecha y la hora, menciona los choques si los hay, y pregúntale si confirma "
            "el cambio. Llama a confirm_reschedule solo si en su siguiente mensaje responde que sí."
        ),
    }


async def confirm_reschedule(_session=None) -> dict:
    """Aplica el reagendado preparado con propose_reschedule, solo si el usuario acaba de confirmarlo."""
    if _session is None:
        return {"error": "No hay sesión de conversación"}

    pending = getattr(_session, "pending_reschedule", None)
    if not pending:
        return {"error": "No hay ningún cambio de evento pendiente de confirmar"}

    if time.monotonic() - pending["created"] > PENDING_RESCHEDULE_TTL:
        _session.pending_reschedule = None
        return {"error": "La propuesta de cambio caducó. Hay que prepararla de nuevo con propose_reschedule"}

    if _session.turn_no != pending["turn"] + 1:
        _session.pending_reschedule = None
        return {"error": "No se puede aplicar el cambio sin que el usuario confirme. Prepáralo de nuevo con propose_reschedule"}

    if not is_affirmative(_session.last_user_text):
        return {
            "error": (
                "El usuario todavía no ha confirmado con claridad. Pregúntale si confirma el cambio "
                "y espera su respuesta; no insistas con esta herramienta."
            )
        }

    event_id = pending["event_id"]
    patch = pending["patch"]
    titulo = pending["titulo"]
    _session.pending_reschedule = None  # un solo uso

    creds, error = await google_credentials(_session)
    if error:
        return error

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            from core.tools.google_client import get_access_token
            token = await get_access_token(client, creds)
            r = await client.patch(
                f"{EVENTS_URL.rstrip('/')}/{event_id}",
                json=patch,
                params={"sendUpdates": "none"},
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            updated = r.json()
    except (GoogleNotConfigured, GoogleReauthNeeded) as e:
        return google_error_message(e)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        logger.error("Google Calendar rechazó el reagendado del evento: %s", code)
        if code == 404:
            return {"error": "No se encontró el evento. Puede que haya sido eliminado."}
        if code in (401, 403):
            return {
                "error": (
                    "Google no permitió modificar el evento: falta el permiso de escritura del calendario. "
                    "El usuario tiene que volver a conectar su cuenta de Google desde «Conexiones»."
                )
            }
        return {"error": f"Google no pudo modificar el evento (código {code})"}

    start_dt = datetime.fromisoformat(patch["start"]["dateTime"])
    return {
        "estado": "reagendado",
        "titulo": titulo,
        "nuevo_inicio": _fmt(start_dt),
        "enlace": updated.get("htmlLink"),
    }

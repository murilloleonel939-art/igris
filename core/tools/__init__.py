"""Registro de herramientas de IGRIS (tool calling, formato OpenAI).

Para añadir una herramienta nueva:
  1. Crea su función async en un módulo de esta carpeta (devuelve un dict).
  2. Agrega su esquema a TOOLS.
  3. Regístrala en _HANDLERS.
  4. Asígnale su función (permiso) en core/capabilities.py (TOOL_FEATURES). Si no
     se asigna, la herramienta queda permitida para todos los usuarios.
"""

import json
import logging

from core.capabilities import denial_message
from core.tools import calendar_write, gcalendar, gmail, notes, reminders, time_tools, weather

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": (
                "Obtiene la fecha y hora actuales. Por defecto devuelve la hora de Colombia. "
                "Úsala cuando el usuario pregunte la hora, el día o la fecha."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": (
                            "Zona horaria IANA, por ejemplo 'America/Bogota' o 'Europe/Madrid'. "
                            "Omitir para usar la hora de Colombia."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Obtiene el clima actual y el pronóstico de hoy de una ciudad. "
                "Úsala cuando el usuario pregunte por el clima, la temperatura o si va a llover."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": (
                            "Nombre de la ciudad, por ejemplo 'Medellín'. "
                            "Omitir para usar la ciudad por defecto del usuario."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_emails",
            "description": (
                "Lista correos de la bandeja de entrada de Gmail del usuario (remitente, asunto, "
                "fecha y vista previa) y cuántos no leídos hay. Úsala cuando pregunte por sus "
                "correos, mensajes nuevos o si le escribió alguien."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Búsqueda opcional con sintaxis de Gmail, por ejemplo 'from:banco' "
                            "o 'subject:factura'."
                        ),
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "true para solo no leídos (por defecto). false para incluir leídos.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Cantidad de correos a listar (1 a 10, por defecto 5).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": (
                "Lee el contenido de un correo concreto usando el id obtenido con list_emails. "
                "Úsala cuando el usuario pida saber qué dice un correo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Id del correo (de list_emails)."}
                },
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": (
                "Lista los eventos del Google Calendar del usuario. Úsala cuando pregunte por su "
                "agenda, reuniones o qué tiene hoy, mañana o esta semana."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Fecha de inicio AAAA-MM-DD. Omitir para hoy.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Cuántos días cubrir desde la fecha (1 a 14, por defecto 1).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_event",
            "description": (
                "Prepara un evento en el Google Calendar del usuario SIN crearlo todavía: devuelve un "
                "resumen para que el usuario lo confirme. Úsala cuando pida agendar, programar o "
                "crear una reunión o cita con fecha y hora en su calendario. Si el usuario pide "
                "cambios antes de confirmar, vuelve a llamarla con los datos corregidos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Título del evento."},
                    "start": {
                        "type": "string",
                        "description": "Inicio en hora de Colombia, formato AAAA-MM-DDTHH:MM, por ejemplo 2026-10-08T15:00.",
                    },
                    "end": {
                        "type": "string",
                        "description": "Fin, mismo formato. Omitir si se indica la duración.",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duración en minutos si no hay hora de fin (por defecto 60).",
                    },
                    "location": {"type": "string", "description": "Lugar (opcional)."},
                    "description": {"type": "string", "description": "Notas del evento (opcional)."},
                },
                "required": ["title", "start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_event",
            "description": (
                "Crea el evento preparado con propose_event. Llámala SOLO cuando el usuario, en su "
                "mensaje más reciente, acaba de responder que sí a agendarlo. Nunca en el mismo turno "
                "en que preparaste el evento."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": (
                "Crea un recordatorio que Igris enviará como aviso por Telegram a la hora indicada. "
                "Úsala cuando el usuario pida que le recuerdes algo (por ejemplo 'recuérdame mañana "
                "a las 8 llamar al banco'). Calcula la fecha con la fecha y hora actuales de Colombia. "
                "Si falta la hora, pregúntala. No es para eventos del calendario (eso es propose_event)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Qué recordar, corto y en infinitivo o frase simple, por ejemplo 'llamar al banco'.",
                    },
                    "when": {
                        "type": "string",
                        "description": "Cuándo avisar, en hora de Colombia, formato AAAA-MM-DDTHH:MM, por ejemplo 2026-10-07T08:00.",
                    },
                    "repeat": {
                        "type": "string",
                        "enum": ["ninguna", "diaria", "semanal"],
                        "description": "Repetición opcional. Por defecto 'ninguna' (una sola vez).",
                    },
                },
                "required": ["text", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": (
                "Lista los recordatorios pendientes con su id y cuándo avisarán. Úsala cuando "
                "pregunte qué recordatorios tiene, y antes de cancelar uno para conocer su id."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_reminder",
            "description": (
                "Cancela UN recordatorio pendiente por su id (obtenido con list_reminders). "
                "Solo cuando el usuario lo pidió en su último mensaje; si hay dudas sobre cuál es, "
                "pregúntale antes. Un solo recordatorio por orden."
            ),
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "integer", "description": "Id del recordatorio."}},
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": (
                "Guarda una nota de texto. Úsala cuando el usuario pida anotar o guardar algo "
                "(por ejemplo 'anota que la clave del wifi de la oficina es X'). Guarda el dato "
                "completo y tal cual lo dijo."
            ),
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Texto completo de la nota."}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "Lista las notas más recientes con su id. Úsala cuando pregunte qué notas tiene.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": (
                "Busca en las notas por palabras clave (sin importar tildes). Úsala cuando pregunte "
                "qué anotó sobre un tema, por ejemplo 'wifi'. Usa una o dos palabras clave, no la frase entera."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Palabras clave a buscar."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": (
                "Borra UNA nota por su id (obtenido con list_notes o search_notes). El borrado no se "
                "puede deshacer: solo cuando el usuario lo pidió en su último mensaje; si hay dudas "
                "sobre cuál es, pregúntale antes. Una sola nota por orden."
            ),
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "integer", "description": "Id de la nota."}},
                "required": ["id"],
            },
        },
    },
]

_HANDLERS = {
    "get_time": time_tools.get_time,
    "get_weather": weather.get_weather,
    "list_emails": gmail.list_emails,
    "read_email": gmail.read_email,
    "list_events": gcalendar.list_events,
    "propose_event": calendar_write.propose_event,
    "confirm_event": calendar_write.confirm_event,
    "create_reminder": reminders.create_reminder,
    "list_reminders": reminders.list_reminders,
    "delete_reminder": reminders.delete_reminder,
    "add_note": notes.add_note,
    "list_notes": notes.list_notes,
    "search_notes": notes.search_notes,
    "delete_note": notes.delete_note,
}

# Herramientas que necesitan la sesión de conversación: para el estado de la charla
# (propuestas pendientes, turno actual), para saber DE QUÉ USUARIO son los datos y
# para resolver con qué cuenta de Google se consulta. El modelo no puede aportar
# nada de esto: lo inyecta el servidor y descarta cualquier "_session" que envíe.
_SESSION_TOOLS = {
    "propose_event", "confirm_event",
    "create_reminder", "list_reminders", "delete_reminder",
    "add_note", "list_notes", "search_notes", "delete_note",
    "list_emails", "read_email", "list_events",
}


async def run_tool(name: str, arguments: str, session=None) -> str:
    """Ejecuta una herramienta y devuelve el resultado como texto JSON.

    Nunca lanza excepciones: los errores se devuelven como {"error": ...}
    para que el modelo pueda explicarlos con naturalidad.

    Los permisos se comprueban AQUÍ, no solo al ofrecer las herramientas al
    modelo. Es la comprobación que de verdad protege: aunque el modelo llame a
    una herramienta que no le tocaba (o un correo intente provocarlo), no se
    ejecuta.
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)

    caps = getattr(session, "capabilities", None)
    # Sin sesión no hay usuario del que dudar: son llamadas internas del servidor
    # (por ejemplo la confirmación directa de un evento), y se permiten.
    if session is not None and caps is not None and not caps.allows_tool(name):
        logger.warning("Herramienta '%s' bloqueada por permisos del usuario %s", name, caps.user_id)
        return json.dumps({"error": denial_message(name, caps)}, ensure_ascii=False)

    try:
        args = json.loads(arguments) if arguments else {}
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        args = {}

    # El modelo nunca puede inyectar la sesión: se descarta cualquier "_session" suyo
    args.pop("_session", None)
    if name in _SESSION_TOOLS:
        args["_session"] = session

    logger.info(f"Ejecutando herramienta: {name} {[k for k in args if k != '_session']}")
    try:
        result = await handler(**args)
    except TypeError as e:
        result = {"error": f"Argumentos inválidos: {e}"}
    except Exception as e:
        logger.exception(f"Error en herramienta {name}")
        result = {"error": f"Falló la herramienta: {e}"}

    return json.dumps(result, ensure_ascii=False)

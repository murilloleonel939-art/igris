"""Registro de herramientas de IGRIS (tool calling, formato OpenAI).

Para añadir una herramienta nueva:
  1. Crea su función async en un módulo de esta carpeta (devuelve un dict).
  2. Agrega su esquema a TOOLS.
  3. Regístrala en _HANDLERS.
"""

import json
import logging

from core.tools import gcalendar, gmail, time_tools, weather

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
]

_HANDLERS = {
    "get_time": time_tools.get_time,
    "get_weather": weather.get_weather,
    "list_emails": gmail.list_emails,
    "read_email": gmail.read_email,
    "list_events": gcalendar.list_events,
}


async def run_tool(name: str, arguments: str) -> str:
    """Ejecuta una herramienta y devuelve el resultado como texto JSON.

    Nunca lanza excepciones: los errores se devuelven como {"error": ...}
    para que el modelo pueda explicarlos con naturalidad.
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)

    try:
        args = json.loads(arguments) if arguments else {}
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        args = {}

    logger.info(f"Ejecutando herramienta: {name} {args}")
    try:
        result = await handler(**args)
    except TypeError as e:
        result = {"error": f"Argumentos inválidos: {e}"}
    except Exception as e:
        logger.exception(f"Error en herramienta {name}")
        result = {"error": f"Falló la herramienta: {e}"}

    return json.dumps(result, ensure_ascii=False)

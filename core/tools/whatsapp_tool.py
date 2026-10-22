"""Herramienta para enviar mensajes por WhatsApp vía Meta Cloud API.

El destinatario se toma de la configuración guardada en Conexiones
(global_settings.whatsapp.phone_number). Si no hay número configurado, se
devuelve un error claro para que la IA no invente que lo envió.
"""

import logging
from typing import Any, Optional

from core.settings_manager import get_settings
from core.whatsapp import WhatsAppClient, WhatsAppConfigurationError, WhatsAppAPIError

logger = logging.getLogger(__name__)


def _configured_destination() -> str:
    """Número de WhatsApp guardado en Conexiones, sin '+'."""
    try:
        phone = (get_settings().get_whatsapp_config().get("phone_number") or "").strip()
    except Exception as e:  # la configuración nunca debe romper el envío
        logger.warning("No se pudo leer el número de WhatsApp configurado: %s", e)
        return ""
    return phone.lstrip("+").strip()


async def send_whatsapp_message(
    message: str,
    phone_number: Optional[str] = None,
    _session: Optional[Any] = None,
) -> dict[str, Any]:
    """Envía un mensaje de texto por WhatsApp.

    Args:
        message: Texto del mensaje (máx. 4096 caracteres).
        phone_number: Destinatario alternativo en formato E.164 sin '+'. Normalmente
            se omite: se usa el número configurado en Conexiones.

    Returns:
        Dict con el resultado del envío o con un error explicable.
    """
    try:
        destination = (phone_number or "").strip().lstrip("+") or _configured_destination()
        if not destination:
            return {
                "error": "No hay número de WhatsApp configurado en Conexiones",
                "hint": (
                    "El administrador debe guardar el número en Conexiones antes de "
                    "poder enviar mensajes."
                ),
            }

        client = WhatsAppClient()
        result = await client.send_text(destination, message)
        sent = (result.get("messages") or [{}])[0] if isinstance(result, dict) else {}
        return {
            "status": "success",
            "to": destination,
            "message_id": sent.get("id"),
            "message": f"Mensaje enviado por WhatsApp a +{destination}.",
        }
    except WhatsAppConfigurationError as e:
        logger.error("WhatsApp no configurado: %s", e)
        return {
            "error": f"WhatsApp no está configurado: {e}",
            "hint": "Faltan las credenciales de la Cloud API en el servidor.",
        }
    except WhatsAppAPIError as e:
        logger.error("Error en WhatsApp API: %s", e)
        return {"error": f"WhatsApp API rechazó la solicitud: {e}"}
    except ValueError as e:
        return {"error": f"Argumento inválido: {e}"}
    except Exception as e:
        logger.exception("Error inesperado al enviar WhatsApp")
        return {"error": f"Error al enviar mensaje: {e}"}

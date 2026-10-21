"""Herramienta para enviar mensajes por WhatsApp vía Meta Cloud API."""

import logging
from typing import Any

from core.whatsapp import WhatsAppClient, WhatsAppConfigurationError, WhatsAppAPIError

logger = logging.getLogger(__name__)


async def send_whatsapp_message(
    phone_number: str,
    message: str,
) -> dict[str, Any]:
    """Envía un mensaje de texto por WhatsApp.
    
    Args:
        phone_number: Número de teléfono en formato E.164 sin '+' (ej: 573504807732)
        message: Texto del mensaje (máx 4096 caracteres)
    
    Returns:
        Dict con el resultado del envío o error
    """
    try:
        client = WhatsAppClient()
        result = await client.send_text(phone_number, message)
        return {
            "status": "success",
            "message_id": result.get("messages", [{}])[0].get("id"),
            "details": result,
        }
    except WhatsAppConfigurationError as e:
        logger.error(f"WhatsApp no configurado: {e}")
        return {
            "error": f"WhatsApp no está configurado: {str(e)}",
            "hint": "Contacta al administrador para configurar las credenciales de WhatsApp",
        }
    except WhatsAppAPIError as e:
        logger.error(f"Error en WhatsApp API: {e}")
        return {
            "error": f"WhatsApp API rechazó la solicitud: {str(e)}",
        }
    except ValueError as e:
        return {
            "error": f"Argumento inválido: {str(e)}",
        }
    except Exception as e:
        logger.exception("Error inesperado al enviar WhatsApp")
        return {
            "error": f"Error al enviar mensaje: {str(e)}",
        }

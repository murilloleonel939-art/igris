"""
Home Assistant - Integración con Home Assistant para control de dispositivos
"""
import asyncio
import logging
from typing import Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


async def validate_homeassistant_connection(url: str, token: str) -> dict[str, Any]:
    """Valida que la conexión a Home Assistant funciona.
    
    Args:
        url: URL base del servidor HA (ej: http://10.0.6.3:8123)
        token: Token de acceso de HA
        
    Returns:
        dict con estado de la conexión y detalles del servidor
    """
    if not url or not token:
        return {"success": False, "error": "URL y token requeridos"}
    
    try:
        # Normalizar URL (sin trailing slash)
        url = url.rstrip('/')
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            
            # Verificar conexión
            async with session.get(f"{url}/api/", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "success": True,
                        "message": "Conexión exitosa con Home Assistant",
                        "server": data.get("message", "OK")
                    }
                elif resp.status == 401:
                    return {"success": False, "error": "Token inválido o expirado"}
                else:
                    return {"success": False, "error": f"Error HTTP {resp.status}"}
                    
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout: Home Assistant no responde"}
    except aiohttp.ClientError as e:
        return {"success": False, "error": f"Error de conexión: {str(e)}"}
    except Exception as e:
        logger.error("Error validando conexión HA: %s", e)
        return {"success": False, "error": "Error interno al validar conexión"}


async def list_homeassistant_devices(url: str, token: str) -> dict[str, Any]:
    """Lista todos los dispositivos disponibles en Home Assistant.
    
    Args:
        url: URL base del servidor HA
        token: Token de acceso de HA
        
    Returns:
        dict con lista de dispositivos y sus estados
    """
    if not url or not token:
        return {"success": False, "error": "URL y token requeridos"}
    
    try:
        url = url.rstrip('/')
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            
            # Obtener estados de todas las entidades
            async with session.get(f"{url}/api/states", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    states = await resp.json()
                    
                    # Filtrar solo dispositivos útiles (light, switch, climate, cover, etc.)
                    devices = {}
                    for state in states:
                        entity_id = state.get("entity_id", "")
                        domain = entity_id.split('.')[0] if '.' in entity_id else None
                        
                        # Incluir dominios relevantes
                        if domain in ["light", "switch", "climate", "cover", "fan", "lock", "media_player", "vacuum"]:
                            devices[entity_id] = {
                                "entity_id": entity_id,
                                "state": state.get("state"),
                                "attributes": state.get("attributes", {}),
                                "domain": domain
                            }
                    
                    return {
                        "success": True,
                        "devices": devices,
                        "count": len(devices)
                    }
                elif resp.status == 401:
                    return {"success": False, "error": "Token inválido"}
                else:
                    return {"success": False, "error": f"Error HTTP {resp.status}"}
                    
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout al listar dispositivos"}
    except Exception as e:
        logger.error("Error listando dispositivos HA: %s", e)
        return {"success": False, "error": "Error al listar dispositivos"}


async def get_homeassistant_device_state(url: str, token: str, entity_id: str) -> dict[str, Any]:
    """Obtiene el estado actual de un dispositivo específico.
    
    Args:
        url: URL base del servidor HA
        token: Token de acceso de HA
        entity_id: ID de la entidad (ej: light.sala)
        
    Returns:
        dict con estado actual del dispositivo
    """
    if not url or not token or not entity_id:
        return {"success": False, "error": "URL, token y entity_id requeridos"}
    
    try:
        url = url.rstrip('/')
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            
            async with session.get(
                f"{url}/api/states/{entity_id}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    state = await resp.json()
                    return {
                        "success": True,
                        "entity_id": entity_id,
                        "state": state.get("state"),
                        "attributes": state.get("attributes", {})
                    }
                elif resp.status == 404:
                    return {"success": False, "error": "Entidad no encontrada"}
                else:
                    return {"success": False, "error": f"Error HTTP {resp.status}"}
                    
    except Exception as e:
        logger.error("Error obteniendo estado de dispositivo HA: %s", e)
        return {"success": False, "error": "Error al obtener estado del dispositivo"}


async def call_homeassistant_service(
    url: str,
    token: str,
    domain: str,
    service: str,
    entity_id: str,
    data: Optional[dict] = None
) -> dict[str, Any]:
    """Ejecuta un servicio en Home Assistant (ej: encender luz).
    
    Args:
        url: URL base del servidor HA
        token: Token de acceso de HA
        domain: Dominio del servicio (ej: light)
        service: Nombre del servicio (ej: turn_on)
        entity_id: ID de la entidad a controlar
        data: Datos adicionales para el servicio (opcional)
        
    Returns:
        dict con resultado del servicio
    """
    if not all([url, token, domain, service, entity_id]):
        return {"success": False, "error": "URL, token, domain, service y entity_id requeridos"}
    
    try:
        url = url.rstrip('/')
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            
            payload = {
                "entity_id": entity_id,
                **(data or {})
            }
            
            async with session.post(
                f"{url}/api/services/{domain}/{service}",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status in [200, 201]:
                    result = await resp.json()
                    return {
                        "success": True,
                        "message": f"Servicio {domain}.{service} ejecutado",
                        "result": result
                    }
                elif resp.status == 401:
                    return {"success": False, "error": "Token inválido"}
                else:
                    return {"success": False, "error": f"Error HTTP {resp.status}"}
                    
    except Exception as e:
        logger.error("Error ejecutando servicio HA: %s", e)
        return {"success": False, "error": "Error al ejecutar servicio"}


async def turn_on_device(url: str, token: str, entity_id: str) -> dict[str, Any]:
    """Enciende un dispositivo (light, switch, etc).
    
    Args:
        url: URL base del servidor HA
        token: Token de acceso de HA
        entity_id: ID del dispositivo (ej: light.sala)
        
    Returns:
        dict con resultado
    """
    domain = entity_id.split('.')[0] if '.' in entity_id else None
    if not domain:
        return {"success": False, "error": "Entity ID inválido"}
    
    return await call_homeassistant_service(url, token, domain, "turn_on", entity_id)


async def turn_off_device(url: str, token: str, entity_id: str) -> dict[str, Any]:
    """Apaga un dispositivo (light, switch, etc).
    
    Args:
        url: URL base del servidor HA
        token: Token de acceso de HA
        entity_id: ID del dispositivo (ej: light.sala)
        
    Returns:
        dict con resultado
    """
    domain = entity_id.split('.')[0] if '.' in entity_id else None
    if not domain:
        return {"success": False, "error": "Entity ID inválido"}
    
    return await call_homeassistant_service(url, token, domain, "turn_off", entity_id)


# ──────────────────────────────────────────────────────────────────────────
# Versiones que aceptan _session para integración con el servidor iGRIS
# ──────────────────────────────────────────────────────────────────────────

async def list_homeassistant_devices_for_session(_session=None) -> dict[str, Any]:
    """Lista dispositivos de Home Assistant del usuario actual.
    
    Obtiene credenciales de HA del usuario de la sesión.
    """
    if not _session or not _session.user:
        return {"success": False, "error": "Usuario no autenticado"}
    
    user = _session.user
    if not user.can_use_homeassistant:
        return {"success": False, "error": "Home Assistant no está habilitado para este usuario"}
    
    if not user.homeassistant_url or not user.homeassistant_token:
        return {"success": False, "error": "Home Assistant no está configurado. Ve a Conexiones para vincular tu cuenta."}
    
    return await list_homeassistant_devices(user.homeassistant_url, user.homeassistant_token)


async def get_homeassistant_device_state_for_session(entity_id: str, _session=None) -> dict[str, Any]:
    """Obtiene el estado de un dispositivo HA del usuario actual."""
    if not _session or not _session.user:
        return {"success": False, "error": "Usuario no autenticado"}
    
    user = _session.user
    if not user.can_use_homeassistant:
        return {"success": False, "error": "Home Assistant no está habilitado"}
    
    if not user.homeassistant_url or not user.homeassistant_token:
        return {"success": False, "error": "Home Assistant no está configurado"}
    
    return await get_homeassistant_device_state(user.homeassistant_url, user.homeassistant_token, entity_id)


async def control_homeassistant_device_for_session(
    entity_id: str,
    action: str,
    data: Optional[dict] = None,
    _session=None
) -> dict[str, Any]:
    """Controla un dispositivo HA del usuario actual.
    
    Args:
        entity_id: ID del dispositivo (ej: light.sala)
        action: Acción (turn_on, turn_off, toggle)
        data: Datos adicionales (optional)
        _session: Sesión del usuario
    """
    if not _session or not _session.user:
        return {"success": False, "error": "Usuario no autenticado"}
    
    user = _session.user
    if not user.can_use_homeassistant:
        return {"success": False, "error": "Home Assistant no está habilitado"}
    
    if not user.homeassistant_url or not user.homeassistant_token:
        return {"success": False, "error": "Home Assistant no está configurado"}
    
    domain = entity_id.split('.')[0] if '.' in entity_id else None
    if not domain:
        return {"success": False, "error": "Entity ID inválido"}
    
    return await call_homeassistant_service(
        user.homeassistant_url,
        user.homeassistant_token,
        domain,
        action,
        entity_id,
        data
    )


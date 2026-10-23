"""
Home Assistant - Integración con Home Assistant para control de dispositivos
"""
import asyncio
import logging
import os
import socket
from typing import Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


def _client_session() -> aiohttp.ClientSession:
    """Sesión HTTP que solo usa IPv4.

    En la red interna de Docker el mismo contenedor responde por IPv4 y por
    IPv6, y el resolver puede devolver primero la IPv6. aiohttp escoge una
    sola familia por petición: si se queda con la IPv6 y esa ruta no existe,
    la llamada muere por timeout aunque la IPv4 del mismo host funcione.
    `curl` no lo sufre porque prueba ambas en paralelo, y por eso desde la
    terminal parecía que todo estaba bien.
    """
    try:
        return aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(family=socket.AF_INET)
        )
    except (TypeError, ValueError):
        # Versiones de aiohttp sin el parámetro `family`: mejor intentarlo sin
        # forzar que dejar la integración inservible.
        return aiohttp.ClientSession()


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
        
        async with _client_session() as session:
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
        async with _client_session() as session:
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
        async with _client_session() as session:
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
        async with _client_session() as session:
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
# Adaptador para el servidor IGRIS: Home Assistant CENTRALIZADO
# ──────────────────────────────────────────────────────────────────────────
#
# Hay UN solo Home Assistant para toda la instalación, con sus credenciales en
# las variables de entorno del backend (IGRIS_HA_URL / IGRIS_HA_TOKEN). Ningún
# usuario introduce URL ni token.
#
# El control de acceso es la asignación: homeassistant_devices dice qué
# entidades puede usar cada usuario. Sin fila en esa tabla, la entidad no
# existe para él, aunque esté en el HA compartido.
#
# Esta comprobación se hace AQUÍ y no solo al ofrecer las herramientas al
# modelo: run_tool() es la última puerta y un prompt inyectado podría intentar
# llamar a una entidad de otro usuario.

# Dominios que se ofrecen como "dispositivos manejables". El resto de entidades
# de HA (sensores, automatizaciones, zonas…) se ignoran a propósito: no tienen
# acciones de control y llenarían el prompt sin aportar nada.
_MANAGEABLE_DOMAINS = frozenset({
    "light", "switch", "climate", "cover", "fan", "lock",
    "media_player", "vacuum", "scene", "script", "input_boolean",
})

_SERVICE_ACTIONS = {
    "turn_on": "turn_on",
    "turn_off": "turn_off",
    "toggle": "toggle",
}


def _ha_credentials() -> tuple[str, str]:
    """(url, token) del Home Assistant compartido, o ("", "") si no está configurado."""
    return (
        (os.environ.get("IGRIS_HA_URL") or "").strip().rstrip("/"),
        (os.environ.get("IGRIS_HA_TOKEN") or "").strip(),
    )


def ha_is_configured() -> bool:
    url, token = _ha_credentials()
    return bool(url and token)


def _not_configured() -> dict[str, Any]:
    return {
        "success": False,
        "error": (
            "Home Assistant no está configurado en el servidor. "
            "Pídele al administrador que revise la conexión."
        ),
    }


def _no_user() -> dict[str, Any]:
    return {
        "success": False,
        "error": (
            "No se pudo identificar al usuario de esta conversación. "
            "Pídele que vuelva a entrar a su cuenta de Igris."
        ),
    }


def _session_user_id(_session) -> Optional[int]:
    """Id del usuario de la sesión, venga como BrainSession o como User.

    En el chat llega un BrainSession (con .user_id). Las rutas HTTP pasan
    directamente el modelo User, que expone .id. Sin esto, las llamadas desde
    /api/user/homeassistant/* no encontraban usuario y devolvían "no se pudo
    identificar al usuario".
    """
    if _session is None:
        return None
    value = getattr(_session, "user_id", None)
    if value is None:
        value = getattr(_session, "id", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _assigned_entity_ids(user_id: int) -> dict[str, str]:
    """{entity_id: nombre_visible} de las entidades asignadas al usuario.

    El nombre visible es el custom_name si existe; si no, el original_name; y
    si tampoco, el propio entity_id. Es el nombre con el que Igris identifica
    el dispositivo cuando el usuario le habla.
    """
    from core import database
    from core.database import HomeAssistantDevice

    assigned: dict[str, str] = {}
    try:
        with database.SessionLocal() as db:
            rows = (
                db.query(HomeAssistantDevice)
                .filter(HomeAssistantDevice.user_id == user_id)
                .all()
            )
            for row in rows:
                visible = (row.custom_name or row.original_name or row.entity_id or "").strip()
                assigned[row.entity_id] = visible or row.entity_id
    except Exception as exc:  # pragma: no cover - la BD no debería fallar aquí
        logger.error("Error leyendo entidades asignadas del usuario %s: %s", user_id, exc)
        return {}
    return assigned


async def list_homeassistant_devices_for_session(_session=None) -> dict[str, Any]:
    """Lista SOLO las entidades asignadas al usuario, con su estado actual.

    Devuelve `name` (el nombre con el que el usuario las conoce) junto al
    `entity_id`, para que el modelo pueda hablar de ellas con naturalidad.
    """
    url, token = _ha_credentials()
    if not url or not token:
        return _not_configured()

    user_id = _session_user_id(_session)
    if not user_id:
        return _no_user()

    assigned = _assigned_entity_ids(user_id)
    if not assigned:
        return {
            "success": True,
            "devices": [],
            "count": 0,
            "note": (
                "Este usuario no tiene dispositivos de Home Assistant asignados. "
                "El administrador debe asignárselos desde el panel de Conexiones."
            ),
        }

    result = await list_homeassistant_devices(url, token)
    if not result.get("success"):
        return result

    # Se cruza lo que hay en HA con lo asignado: si el administrador borró una
    # entidad del HA real, deja de aparecer en vez de dar un error al usarla.
    devices = []
    for entity_id, info in (result.get("devices") or {}).items():
        if entity_id not in assigned:
            continue
        devices.append({
            "entity_id": entity_id,
            "name": assigned[entity_id],
            "state": info.get("state"),
            "domain": info.get("domain"),
            "attributes": info.get("attributes", {}),
        })

    return {"success": True, "devices": devices, "count": len(devices)}


async def get_homeassistant_device_state_for_session(
    entity_id: str, _session=None
) -> dict[str, Any]:
    """Estado de una entidad, solo si está asignada al usuario."""
    url, token = _ha_credentials()
    if not url or not token:
        return _not_configured()

    user_id = _session_user_id(_session)
    if not user_id:
        return _no_user()

    assigned = _assigned_entity_ids(user_id)
    if entity_id not in assigned:
        # Mismo mensaje que si no existiera: no se filtra si la entidad existe
        # en el HA compartido pero pertenece a otro usuario.
        return {"success": False, "error": f"No tienes ningún dispositivo llamado '{entity_id}'."}

    result = await get_homeassistant_device_state(url, token, entity_id)
    if result.get("success"):
        result["name"] = assigned[entity_id]
    return result


async def control_homeassistant_device_for_session(
    entity_id: str,
    action: str,
    data: Optional[dict] = None,
    _session=None,
) -> dict[str, Any]:
    """Controla una entidad, solo si está asignada al usuario.

    `action` acepta turn_on / turn_off / toggle.
    """
    url, token = _ha_credentials()
    if not url or not token:
        return _not_configured()

    user_id = _session_user_id(_session)
    if not user_id:
        return _no_user()

    assigned = _assigned_entity_ids(user_id)
    if entity_id not in assigned:
        return {"success": False, "error": f"No tienes ningún dispositivo llamado '{entity_id}'."}

    if "." not in entity_id:
        return {"success": False, "error": "Entity ID inválido"}

    service = _SERVICE_ACTIONS.get((action or "").strip().lower())
    if not service:
        return {
            "success": False,
            "error": "Acción no válida. Usa turn_on, turn_off o toggle.",
        }

    domain = entity_id.split(".")[0]
    result = await call_homeassistant_service(url, token, domain, service, entity_id, data)
    if result.get("success"):
        result["name"] = assigned[entity_id]
    return result


async def resolve_entity_for_session(name_or_id: str, _session=None) -> dict[str, Any]:
    """Traduce lo que dijo el usuario a una entidad asignada suya.

    Acepta el entity_id exacto o el nombre visible (custom_name) sin distinguir
    mayúsculas ni acentos. Es la pieza que permite decir «apaga la luz de la
    sala» en vez de «apaga light.sala».

    Devuelve {"success": True, "entity_id": ...} o un error con las opciones
    disponibles, para que el modelo pueda repreguntar en vez de inventar.
    """
    user_id = _session_user_id(_session)
    if not user_id:
        return _no_user()

    assigned = _assigned_entity_ids(user_id)
    if not assigned:
        return {"success": False, "error": "No tienes dispositivos de Home Assistant asignados."}

    raw = (name_or_id or "").strip()
    if not raw:
        return {"success": False, "error": "Falta el nombre del dispositivo."}

    # 1) entity_id exacto
    if raw in assigned:
        return {"success": True, "entity_id": raw, "name": assigned[raw]}

    def _norm(text: str) -> str:
        import unicodedata

        decomposed = unicodedata.normalize("NFD", (text or "").lower())
        return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").strip()

    target = _norm(raw)
    # 2) nombre visible exacto (sin mayúsculas ni acentos)
    exact = [eid for eid, label in assigned.items() if _norm(label) == target]
    if len(exact) == 1:
        return {"success": True, "entity_id": exact[0], "name": assigned[exact[0]]}

    # 3) coincidencia parcial: «luz» encuentra «Luz de la sala»
    partial = [eid for eid, label in assigned.items() if target in _norm(label)]
    if len(partial) == 1:
        return {"success": True, "entity_id": partial[0], "name": assigned[partial[0]]}
    if len(partial) > 1:
        options = ", ".join(f"'{assigned[e]}'" for e in partial)
        return {
            "success": False,
            "error": f"Hay varios dispositivos que coinciden con '{raw}': {options}. ¿Cuál de ellos?",
            "ambiguous": partial,
        }

    options = ", ".join(f"'{label}'" for label in sorted(assigned.values()))
    return {
        "success": False,
        "error": f"No encuentro '{raw}' entre tus dispositivos. Tienes: {options}.",
    }


async def validate_server_connection(url: str, token: str) -> dict:
    """Valida que una URL y token de HA sean correctos.
    
    Retorna:
        {"success": True} si la conexión es válida
        {"success": False, "error": "...mensaje..."} si no funciona
    """
    if not url or not token:
        return {"success": False, "error": "URL y token son requeridos"}
    
    url = url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with _client_session() as session:
            async with session.get(
                f"{url}/api/",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                if r.status == 200:
                    return {"success": True}
                elif r.status == 401:
                    return {"success": False, "error": "Token inválido"}
                else:
                    return {"success": False, "error": f"Error HTTP {r.status}"}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Conexión agotada (timeout 5s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_server_entities(url: str, token: str) -> dict:
    """Lista todos los dispositivos de una instancia HA.
    
    Retorna:
        {"success": True, "entities": [{"entity_id": "...", "friendly_name": "..."}, ...]}
        {"success": False, "error": "..."}
    """
    url = url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with _client_session() as session:
            async with session.get(
                f"{url}/api/states",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                if r.status != 200:
                    return {"success": False, "error": f"Error HTTP {r.status}"}
                
                states = await r.json()
                
                # Filtrar solo entidades controlables (luz, switch, clima, etc.)
                controllable_domains = {
                    "light", "switch", "climate", "fan", "cover", "lock",
                    "vacuum", "water_heater"
                }
                
                entities = []
                for state in states:
                    entity_id = state.get("entity_id", "")
                    domain = entity_id.split(".")[0] if "." in entity_id else ""
                    
                    if domain in controllable_domains:
                        friendly_name = state.get("attributes", {}).get("friendly_name", entity_id)
                        entities.append({
                            "entity_id": entity_id,
                            "friendly_name": friendly_name,
                        })
                
                return {"success": True, "entities": entities}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Conexión agotada (timeout 5s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}

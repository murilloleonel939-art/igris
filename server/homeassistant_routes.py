"""IGRIS — Home Assistant Integration (/api/user/homeassistant/*)

Endpoints para que los usuarios controlen sus dispositivos de Home Assistant.

NO hay credenciales por usuario. El backend se conecta al HA compartido (credenciales
en variables de entorno). Aquí el usuario solo accede a las entidades que le asignó
el administrador desde /api/admin/homeassistant/devices.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import User, get_db
from core.tools import homeassistant as ha
from server.user_routes import require_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ============= MODELOS =============

class ControlDeviceRequest(BaseModel):
    """Solicitud para controlar un dispositivo."""
    action: str = Field(..., description="Acción: turn_on, turn_off, toggle")
    data: dict = Field(default_factory=dict, description="Datos opcionales")


# ============= HELPERS =============

def _require_configured() -> None:
    """Lanza HTTPException si HA no está configurado."""
    if not ha.ha_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Home Assistant no está configurado en el servidor. "
                "Pídele al administrador que lo configure."
            ),
        )


# ============= ENDPOINTS =============

@router.get("/api/user/homeassistant/status")
async def homeassistant_status(user: User = Depends(require_user)) -> dict[str, Any]:
    """Estado: si HA está configurado y el usuario tiene entidades asignadas."""
    _require_configured()

    from core.database import HomeAssistantDevice, SessionLocal

    assigned_count = 0
    try:
        with SessionLocal() as db:
            assigned_count = (
                db.query(HomeAssistantDevice)
                .filter(HomeAssistantDevice.user_id == user.id)
                .count()
            )
    except Exception as exc:  # pragma: no cover
        logger.error("Error leyendo dispositivos del usuario %s: %s", user.id, exc)

    return {
        "configured": True,
        "devices_assigned": assigned_count,
    }


@router.get("/api/user/homeassistant/devices")
async def list_devices(user: User = Depends(require_user)) -> dict[str, Any]:
    """Lista las entidades asignadas al usuario con su estado actual."""
    _require_configured()
    return await ha.list_homeassistant_devices_for_session(_session=user)


@router.post("/api/user/homeassistant/devices/{entity_id}/control")
async def control_device(
    entity_id: str,
    request: ControlDeviceRequest,
    user: User = Depends(require_user),
) -> dict[str, Any]:
    """Controla un dispositivo asignado al usuario."""
    _require_configured()
    return await ha.control_homeassistant_device_for_session(
        entity_id=entity_id,
        action=request.action,
        data=request.data or None,
        _session=user,
    )


@router.get("/api/user/homeassistant/devices/{entity_id}/state")
async def get_device_state(
    entity_id: str,
    user: User = Depends(require_user),
) -> dict[str, Any]:
    """Estado de un dispositivo asignado al usuario."""
    _require_configured()
    return await ha.get_homeassistant_device_state_for_session(
        entity_id=entity_id,
        _session=user,
    )

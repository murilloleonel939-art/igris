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

from core.database import HomeAssistantDevice, User, get_db, utcnow
from core.tools import homeassistant as ha
from server.user_routes import require_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ============= MODELOS =============

class RenameDeviceRequest(BaseModel):
    """Nombre con el que el usuario conocerá el dispositivo."""
    name: str = Field(..., min_length=1, max_length=120)


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


@router.post("/api/user/homeassistant/devices/{entity_id}/rename")
async def rename_device(
    entity_id: str,
    payload: RenameDeviceRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Pone el nombre que el usuario prefiera a un dispositivo suyo.

    Solo toca su propia fila: dos usuarios pueden tener la misma entidad física
    con nombres distintos, y el de uno no cambia el del otro. Tampoco modifica
    nada en Home Assistant, solo cómo lo llama Igris.
    """
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")

    row = (
        db.query(HomeAssistantDevice)
        .filter(
            HomeAssistantDevice.user_id == user.id,
            HomeAssistantDevice.entity_id == entity_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Ese dispositivo no está asignado a tu cuenta",
        )

    # Si el nombre coincide con el de Home Assistant se guarda vacío, para que
    # siga los cambios que el administrador haga allí.
    original = (row.original_name or "").strip()
    row.custom_name = None if name == original else name
    row.last_sync = utcnow()
    db.commit()
    db.refresh(row)

    logger.info("HA: usuario %s renombró %s a %s", user.id, entity_id, name)
    return {
        "success": True,
        "entity_id": row.entity_id,
        "name": name,
    }

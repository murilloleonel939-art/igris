"""IGRIS — Home Assistant Admin Endpoints (/api/admin/homeassistant/*)

Endpoints para que el administrador gestione la configuración centralizada de HA
y asigne dispositivos a usuarios. Requiere X-Igris-Key.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import User, HomeAssistantDevice, SessionLocal, get_db
from core.tools import homeassistant as ha
from server.user_routes import require_key

logger = logging.getLogger(__name__)

router = APIRouter()


# ============= MODELOS =============

class HomeAssistantConfigRequest(BaseModel):
    """Configuración centralizada de HA (solo administrador)."""
    url: str = Field(..., description="URL de Home Assistant, ej: http://10.0.6.1:8123")
    token: str = Field(..., description="Token de API largo de HA")


class AssignDeviceRequest(BaseModel):
    """Asignar un dispositivo a un usuario."""
    user_id: int = Field(..., description="ID del usuario")
    entity_id: str = Field(..., description="Entity ID, ej: light.sala")
    name: str = Field(..., description="Nombre amigable para mostrar")


# ============= ADMIN PROTECTION =============

async def require_admin_key(
    x_igris_key: str = Header(None),
) -> None:
    """Protege endpoints admin. Delega a require_key del panel."""
    await require_key(x_igris_key)


# ============= ENDPOINTS =============

@router.post("/api/admin/homeassistant/config")
async def set_homeassistant_config(
    request: HomeAssistantConfigRequest,
    _: None = Depends(require_admin_key),
) -> dict[str, str]:
    """Establece la URL y token de HA centralizado.
    
    En producción, estos deberían venir de variables de entorno (Coolify),
    pero exponemos este endpoint para cambiarlos en tiempo de ejecución si es necesario.
    """
    try:
        # Valida conectividad
        is_valid = await ha.validate_homeassistant(request.url, request.token)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo conectar a Home Assistant con esas credenciales.",
            )

        # Guarda en variables de entorno (runtime only; no persiste)
        # En producción real, cambiar Coolify env vars o variables de Docker
        import os
        os.environ["IGRIS_HA_URL"] = request.url
        os.environ["IGRIS_HA_TOKEN"] = request.token

        # Recarga el módulo HA para que use las nuevas credenciales
        ha.reload_homeassistant_config()

        return {"status": "configured", "url": request.url}
    except Exception as exc:
        logger.error("Error configurando HA: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/api/admin/homeassistant/status")
async def admin_homeassistant_status(
    _: None = Depends(require_admin_key),
) -> dict[str, Any]:
    """Estado del HA centralizado y resumen de usuarios."""
    if not ha.ha_is_configured():
        return {
            "configured": False,
            "users_assigned": 0,
            "total_devices_assigned": 0,
        }

    try:
        is_valid = await ha.validate_homeassistant()
        if not is_valid:
            return {
                "configured": True,
                "connected": False,
                "users_assigned": 0,
                "total_devices_assigned": 0,
            }
    except Exception as exc:
        logger.warning("Error validando HA: %s", exc)
        return {
            "configured": True,
            "connected": False,
            "error": str(exc),
        }

    try:
        with SessionLocal() as db:
            users_with_devices = (
                db.query(User.id)
                .distinct()
                .join(HomeAssistantDevice)
                .count()
            )
            total_devices = db.query(HomeAssistantDevice).count()

        return {
            "configured": True,
            "connected": True,
            "users_assigned": users_with_devices,
            "total_devices_assigned": total_devices,
        }
    except Exception as exc:
        logger.error("Error consultando BD: %s", exc)
        return {
            "configured": True,
            "connected": True,
            "error": str(exc),
        }


@router.get("/api/admin/homeassistant/users")
async def list_users_with_devices(
    _: None = Depends(require_admin_key),
) -> list[dict[str, Any]]:
    """Lista usuarios con sus dispositivos HA asignados (sin credenciales)."""
    try:
        with SessionLocal() as db:
            users = db.query(User).all()
            result = []
            for user in users:
                devices = (
                    db.query(HomeAssistantDevice)
                    .filter(HomeAssistantDevice.user_id == user.id)
                    .all()
                )
                result.append({
                    "id": user.id,
                    "name": user.name or "Sin nombre",
                    "email": user.email or "Sin email",
                    "devices_assigned": len(devices),
                    "device_list": [
                        {"entity_id": d.entity_id, "name": d.name}
                        for d in devices
                    ],
                })
            return result
    except Exception as exc:
        logger.error("Error listando usuarios: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/api/admin/homeassistant/devices/assign")
async def assign_device_to_user(
    request: AssignDeviceRequest,
    _: None = Depends(require_admin_key),
) -> dict[str, str]:
    """Asigna un dispositivo de HA a un usuario."""
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == request.user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Usuario {request.user_id} no existe.",
                )

            # Verifica que el entity_id existe en HA
            if not ha.ha_is_configured():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="HA no está configurado.",
                )

            # Intenta obtener el estado del dispositivo (valida su existencia)
            try:
                await ha.get_homeassistant_entity_state(request.entity_id)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Entity '{request.entity_id}' no encontrado en HA: {exc}",
                ) from exc

            # Busca o crea el asignación
            device = (
                db.query(HomeAssistantDevice)
                .filter(
                    HomeAssistantDevice.user_id == request.user_id,
                    HomeAssistantDevice.entity_id == request.entity_id,
                )
                .first()
            )
            if device:
                device.name = request.name
            else:
                device = HomeAssistantDevice(
                    user_id=request.user_id,
                    entity_id=request.entity_id,
                    name=request.name,
                )
                db.add(device)

            db.commit()
            return {
                "status": "assigned",
                "user_id": request.user_id,
                "entity_id": request.entity_id,
                "name": request.name,
            }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error asignando dispositivo: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete("/api/admin/homeassistant/devices/{device_id}")
async def unassign_device(
    device_id: int,
    _: None = Depends(require_admin_key),
) -> dict[str, str]:
    """Desasigna un dispositivo de un usuario."""
    try:
        with SessionLocal() as db:
            device = db.query(HomeAssistantDevice).filter(
                HomeAssistantDevice.id == device_id
            ).first()
            if not device:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dispositivo {device_id} no encontrado.",
                )

            user_id = device.user_id
            entity_id = device.entity_id
            db.delete(device)
            db.commit()

            return {
                "status": "unassigned",
                "user_id": str(user_id),
                "entity_id": entity_id,
            }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error desasignando dispositivo: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/api/admin/homeassistant/available-entities")
async def list_available_entities(
    _: None = Depends(require_admin_key),
) -> list[dict[str, str]]:
    """Lista todas las entidades disponibles en HA para asignar."""
    if not ha.ha_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HA no está configurado.",
        )

    try:
        entities = await ha.list_homeassistant_entities()
        return entities
    except Exception as exc:
        logger.error("Error listando entidades: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

"""
IGRIS — Home Assistant Integration (/api/user/homeassistant/*)

Endpoints para que los usuarios conecten y controlen sus dispositivos de Home Assistant.
"""
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import User, get_db
from core.auth import require_user
from core.tools.homeassistant import (
    validate_homeassistant_connection,
    list_homeassistant_devices,
    get_homeassistant_device_state,
    call_homeassistant_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============= MODELS =============

class ConnectHomeAssistantRequest(BaseModel):
    """Solicitud para conectar Home Assistant"""
    url: str = Field(..., description="URL base de Home Assistant (ej: http://10.0.6.3:8123)")
    token: str = Field(..., description="Token de acceso de Home Assistant")


class ControlDeviceRequest(BaseModel):
    """Solicitud para controlar un dispositivo"""
    entity_id: str = Field(..., description="ID de la entidad (ej: light.sala)")
    action: str = Field(..., description="Acción (turn_on, turn_off, toggle)")
    data: Optional[dict] = Field(None, description="Datos adicionales opcionales")


class DeviceStateResponse(BaseModel):
    """Estado de un dispositivo"""
    entity_id: str
    state: str
    attributes: dict


# ============= ENDPOINTS =============

@router.post("/api/user/homeassistant/connect")
async def connect_homeassistant(
    request: ConnectHomeAssistantRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Conecta el usuario a su instancia de Home Assistant.
    
    Valida la conexión y guarda las credenciales.
    """
    if not request.url or not request.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL y token son requeridos"
        )
    
    # Validar la conexión antes de guardar
    validation = await validate_homeassistant_connection(request.url, request.token)
    if not validation.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.get("error", "No se pudo conectar a Home Assistant")
        )
    
    # Guardar credenciales
    try:
        user.homeassistant_url = request.url.rstrip('/')
        user.homeassistant_token = request.token
        user.can_use_homeassistant = True
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info("Usuario %s conectado a Home Assistant: %s", user.id, request.url)
        
        return {
            "success": True,
            "message": "Conectado a Home Assistant exitosamente",
            "url": user.homeassistant_url,
        }
    except Exception as e:
        db.rollback()
        logger.error("Error guardando credenciales de HA para usuario %s: %s", user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error guardando conexión"
        )


@router.post("/api/user/homeassistant/disconnect")
async def disconnect_homeassistant(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Desconecta el usuario de Home Assistant y elimina las credenciales.
    """
    try:
        user.homeassistant_url = None
        user.homeassistant_token = None
        user.can_use_homeassistant = False
        db.add(user)
        db.commit()
        
        logger.info("Usuario %s desconectado de Home Assistant", user.id)
        
        return {
            "success": True,
            "message": "Desconectado de Home Assistant"
        }
    except Exception as e:
        db.rollback()
        logger.error("Error desconectando HA para usuario %s: %s", user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error desconectando"
        )


@router.get("/api/user/homeassistant/status")
async def homeassistant_status(
    user: User = Depends(require_user),
):
    """
    Devuelve el estado actual de la conexión a Home Assistant.
    """
    if not user.can_use_homeassistant or not user.homeassistant_url:
        return {
            "connected": False,
            "message": "Home Assistant no está conectado"
        }
    
    return {
        "connected": True,
        "url": user.homeassistant_url,
        "message": "Conectado a Home Assistant"
    }


@router.get("/api/user/homeassistant/devices")
async def list_devices(
    user: User = Depends(require_user),
):
    """
    Lista todos los dispositivos disponibles en Home Assistant del usuario.
    """
    if not user.can_use_homeassistant or not user.homeassistant_url or not user.homeassistant_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home Assistant no está configurado"
        )
    
    result = await list_homeassistant_devices(
        user.homeassistant_url,
        user.homeassistant_token
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Error listando dispositivos")
        )
    
    return result


@router.get("/api/user/homeassistant/devices/{entity_id}/state")
async def get_device_state(
    entity_id: str,
    user: User = Depends(require_user),
):
    """
    Obtiene el estado actual de un dispositivo específico.
    """
    if not user.can_use_homeassistant or not user.homeassistant_url or not user.homeassistant_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home Assistant no está configurado"
        )
    
    result = await get_homeassistant_device_state(
        user.homeassistant_url,
        user.homeassistant_token,
        entity_id
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Error obteniendo estado del dispositivo")
        )
    
    return result


@router.post("/api/user/homeassistant/devices/{entity_id}/control")
async def control_device(
    entity_id: str,
    request: ControlDeviceRequest,
    user: User = Depends(require_user),
):
    """
    Controla un dispositivo (turn_on, turn_off, toggle, etc).
    """
    if not user.can_use_homeassistant or not user.homeassistant_url or not user.homeassistant_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home Assistant no está configurado"
        )
    
    # Validar que el action sea válido
    valid_actions = ["turn_on", "turn_off", "toggle", "open", "close", "stop"]
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Acción inválida. Acciones válidas: {', '.join(valid_actions)}"
        )
    
    domain = entity_id.split('.')[0] if '.' in entity_id else None
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity ID inválido"
        )
    
    result = await call_homeassistant_service(
        user.homeassistant_url,
        user.homeassistant_token,
        domain,
        request.action,
        entity_id,
        request.data
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Error controlando dispositivo")
        )
    
    logger.info(
        "Usuario %s ejecutó acción %s en %s",
        user.id, request.action, entity_id
    )
    
    return result


@router.post("/api/user/homeassistant/validate")
async def validate_connection(
    request: ConnectHomeAssistantRequest,
    user: User = Depends(require_user),
):
    """
    Valida una conexión a Home Assistant sin guardarla.
    Útil para probar credenciales antes de conectar.
    """
    result = await validate_homeassistant_connection(request.url, request.token)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "No se pudo conectar a Home Assistant")
        )
    
    return result

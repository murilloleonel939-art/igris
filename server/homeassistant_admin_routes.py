"""
Endpoints admin para gestionar conexiones Home Assistant de usuarios.

Protegidos con admin key (X-Igris-Key header).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from core.database import get_db, User, HAAssignment
from core.tools import homeassistant as ha_tools

# require_key se importará dinámicamente en main.py
require_admin_key = None

logger = logging.getLogger(__name__)

router_admin = APIRouter(prefix="/api/admin/homeassistant", tags=["admin-homeassistant"])


class HAStatusResponse(BaseModel):
    """Estado de conexión HA de un usuario."""
    user_id: int
    user_name: str
    ha_url: str | None
    is_connected: bool
    device_count: int


class HAUserDevicesResponse(BaseModel):
    """Dispositivos de un usuario."""
    user_id: int
    user_name: str
    devices: list[dict]


class ConnectHARequest(BaseModel):
    """Conectar HA a un usuario."""
    user_id: int
    ha_url: str
    ha_token: str


class DisconnectHARequest(BaseModel):
    """Desconectar HA de un usuario."""
    user_id: int


class AssignDeviceRequest(BaseModel):
    """Asignar dispositivo a usuario."""
    user_id: int
    entity_id: str
    friendly_name: str


class UnassignDeviceRequest(BaseModel):
    """Desasignar dispositivo de usuario."""
    user_id: int
    entity_id: str


@router_admin.get("/status", response_model=list[HAStatusResponse])
async def get_ha_status_all(
    db: Session = Depends(get_db),
    _: None = Depends(lambda: require_admin_key),
) -> list[HAStatusResponse]:
    """Lista estado HA de todos los usuarios."""
    users = db.query(User).all()
    result = []

    for user in users:
        is_connected = bool(user.homeassistant_url and user.homeassistant_token)
        device_count = (
            db.query(HAAssignment).filter_by(user_id=user.id).count()
            if is_connected
            else 0
        )

        result.append(
            HAStatusResponse(
                user_id=user.id,
                user_name=user.name or f"User {user.id}",
                ha_url=user.homeassistant_url if is_connected else None,
                is_connected=is_connected,
                device_count=device_count,
            )
        )

    return result


@router_admin.get("/status/{user_id}", response_model=HAStatusResponse)
async def get_ha_status(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(lambda: require_admin_key),
) -> HAStatusResponse:
    """Obtiene estado HA de un usuario específico."""
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    is_connected = bool(user.homeassistant_url and user.homeassistant_token)
    device_count = (
        db.query(HAAssignment).filter_by(user_id=user.id).count()
        if is_connected
        else 0
    )

    return HAStatusResponse(
        user_id=user.id,
        user_name=user.name or f"User {user.id}",
        ha_url=user.homeassistant_url if is_connected else None,
        is_connected=is_connected,
        device_count=device_count,
    )


@router_admin.post("/connect")
async def connect_ha_admin(
    req: ConnectHARequest,
    db: Session = Depends(get_db),
    _: None = Depends(lambda: require_admin_key),
) -> dict:
    """Conecta HA a un usuario. Admin valida credentials."""
    user = db.query(User).filter_by(id=req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar credenciales
    validation = await ha_tools.validate_server_connection(req.ha_url, req.ha_token)
    if not validation.get("success"):
        raise HTTPException(status_code=400, detail=validation.get("error", "Validación fallida"))

    # Guardar credenciales
    user.homeassistant_url = req.ha_url.rstrip("/")
    user.homeassistant_token = req.ha_token
    user.can_use_homeassistant = True

    db.commit()
    logger.info(f"Admin connected HA for user {user.id}")

    return {"success": True, "message": f"HA conectado para {user.name or f'User {user.id}'}"}


@router_admin.post("/disconnect")
async def disconnect_ha_admin(
    req: DisconnectHARequest,
    db: Session = Depends(get_db),
    _: None = Depends(lambda: require_admin_key),
) -> dict:
    """Desconecta HA de un usuario."""
    user = db.query(User).filter_by(id=req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.homeassistant_url = None
    user.homeassistant_token = None
    user.can_use_homeassistant = False

    # Borrar asignaciones de dispositivos
    db.query(HAAssignment).filter_by(user_id=user.id).delete()

    db.commit()
    logger.info(f"Admin disconnected HA for user {user.id}")

    return {"success": True, "message": f"HA desconectado para {user.name or f'User {user.id}'}"}


@router_admin.get("/devices/{user_id}", response_model=HAUserDevicesResponse)
async def get_user_devices(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(lambda: require_admin_key),
) -> HAUserDevicesResponse:
    """Lista dispositivos disponibles en HA del usuario."""
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not user.homeassistant_url or not user.homeassistant_token:
        raise HTTPException(status_code=400, detail="Usuario sin HA conectado")

    # Listar entidades del servidor HA
    entities_result = await ha_tools.list_server_entities(
        user.homeassistant_url, user.homeassistant_token
    )
    if not entities_result.get("success"):
        raise HTTPException(status_code=400, detail=entities_result.get("error", "Error listando entidades"))

    entities = entities_result.get("entities", [])

    # Marcar cuáles están asignadas
    assignments = db.query(HAAssignment).filter_by(user_id=user.id).all()
    assigned_ids = {a.entity_id for a in assignments}

    for entity in entities:
        entity["assigned"] = entity["entity_id"] in assigned_ids

    return HAUserDevicesResponse(
        user_id=user.id,
        user_name=user.name or f"User {user.id}",
        devices=entities,
    )


@router_admin.post("/devices/assign")
async def assign_device(
    req: AssignDeviceRequest,
    db: Session = Depends(get_db),
    _: None = Depends(lambda: require_admin_key),
) -> dict:
    """Asigna un dispositivo HA a un usuario."""
    user = db.query(User).filter_by(id=req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Verificar que no esté ya asignado
    existing = (
        db.query(HAAssignment)
        .filter_by(user_id=req.user_id, entity_id=req.entity_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Dispositivo ya asignado")

    assignment = HAAssignment(
        user_id=req.user_id,
        entity_id=req.entity_id,
        friendly_name=req.friendly_name,
    )
    db.add(assignment)
    db.commit()

    logger.info(f"Admin assigned {req.entity_id} to user {req.user_id}")

    return {"success": True, "message": f"Dispositivo '{req.friendly_name}' asignado"}


@router_admin.post("/devices/unassign")
async def unassign_device(
    req: UnassignDeviceRequest,
    db: Session = Depends(get_db),
    _: None = Depends(lambda: require_admin_key),
) -> dict:
    """Desasigna un dispositivo HA de un usuario."""
    user = db.query(User).filter_by(id=req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    deleted = (
        db.query(HAAssignment)
        .filter_by(user_id=req.user_id, entity_id=req.entity_id)
        .delete()
    )
    db.commit()

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")

    logger.info(f"Admin unassigned {req.entity_id} from user {req.user_id}")

    return {"success": True, "message": "Dispositivo desasignado"}

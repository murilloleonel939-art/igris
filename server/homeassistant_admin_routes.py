"""Admin endpoints for Home Assistant management."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import User, HAAssignment
from core.auth import get_admin_key
from server.database import get_db

router = APIRouter(prefix="/api/admin/homeassistant", tags=["admin-ha"])


class AssignDeviceRequest(BaseModel):
    user_id: int
    entity_id: str
    name: str = ""


class HAStatusResponse(BaseModel):
    configured: bool
    connected: bool
    total_devices_assigned: int
    users_assigned: int


class EntityResponse(BaseModel):
    entity_id: str
    name: str


class DeviceResponse(BaseModel):
    name: str
    entity_id: str


@router.get("/status", response_model=HAStatusResponse, dependencies=[Depends(get_admin_key)])
async def get_ha_status(db: AsyncSession = Depends(get_db)):
    """Get HA server status and assignment stats."""
    # Check if server HA is configured
    from core.tools.homeassistant import get_server_config
    config = get_server_config()
    
    if not config or not config.get("url"):
        return HAStatusResponse(
            configured=False,
            connected=False,
            total_devices_assigned=0,
            users_assigned=0
        )
    
    # Check connection
    from core.tools.homeassistant import validate_server_connection
    try:
        connected = await validate_server_connection()
    except Exception:
        connected = False
    
    # Count assignments
    result = await db.execute(
        select(HAAssignment.user_id).distinct()
    )
    users_with_devices = result.scalars().all()
    
    total_devices = await db.execute(select(HAAssignment))
    total_assigned = len(total_devices.scalars().all())
    
    return HAStatusResponse(
        configured=True,
        connected=connected,
        total_devices_assigned=total_assigned,
        users_assigned=len(users_with_devices)
    )


@router.get("/entities", response_model=dict, dependencies=[Depends(get_admin_key)])
async def list_ha_entities(db: AsyncSession = Depends(get_db)):
    """List all available entities from HA server."""
    from core.tools.homeassistant import list_server_entities
    
    try:
        entities = await list_server_entities()
        return {"entities": [
            EntityResponse(entity_id=e["entity_id"], name=e.get("name", e["entity_id"]))
            for e in entities
        ]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"HA connection failed: {str(e)}")


@router.post("/assign", dependencies=[Depends(get_admin_key)])
async def assign_device_to_user(req: AssignDeviceRequest, db: AsyncSession = Depends(get_db)):
    """Assign a HA device to a user."""
    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == req.user_id))
    user = user_result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already assigned
    existing = await db.execute(
        select(HAAssignment).where(
            (HAAssignment.user_id == req.user_id) & 
            (HAAssignment.entity_id == req.entity_id)
        )
    )
    if existing.scalar():
        raise HTTPException(status_code=409, detail="Device already assigned to user")
    
    # Create assignment
    assignment = HAAssignment(
        user_id=req.user_id,
        entity_id=req.entity_id,
        friendly_name=req.name or req.entity_id
    )
    db.add(assignment)
    await db.commit()
    
    return {"status": "assigned"}


@router.post("/unassign", dependencies=[Depends(get_admin_key)])
async def unassign_device_from_user(req: AssignDeviceRequest, db: AsyncSession = Depends(get_db)):
    """Remove a device assignment from a user."""
    result = await db.execute(
        select(HAAssignment).where(
            (HAAssignment.user_id == req.user_id) & 
            (HAAssignment.entity_id == req.entity_id)
        )
    )
    assignment = result.scalar()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await db.delete(assignment)
    await db.commit()
    
    return {"status": "unassigned"}


@router.get("/users/{user_id}/devices", dependencies=[Depends(get_admin_key)])
async def get_user_devices(user_id: int, db: AsyncSession = Depends(get_db)):
    """List devices assigned to a user."""
    result = await db.execute(
        select(HAAssignment).where(HAAssignment.user_id == user_id)
    )
    assignments = result.scalars().all()
    
    return {
        "devices": [
            DeviceResponse(name=a.friendly_name, entity_id=a.entity_id)
            for a in assignments
        ]
    }

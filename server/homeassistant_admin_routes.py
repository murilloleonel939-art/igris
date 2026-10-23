"""IGRIS — Administración del Home Assistant centralizado (/api/admin/homeassistant/*)

Hay UN solo Home Assistant para toda la instalación, con sus credenciales en las
variables de entorno del backend (IGRIS_HA_URL / IGRIS_HA_TOKEN). El usuario
final nunca ve ni introduce URL ni token.

Aquí el administrador:
  1. Ve el estado de la conexión.
  2. Consulta las entidades que expone HA.
  3. Asigna una entidad a un usuario con el nombre que quiera.

La tabla `homeassistant_devices` es el control de acceso: sin fila asignada a un
usuario, la entidad no existe para él aunque esté en el HA compartido.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import HomeAssistantDevice, User, get_db, utcnow
from core.tools import homeassistant as ha
from server.user_routes import require_admin_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/homeassistant", tags=["admin-homeassistant"])


# ============= MODELOS =============

class AssignDeviceRequest(BaseModel):
    """Asigna una entidad de HA a un usuario, con el nombre que él verá."""
    user_id: int = Field(..., description="Id del usuario que podrá controlarla")
    entity_id: str = Field(..., description="Entidad de HA, ej: light.sala")
    name: str = Field(default="", description="Nombre visible para el usuario")


class UnassignDeviceRequest(BaseModel):
    """Quita la asignación de una entidad a un usuario."""
    user_id: int = Field(...)
    entity_id: str = Field(...)


# ============= HELPERS =============

def _require_configured() -> tuple[str, str]:
    """(url, token) del HA compartido, o 503 si el servidor no está configurado."""
    url, token = ha._ha_credentials()
    if not url or not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Home Assistant no está configurado en el servidor. "
                "Define IGRIS_HA_URL e IGRIS_HA_TOKEN en el entorno del backend."
            ),
        )
    return url, token


def _visible_name(row: HomeAssistantDevice) -> str:
    """Nombre con el que el usuario conoce la entidad."""
    return (row.custom_name or row.original_name or row.entity_id or "").strip() or row.entity_id


# ============= ENDPOINTS =============

@router.get("/status")
async def ha_status(
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Estado de la conexión con el HA compartido y uso por usuario.

    Nunca devuelve el token. La URL sí, porque no es un secreto y ayuda a
    diagnosticar a qué HA está apuntando el backend.
    """
    url, token = ha._ha_credentials()
    if not url or not token:
        # Se distingue el caso "falta una de las dos" para no mandar al
        # administrador a revisar el token cuando lo que falta es la URL.
        missing = [n for n, v in (("IGRIS_HA_URL", url), ("IGRIS_HA_TOKEN", token)) if not v]
        return {
            "configured": False,
            "connected": False,
            "url": url or None,
            "error": "Falta " + " y ".join(missing) + " en el entorno del backend",
            "total_devices_assigned": 0,
            "users_assigned": 0,
        }

    connected = False
    error: Optional[str] = None
    try:
        result = await ha.validate_server_connection(url, token)
        connected = bool(result.get("success"))
        if not connected:
            error = result.get("error")
    except Exception as exc:  # pragma: no cover
        logger.error("Error comprobando HA: %s", exc)
        error = "Error al contactar con Home Assistant"

    rows = db.query(HomeAssistantDevice).all()
    assigned = [r for r in rows if r.user_id is not None]

    return {
        "configured": True,
        "connected": connected,
        "url": url,
        "error": error,
        "total_devices_assigned": len(assigned),
        "users_assigned": len({r.user_id for r in assigned}),
    }


@router.get("/entities")
async def list_entities(
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Entidades que expone el HA compartido, con quién las tiene asignadas.

    Se consulta HA en vivo. Si HA no responde se devuelve igualmente lo que hay
    guardado en la base, para que el panel no quede inservible cuando HA está
    caído o reiniciándose.
    """
    url, token = _require_configured()

    assigned_by_entity: dict[str, list[HomeAssistantDevice]] = {}
    for row in db.query(HomeAssistantDevice).all():
        assigned_by_entity.setdefault(row.entity_id, []).append(row)

    usernames = {u.id: u.username for u in db.query(User).all()}

    live: list[dict[str, Any]] = []
    ha_error: Optional[str] = None
    try:
        result = await ha.list_server_entities(url, token)
        if result.get("success"):
            live = result.get("entities") or []
        else:
            ha_error = result.get("error")
    except Exception as exc:  # pragma: no cover
        logger.error("Error consultando entidades de HA: %s", exc)
        ha_error = "Error al contactar con Home Assistant"

    entities: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in live:
        entity_id = item.get("entity_id")
        if not entity_id:
            continue
        seen.add(entity_id)
        rows = assigned_by_entity.get(entity_id, [])
        entities.append({
            "entity_id": entity_id,
            "name": item.get("friendly_name") or entity_id,
            # Una misma entidad puede estar asignada a varios usuarios: cada uno
            # con su propio nombre. Se listan todos para que el panel lo muestre.
            "assignments": [
                {"user_id": r.user_id, "username": usernames.get(r.user_id), "name": _visible_name(r)}
                for r in rows if r.user_id is not None
            ],
        })

    # Entidades guardadas que ya no están en HA: se muestran marcadas en vez de
    # desaparecer sin explicación.
    for entity_id, rows in assigned_by_entity.items():
        if entity_id in seen:
            continue
        entities.append({
            "entity_id": entity_id,
            "name": rows[0].original_name or entity_id,
            "missing_in_ha": True,
            "assignments": [
                {"user_id": r.user_id, "username": usernames.get(r.user_id), "name": _visible_name(r)}
                for r in rows if r.user_id is not None
            ],
        })

    entities.sort(key=lambda e: (e.get("entity_id") or ""))

    return {"entities": entities, "total": len(entities), "ha_error": ha_error}


@router.post("/assign")
async def assign_device(
    payload: AssignDeviceRequest,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Asigna una entidad a un usuario. Si ya estaba, actualiza el nombre."""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Ese usuario no existe")

    entity_id = (payload.entity_id or "").strip()
    if not entity_id:
        raise HTTPException(status_code=400, detail="Falta la entidad")

    name = (payload.name or "").strip() or entity_id

    row = (
        db.query(HomeAssistantDevice)
        .filter(
            HomeAssistantDevice.user_id == payload.user_id,
            HomeAssistantDevice.entity_id == entity_id,
        )
        .first()
    )

    if row is None:
        # Nombre original de HA, para no perderlo si el usuario luego borra el suyo.
        original_name = entity_id
        entity_type = entity_id.split(".")[0] if "." in entity_id else None
        try:
            url, token = _require_configured()
            result = await ha.list_server_entities(url, token)
            if result.get("success"):
                for item in result.get("entities") or []:
                    if item.get("entity_id") == entity_id:
                        original_name = item.get("friendly_name") or entity_id
                        break
        except HTTPException:
            # HA caído: se guarda igualmente con lo que sabemos. El nombre se
            # corrige en la próxima asignación.
            pass

        row = HomeAssistantDevice(
            user_id=payload.user_id,
            entity_id=entity_id,
            original_name=original_name,
            custom_name=name if name != original_name else None,
            entity_type=entity_type,
            last_sync=utcnow(),
            created_at=utcnow(),
        )
        db.add(row)
    else:
        row.custom_name = name

    db.commit()
    db.refresh(row)

    logger.info("HA: entidad %s asignada al usuario %s", entity_id, payload.user_id)

    return {
        "success": True,
        "user_id": row.user_id,
        "entity_id": row.entity_id,
        "name": _visible_name(row),
    }


@router.post("/unassign")
async def unassign_device(
    payload: UnassignDeviceRequest,
    _: None = Depends(require_admin_key),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Quita la asignación. No toca la entidad real de Home Assistant."""
    deleted = (
        db.query(HomeAssistantDevice)
        .filter(
            HomeAssistantDevice.user_id == payload.user_id,
            HomeAssistantDevice.entity_id == payload.entity_id,
        )
        .delete()
    )
    db.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Esa asignación no existe")

    logger.info("HA: entidad %s desasignada del usuario %s", payload.entity_id, payload.user_id)
    return {"success": True, "entity_id": payload.entity_id, "user_id": payload.user_id}

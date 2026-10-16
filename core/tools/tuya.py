"""Cliente mínimo de Tuya Cloud para dispositivos Smart Life."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
import unicodedata
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_REGION_ENDPOINTS = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}


def _config() -> tuple[str, str, str]:
    access_id = os.getenv("TUYA_ACCESS_ID", "").strip()
    access_secret = os.getenv("TUYA_ACCESS_SECRET", "").strip()
    region = os.getenv("TUYA_REGION", "us").strip().lower()
    endpoint = os.getenv("TUYA_ENDPOINT", _REGION_ENDPOINTS.get(region, _REGION_ENDPOINTS["us"])).rstrip("/")
    return access_id, access_secret, endpoint


def _signed_headers(method: str, path: str, body: str, token: str = "") -> dict[str, str]:
    access_id, secret, _ = _config()
    if not access_id or not secret:
        raise RuntimeError("Faltan TUYA_ACCESS_ID y TUYA_ACCESS_SECRET en la configuración del servidor.")

    timestamp = str(int(time.time() * 1000))
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    string_to_sign = f"{method}\n{body_hash}\n\n{path}"
    prefix = access_id + (token or "") + timestamp
    sign = hmac.new(secret.encode("utf-8"), (prefix + string_to_sign).encode("utf-8"), hashlib.sha256).hexdigest().upper()
    headers = {
        "client_id": access_id,
        "t": timestamp,
        "sign_method": "HMAC-SHA256",
        "sign": sign,
        "Content-Type": "application/json",
    }
    if token:
        headers["access_token"] = token
    return headers


async def _request(method: str, path: str, *, token: str = "", payload: dict | None = None) -> dict[str, Any]:
    _, _, endpoint = _config()
    body = json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False) if method != "GET" else ""
    headers = _signed_headers(method, path, body, token)
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.request(method, endpoint + path, content=body, headers=headers)
    data = response.json()
    if response.status_code >= 400 or not data.get("success", False):
        raise RuntimeError(data.get("msg") or f"Tuya devolvió HTTP {response.status_code}")
    return data.get("result") or {}


async def _token() -> str:
    result = await _request("GET", "/v1.0/token?grant_type=1")
    token = result.get("access_token")
    if not token:
        raise RuntimeError("Tuya no devolvió un token de acceso.")
    return token


async def _call(path: str, method: str = "GET", payload: dict | None = None) -> dict[str, Any]:
    token = await _token()
    return await _request(method, path, token=token, payload=payload)


async def list_tuya_devices() -> dict[str, Any]:
    """Lista los dispositivos vinculados al proyecto Smart Life."""
    try:
        uid = os.getenv("TUYA_UID", "").strip()
        if not uid:
            return {"error": "Falta TUYA_UID para identificar la cuenta Smart Life vinculada."}
        result = await _call(f"/v1.0/users/{uid}/devices")
        # Tuya devuelve normalmente una lista directamente; algunas versiones
        # responden {"devices": [...]}, por lo que soportamos ambos formatos.
        if isinstance(result, list):
            devices = result
        elif isinstance(result, dict):
            devices = result.get("devices", [])
        else:
            devices = []
        return {
            "dispositivos": [
                {"id": d.get("id"), "nombre": d.get("name"), "producto": d.get("product_name"), "online": d.get("online")}
                for d in devices
            ]
        }
    except Exception as exc:
        logger.exception("Error listando dispositivos Tuya")
        return {"error": str(exc)}


def _configured_device_ids() -> set[str]:
    return {
        item.strip()
        for item in os.getenv("TUYA_DEVICE_IDS", "").split(",")
        if item.strip()
    }


def _allowed_device(device_id: str) -> bool:
    configured = _configured_device_ids()
    # Sin allowlist explícita, la cuenta Smart Life vinculada es el límite de acceso.
    return not configured or device_id in configured


def _normalize_device_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


async def _resolve_device_id(device_ref: str) -> str | None:
    """Acepta ID, nombre, alias configurado o una referencia natural."""
    if _allowed_device(device_ref):
        return device_ref

    normalized_ref = _normalize_device_name(device_ref)
    aliases = {}
    for item in os.getenv("TUYA_DEVICE_ALIASES", "").split(","):
        if ":" in item:
            alias, device_id = item.split(":", 1)
            aliases[_normalize_device_name(alias)] = device_id.strip()
    alias_id = aliases.get(normalized_ref)
    if alias_id and _allowed_device(alias_id):
        return alias_id

    try:
        listed = await list_tuya_devices()
        for device in listed.get("dispositivos", []):
            device_id = device.get("id")
            device_name = _normalize_device_name(device.get("nombre"))
            if (
                device_id
                and _allowed_device(device_id)
                and device_name
                and (
                    device_name == normalized_ref
                    or device_name in normalized_ref
                    or normalized_ref in device_name
                )
            ):
                return device_id
    except Exception:
        logger.exception("Error resolviendo nombre de dispositivo Tuya")
    return None


async def get_tuya_device_status(device_id: str) -> dict[str, Any]:
    """Consulta el estado actual de un dispositivo por su id o nombre."""
    resolved_id = await _resolve_device_id(device_id)
    if not resolved_id:
        return {"error": "Ese dispositivo no está autorizado para Igris."}
    device_id = resolved_id
    try:
        return {"device_id": device_id, "estado": await _call(f"/v1.0/iot-03/devices/{device_id}/status")}
    except Exception as exc:
        logger.exception("Error consultando estado Tuya")
        return {"error": str(exc)}


async def send_tuya_command(device_id: str, code: str, value: Any) -> dict[str, Any]:
    """Envía una orden; acepta el ID técnico o el nombre visible."""
    resolved_id = await _resolve_device_id(device_id)
    if not resolved_id:
        return {"error": "Ese dispositivo no está autorizado para Igris."}
    device_id = resolved_id
    try:
        result = await _call(
            f"/v1.0/iot-03/devices/{device_id}/commands",
            method="POST",
            payload={"commands": [{"code": code, "value": value}]},
        )
        return {"device_id": device_id, "resultado": result}
    except Exception as exc:
        logger.exception("Error enviando orden Tuya")
        return {"error": str(exc)}


async def control_tuya_device(device_id: str, code: str, value: Any, _session=None) -> dict[str, Any]:
    """Envía una orden únicamente tras confirmar la orden pendiente exacta."""
    if _session is not None:
        from core.tools.calendar_write import is_affirmative

        pending = getattr(_session, "_tuya_pending", None)
        last_text = getattr(_session, "last_user_text", "")
        if pending and is_affirmative(last_text):
            device_id, code, value = pending
            _session._tuya_pending = None
        else:
            if pending and last_text:
                _session._tuya_pending = None
            _session._tuya_pending = (device_id, code, value)
            return {
                "requiere_confirmacion": True,
                "mensaje": f"Confirma esta acción sobre el dispositivo {device_id} escribiendo sí.",
            }
    return await send_tuya_command(device_id, code, value)


async def list_tuya_device_status(device_id: str, _session=None) -> dict[str, Any]:
    return await get_tuya_device_status(device_id)


async def list_tuya_devices_for_session(_session=None) -> dict[str, Any]:
    return await list_tuya_devices()

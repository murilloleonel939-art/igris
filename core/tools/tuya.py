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
                and device_name
                and (
                    device_name == normalized_ref
                    or device_name in normalized_ref
                    or normalized_ref in device_name
                    or ("aire" in normalized_ref and "aire" in device_name)
                    or ("acondicionado" in normalized_ref and "aire" in device_name)
                )
            ):
                # Los dispositivos ya vienen autorizados por el proyecto Tuya.
                # TUYA_DEVICE_IDS, si existe, solo restringe explícitamente.
                if _allowed_device(device_id):
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
        status = await _call(f"/v1.0/iot-03/devices/{device_id}/status")
        functions = await _device_functions(device_id)
        response: dict[str, Any] = {"device_id": device_id, "estado": status}
        if functions:
            # Se le dicen al modelo los códigos válidos para que no los invente.
            response["funciones"] = [
                {"codigo": f["code"], "tipo": f.get("type"), "valores": f.get("values")}
                for f in functions
            ]
        return response
    except Exception as exc:
        logger.exception("Error consultando estado Tuya")
        return {"error": str(exc)}


async def _device_functions(device_id: str) -> list[dict[str, Any]]:
    """Funciones reales del dispositivo (códigos válidos) según Tuya."""
    try:
        result = await _call(f"/v1.0/iot-03/devices/{device_id}/specification")
    except Exception:
        logger.exception("No se pudo leer la especificación del dispositivo Tuya")
        return []
    functions = result.get("functions") if isinstance(result, dict) else None
    if not isinstance(functions, list):
        return []
    return [f for f in functions if isinstance(f, dict) and f.get("code")]


_ON_CODES = {"switch", "switch 1", "switch 2", "power", "power switch", "switch led", "switch on"}


def _coerce_value(function: dict[str, Any], value: Any) -> Any:
    """Ajusta el valor al tipo que declara el dispositivo (booleano, entero...).

    Los botones de un control IR (PowerOn, PowerOff) se disparan con `true`; enviar
    el nombre del botón como valor hace que Tuya acepte la orden pero no emita la
    señal infrarroja.
    """
    code = _normalize_device_name(function.get("code"))
    ftype = str(function.get("type", "")).casefold()

    if code in {"poweron", "poweroff"} or code.startswith("power on") or code.startswith("power off"):
        return True

    if ftype == "boolean":
        if isinstance(value, str):
            return value.strip().casefold() in {"true", "1", "on", "encender", "prender", "si", "sí", "yes"}
        return bool(value)
    if ftype == "integer":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def _pick_code(functions: list[dict[str, Any]], requested: str) -> dict[str, Any] | None:
    """Elige el código real del dispositivo a partir del que pidió el modelo."""
    codes = {f["code"]: f for f in functions}
    if requested in codes:
        return codes[requested]

    normalized = _normalize_device_name(requested)
    for code, function in codes.items():
        if _normalize_device_name(code) == normalized:
            return function

    # Los controles IR exponen PowerOn/PowerOff en lugar de switch/power. Según lo
    # que pida el usuario (o el valor), se elige el botón correcto.
    wants_off = any(
        word in normalized for word in ("poweroff", "apagar", "apaga", "off", "detener")
    )
    wants_on = any(
        word in normalized for word in ("poweron", "encender", "prender", "enciende", "on", "arrancar")
    )
    if wants_on or wants_off or normalized in _ON_CODES:
        for code, function in codes.items():
            code_name = _normalize_device_name(code)
            if wants_off and code_name in {"poweroff", "power off"}:
                return function
            if not wants_off and code_name in {"poweron", "power on"}:
                return function
        for code, function in codes.items():
            if _normalize_device_name(code) in _ON_CODES:
                return function

    # Como último recurso, coincidencia parcial por nombre.
    for code, function in codes.items():
        code_name = _normalize_device_name(code)
        if code_name and (code_name in normalized or normalized in code_name):
            return function
    return None


async def send_tuya_command(device_id: str, code: str, value: Any) -> dict[str, Any]:
    """Envía una orden; acepta el ID técnico o el nombre visible."""
    resolved_id = await _resolve_device_id(device_id)
    if not resolved_id:
        return {"error": "Ese dispositivo no está autorizado para Igris."}
    device_id = resolved_id

    functions = await _device_functions(device_id)
    logger.info("Funciones del dispositivo %s: %s", device_id, [f.get("code") for f in functions])
    final_code = code
    final_value = value
    if functions:
        function = _pick_code(functions, code)
        logger.info("Código solicitado: %r  → elegido: %r", code, function.get("code") if function else None)
        if function is None:
            return {
                "device_id": device_id,
                "error": f"El dispositivo no acepta la función '{code}'.",
                "funciones_disponibles": [f["code"] for f in functions],
            }
        final_code = function["code"]
        final_value = _coerce_value(function, value)
    else:
        logger.warning("No se obtuvieron funciones para %s; se envía código sin validar: %r", device_id, code)

    logger.info("Enviando a Tuya device=%s code=%r value=%r", device_id, final_code, final_value)
    try:
        result = await _call(
            f"/v1.0/iot-03/devices/{device_id}/commands",
            method="POST",
            payload={"commands": [{"code": final_code, "value": final_value}]},
        )
        logger.info("Respuesta Tuya para %s: %s", device_id, result)
        return {"device_id": device_id, "codigo": final_code, "valor": final_value, "resultado": result}
    except Exception as exc:
        logger.exception("Error enviando orden Tuya")
        return {"error": str(exc)}


async def control_tuya_device(device_id: str, code: str, value: Any, _session=None) -> dict[str, Any]:
    """Deja la orden pendiente de confirmación; no la ejecuta.

    La ejecución la hace el servidor (ver `confirm_pending_command`) cuando el
    mensaje REAL del usuario es una afirmación. Así no depende de que el modelo
    vuelva a llamar la herramienta, que era lo que dejaba la orden bloqueada.
    """
    if _session is None:
        return await send_tuya_command(device_id, code, value)

    _session._tuya_pending = {
        "device_id": device_id,
        "code": code,
        "value": value,
        "turn": getattr(_session, "turn_no", 0),
        "ts": time.time(),
    }
    return {
        "requiere_confirmacion": True,
        "device_id": device_id,
        "code": code,
        "value": value,
        "mensaje": (
            "La orden quedó pendiente. Pídele al usuario que la confirme respondiendo "
            "«sí»; se ejecutará sola, no hace falta que vuelvas a llamar a esta herramienta."
        ),
    }


def _confirmed(text: str) -> bool:
    """Confirma la orden con un «sí» claro, aunque venga dentro de una frase corta.

    Más tolerante que la confirmación de eventos porque aquí el usuario ya expresó
    la intención antes y la orden concreta quedó fijada por el servidor: cualquier
    respuesta con una negación o un cambio la descarta.
    """
    from core.tools.calendar_write import _AFFIRM, _BLOCKERS, _normalize, is_affirmative

    if is_affirmative(text):
        return True
    normalized = _normalize(text or "")
    if not normalized or len(normalized) > 60 or _BLOCKERS.search(normalized):
        return False
    return bool(_AFFIRM.search(normalized))


async def confirm_pending_command(session) -> dict[str, Any] | None:
    """Ejecuta la orden pendiente si el último mensaje real del usuario la confirma.

    Devuelve None si no hay nada pendiente (el turno lo maneja el modelo como siempre).
    """
    pending = getattr(session, "_tuya_pending", None)
    if not pending:
        return None

    from core.tools.calendar_write import PENDING_TTL

    # Cualquier respuesta la consume: una orden solo se confirma en el turno siguiente.
    session._tuya_pending = None

    if time.time() - pending.get("ts", 0) > PENDING_TTL:
        return {"error": "La orden caducó antes de confirmarse; hay que pedirla de nuevo."}
    if getattr(session, "turn_no", 0) > pending.get("turn", 0) + 1:
        return {"error": "La confirmación llegó tarde; la orden fue descartada."}
    if not _confirmed(getattr(session, "last_user_text", "")):
        return None

    return await send_tuya_command(pending["device_id"], pending["code"], pending["value"])


async def list_tuya_device_status(device_id: str, _session=None) -> dict[str, Any]:
    return await get_tuya_device_status(device_id)


async def list_tuya_devices_for_session(_session=None) -> dict[str, Any]:
    return await list_tuya_devices()

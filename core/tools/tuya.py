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
from urllib.parse import urlencode
from typing import Any, Optional

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


async def list_tuya_devices(uid: str) -> dict[str, Any]:
    """Dispositivos de la cuenta Smart Life indicada.

    El uid ya no sale de una variable de entorno: se pasa, porque ahora cada
    usuario tiene la suya. Sin uid no hay nada que listar.
    """
    uid = (uid or "").strip()
    if not uid:
        return {"error": "Este usuario todavía no ha vinculado su cuenta de Tuya."}
    try:
        result = await _call(f"/v1.0/users/{uid}/devices")
        # Tuya devuelve normalmente una lista directamente; algunas versiones
        # responden {"devices": [...]}, por lo que soportamos ambos formatos.
        if isinstance(result, list):
            devices = result
        elif isinstance(result, dict):
            devices = result.get("devices", [])
        else:
            devices = []
        normalized_devices = [
            {
                "id": d.get("id"),
                "nombre": d.get("name"),
                "producto": d.get("product_name"),
                "categoria": d.get("category"),
                "online": d.get("online"),
            }
            for d in devices
        ]
        # El hub es el único dispositivo que contiene mandos virtuales. Los
        # añadimos al inventario para que los nuevos aparatos aparezcan solos.
        for device in normalized_devices:
            if _looks_like_hub(device) and device.get("id"):
                try:
                    device["controles_ir"] = await list_infrared_remotes(device["id"])
                except Exception as exc:
                    logger.warning("No se pudieron cargar controles IR de %s: %s", device["id"], exc)
                    device["controles_ir"] = []
        logger.info("Dispositivos Tuya para búsqueda IR: %s", normalized_devices)
        return {"dispositivos": normalized_devices}
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


class AmbiguousTuyaDeviceError(ValueError):
    """La referencia coincide con más de un dispositivo autorizado."""

    def __init__(self, reference: str, devices: list[dict[str, Any]]):
        self.reference = reference
        self.devices = devices
        names = ", ".join(d.get("nombre") or d.get("id") for d in devices)
        super().__init__(f"La referencia '{reference}' coincide con varios dispositivos: {names}.")


def _looks_like_device_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]{20,32}", value.strip().casefold()))


def _normalize_device_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


async def _resolve_device_id(device_ref: str) -> str | None:
    """Acepta ID, alias o nombre; rechaza referencias que coincidan con varios."""
    reference = str(device_ref or "").strip()
    if _looks_like_device_id(reference) and _allowed_device(reference):
        return reference

    normalized_ref = _normalize_device_name(reference)
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
        matches = []
        for device in listed.get("dispositivos", []):
            device_id = device.get("id")
            device_name = _normalize_device_name(device.get("nombre"))
            product_name = _normalize_device_name(device.get("producto"))
            category_name = _normalize_device_name(device.get("categoria"))
            searchable = " ".join((device_name, product_name, category_name))
            is_air_request = any(word in normalized_ref for word in ("aire", "acondicionado", "clima"))
            is_tv_request = any(word in normalized_ref for word in ("tv", "televisor", "television"))
            is_air_device = any(word in searchable for word in ("aire", "air conditioning", "infrared ac"))
            is_tv_device = any(word in searchable for word in ("tv", "televisor", "television", "infrared tv"))
            matches_name = device_name and (
                device_name == normalized_ref
                or device_name in normalized_ref
                or normalized_ref in device_name
                or (is_air_request and is_air_device)
                or (is_tv_request and is_tv_device)
            )
            if device_id and matches_name and _allowed_device(device_id):
                matches.append(device)
        if len(matches) == 1:
            return matches[0]["id"]
        if len(matches) > 1:
            raise AmbiguousTuyaDeviceError(reference, matches)
    except AmbiguousTuyaDeviceError:
        raise
    except Exception:
        logger.exception("Error resolviendo nombre de dispositivo Tuya")
    return None


async def get_tuya_device_status(device_id: str) -> dict[str, Any]:
    """Consulta el estado real disponible para un dispositivo directo o mando IR."""
    try:
        resolved_id = await _resolve_device_id(device_id)
    except AmbiguousTuyaDeviceError as exc:
        return {
            "error": "Necesito que especifiques cuál dispositivo quieres consultar.",
            "dispositivos_coincidentes": [d.get("nombre") or d.get("id") for d in exc.devices],
        }
    if not resolved_id:
        return {"error": "No encontré un dispositivo único con ese nombre."}
    device_id = resolved_id
    try:
        # El estado de un aire IR se consulta en el endpoint específico del mando;
        # el endpoint genérico solo refleja el dispositivo virtual y puede mentir.
        hub = await _find_infrared_hub(device_id)
        if hub:
            hub_id, remotes = hub
            remote = next((r for r in remotes if r.get("remote_id") == device_id), None)
            if remote and int(remote.get("category_id", -1)) == _AC_CATEGORY_ID:
                status = await get_infrared_ac_status(hub_id, device_id)
                return {
                    "device_id": device_id,
                    "hub_id": hub_id,
                    "control": remote.get("remote_name"),
                    "tipo": "infrarrojos",
                    "estado": status,
                    "verificado_por": "estado del aire en Smart IR",
                }

        status = await _call(f"/v1.0/iot-03/devices/{device_id}/status")
        functions = await _device_functions(device_id)
        response: dict[str, Any] = {"device_id": device_id, "estado": status}
        if hub:
            response["tipo"] = "infrarrojos"
            response["verificado_por"] = "estado reportado por el mando virtual"
        else:
            response["tipo"] = "dispositivo_directo"
            response["verificado_por"] = "estado reportado por Smart Life"
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


async def list_infrared_remotes(infrared_id: str) -> list[dict[str, Any]]:
    """Controles remotos (aire, TV...) guardados dentro de un hub infrarrojo.

    Un hub IR no expone el aire como dispositivo aparte: el aire vive aquí como un
    control remoto virtual, con su propio `remote_id`.
    """
    result = await _call(f"/v2.0/infrareds/{infrared_id}/remotes")
    if isinstance(result, list):
        remotes = [r for r in result if isinstance(r, dict)]
    elif isinstance(result, dict):
        nested = next(
            (
                result.get(key)
                for key in ("remotes", "remote_list", "remoteList", "list", "data", "result")
                if result.get(key) is not None
            ),
            [],
        )
        if isinstance(nested, dict):
            nested = next(
                (
                    nested.get(key)
                    for key in ("remotes", "remote_list", "remoteList", "list", "data")
                    if nested.get(key) is not None
                ),
                [],
            )
        remotes = [r for r in nested if isinstance(r, dict)] if isinstance(nested, list) else []
    else:
        remotes = []
    logger.info(
        "Respuesta controles IR device=%s tipo=%s cantidad=%d datos=%s",
        infrared_id,
        type(result).__name__,
        len(remotes),
        remotes,
    )
    return remotes


# En Tuya, la categoría 5 es "aire acondicionado" y la 2 "televisor".
_AC_CATEGORY_ID = 5

# Categorías de producto que identifican un hub emisor de infrarrojos.
_HUB_CATEGORY_HINTS = ("infrared", "ir_remote", "remote_control", "wnykq", "smart ir")

# Caché de sondeos: evita repetir la búsqueda de hub en cada orden. Guarda también
# los negativos, para que un dispositivo directo (bombilla, enchufe) no provoque un
# sondeo de toda la cuenta cada vez que se le manda una orden.
_HUB_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_HUB_CACHE_TTL = 300


def _looks_like_hub(device: dict[str, Any]) -> bool:
    """Heurística para reconocer el aparato físico que emite infrarrojos."""
    haystack = " ".join(
        str(device.get(key) or "") for key in ("categoria", "category", "producto", "nombre")
    ).casefold()
    return any(hint in haystack for hint in _HUB_CATEGORY_HINTS)


async def _find_infrared_hub(preferred_id: str) -> tuple[str, list[dict[str, Any]]] | None:
    """Localiza el hub IR real y sus controles.

    El usuario nombra "el aire", y la resolución devuelve el control *virtual*
    (`eb0fa487...`), no el hub que emite. Se prueba el id recibido y después el
    resto de dispositivos de la cuenta, dando prioridad a los que parecen un hub.
    """
    hub_id, remotes = await _probe_infrared(preferred_id)
    if remotes:
        return hub_id, remotes

    try:
        listed = await list_tuya_devices()
        others = [
            d for d in listed.get("dispositivos", [])
            if d.get("id") and d["id"] != preferred_id
        ]
    except Exception:
        logger.exception("No se pudo listar dispositivos para buscar el hub IR")
        return None

    # Primero los que por categoría o nombre parecen un hub emisor.
    others.sort(key=lambda d: not _looks_like_hub(d))

    for device in others:
        candidate = device["id"]
        hub_id, remotes = await _probe_infrared(candidate)
        if remotes:
            logger.info("Hub IR localizado en %s (%s)", candidate, device.get("nombre"))
            return hub_id, remotes
    return None


async def _probe_infrared(candidate: str) -> tuple[str, list[dict[str, Any]]]:
    """Devuelve (id, controles) si el dispositivo es un hub IR; si no, ([], [])."""
    cached = _HUB_CACHE.get(candidate)
    if cached and time.time() - cached[0] < _HUB_CACHE_TTL:
        return candidate, cached[1]
    try:
        remotes = await list_infrared_remotes(candidate)
    except Exception as exc:
        logger.warning("Fallo al consultar controles IR device=%s: %s", candidate, exc)
        return candidate, []
    logger.info("Sondeo IR device=%s encontró %d controles", candidate, len(remotes))
    if remotes:
        _HUB_CACHE[candidate] = (time.time(), remotes)
    return candidate, remotes


def _is_air_conditioner(remote: dict[str, Any]) -> bool:
    try:
        if int(remote.get("category_id", -1)) == _AC_CATEGORY_ID:
            return True
    except (TypeError, ValueError):
        pass
    name = _normalize_device_name(remote.get("remote_name"))
    return "aire" in name or "air" in name or "acondicionado" in name


def _find_air_conditioner(remotes: list[dict[str, Any]]) -> dict[str, Any] | None:
    for remote in remotes:
        if _is_air_conditioner(remote) and remote.get("remote_id"):
            return remote
    return None


def _power_intent(code: str, value: Any) -> bool | None:
    """Traduce código y valor a encender (True) o apagar (False)."""
    normalized = _normalize_device_name(code)
    if any(word in normalized for word in ("poweroff", "power off", "apagar", "apaga", "detener")):
        return False
    if any(word in normalized for word in ("poweron", "power on", "encender", "prender", "enciende")):
        return True

    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "1", "on", "encender", "prender", "si", "sí", "yes"}:
            return True
        if lowered in {"false", "0", "off", "apagar", "no"}:
            return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return None


_IR_KEY_ALIASES = {
    "poweron": "Power",
    "poweroff": "Power",
    "power": "Power",
    "switch": "Power",
    "encender": "Power",
    "prender": "Power",
    "apagar": "Power",
    "volumenmas": "Volume+",
    "volumenmenos": "Volume-",
    "subirvolumen": "Volume+",
    "bajarvolumen": "Volume-",
    "silenciar": "Mute",
    "mute": "Mute",
    "canalmas": "Channel+",
    "canalmenos": "Channel-",
    "subircanal": "Channel+",
    "bajarcana": "Channel-",
    "bajarcanal": "Channel-",
}


def _infrared_key(code: str, value: Any) -> str:
    normalized = _normalize_device_name(code).replace(" ", "")
    return _IR_KEY_ALIASES.get(normalized, code)


async def send_infrared_key(
    infrared_id: str, remote: dict[str, Any], code: str, value: Any
) -> dict[str, Any]:
    """Envía una tecla a cualquier mando virtual (TV, equipo, ventilador, etc.)."""
    key = _infrared_key(code, value)
    payload: dict[str, Any] = {
        "category_id": int(remote["category_id"]),
        "key": key,
    }
    if remote.get("remote_index") is not None:
        payload["remote_index"] = int(remote["remote_index"])
    result = await _call(
        f"/v2.0/infrareds/{infrared_id}/remotes/{remote['remote_id']}/command",
        method="POST",
        payload=payload,
    )
    logger.info("Orden IR genérica enviada a %s remote=%s payload=%s → %s", infrared_id, remote["remote_id"], payload, result)
    return {
        "device_id": infrared_id,
        "via": "infrarrojos",
        "control": remote.get("remote_name") or remote["remote_id"],
        "tecla": key,
        "resultado": result,
    }


async def send_infrared_power(infrared_id: str, remote: dict[str, Any], power_on: bool) -> dict[str, Any]:
    """Enciende o apaga el aire a través del control remoto del hub IR.

    Se usa la API de aires acondicionados por infrarrojos, que es la que emite de
    verdad la señal: la API genérica de comandos de dispositivo responde `true`
    pero solo mueve los botones del hub, sin irradiar nada.
    """
    remote_id = remote.get("remote_id")
    payload: dict[str, Any] = {"power": 1 if power_on else 0}
    if remote.get("remote_index") is not None:
        payload["remote_index"] = remote["remote_index"]
    if remote.get("category_id") is not None:
        payload["category_id"] = remote["category_id"]

    result = await _call(
        f"/v2.0/infrareds/{infrared_id}/air-conditioners/{remote_id}/scenes/command",
        method="POST",
        payload=payload,
    )
    logger.info("Orden IR enviada a %s remote=%s payload=%s → %s", infrared_id, remote_id, payload, result)
    return {
        "device_id": infrared_id,
        "via": "infrarrojos",
        "control": remote.get("remote_name") or "aire acondicionado",
        "accion": "encender" if power_on else "apagar",
        "resultado": result,
    }


async def get_infrared_ac_status(infrared_id: str, remote_id: str) -> dict[str, Any]:
    return await _call(f"/v2.0/infrareds/{infrared_id}/remotes/{remote_id}/ac/status")


async def send_tuya_command(device_id: str, code: str, value: Any) -> dict[str, Any]:
    """Envía una orden solo cuando la referencia identifica un dispositivo único."""
    try:
        resolved_id = await _resolve_device_id(device_id)
    except AmbiguousTuyaDeviceError as exc:
        return {
            "error": "Necesito que especifiques cuál dispositivo quieres controlar.",
            "dispositivos_coincidentes": [d.get("nombre") or d.get("id") for d in exc.devices],
        }
    if not resolved_id:
        return {"error": "No encontré un dispositivo único con ese nombre."}
    device_id = resolved_id

    # Un hub infrarrojo necesita su propia API: el aire no es un dispositivo aparte.
    hub = await _find_infrared_hub(device_id)

    if hub:
        hub_id, remotes = hub
        logger.info("Hub IR %s con controles: %s", hub_id, [r.get("remote_name") for r in remotes])
        # Solo se redirige al hub cuando el dispositivo resuelto es uno de sus
        # mandos virtuales. Un dispositivo Wi-Fi directo nunca debe terminar
        # enviando una orden al aire por accidente.
        remote = next((r for r in remotes if r.get("remote_id") == device_id), None)
        if remote:
            power_on = _power_intent(code, value)
            try:
                if int(remote.get("category_id", -1)) == _AC_CATEGORY_ID and power_on is not None:
                    return await send_infrared_power(hub_id, remote, power_on)
                return await send_infrared_key(hub_id, remote, code, value)
            except Exception as exc:
                logger.exception("Error enviando orden IR")
                return {"error": str(exc)}

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
    """Ejecuta inmediatamente una orden explícita de Smart Life o Smart IR."""
    # El usuario ya dio la orden en el mensaje actual. No se pide una segunda
    # confirmación: se ejecuta directamente y se devuelve el resultado real.
    return await send_tuya_command(device_id, code, value)


async def list_tuya_device_status(device_id: str, _session=None) -> dict[str, Any]:
    return await get_tuya_device_status(device_id)


def _session_user_id(session) -> Optional[int]:
    """Id del usuario a partir de la sesión del cerebro o del modelo User.

    Las tools reciben un BrainSession (.user_id) cuando las llama Igris, pero
    las rutas HTTP pasan el modelo User, que expone .id. Con leer solo
    .user_id, desde HTTP nunca se encontraba al usuario.
    """
    if session is None:
        return None
    uid = getattr(session, "user_id", None)
    if isinstance(uid, int):
        return uid
    uid = getattr(session, "id", None)
    return uid if isinstance(uid, int) else None


def tuya_uid_for_user(user_id: Optional[int]) -> Optional[str]:
    """uid de Tuya vinculado por ese usuario, si lo tiene."""
    if not user_id:
        return None
    # Import local: core.database importa muchas cosas y tuya.py se carga
    # también desde contextos donde la base aún no está lista.
    from core.database import SessionLocal, TuyaAccount

    db = SessionLocal()
    try:
        row = db.query(TuyaAccount).filter(TuyaAccount.user_id == user_id).first()
        return row.tuya_uid if row else None
    finally:
        db.close()


async def list_tuya_devices_for_session(session=None) -> dict[str, Any]:
    """Dispositivos de la cuenta Tuya del usuario de la sesión.

    Sin vinculación no se devuelve nada: la cuenta global ya no se usa como
    respaldo, porque el objetivo es que cada usuario vea solo su casa.
    """
    user_id = _session_user_id(session)
    uid = tuya_uid_for_user(user_id)
    if not uid:
        return {
            "error": "Todavía no has vinculado tu cuenta de Tuya. Hazlo desde Conexiones.",
            "sin_vincular": True,
        }
    return await list_tuya_devices(uid)


# ─────────────────────────────────────────────────────────────────────────────
# OAuth 2.0 por usuario
#
# Flujo: el usuario abre el H5 de Tuya con su client_id, autoriza, y Tuya lo
# devuelve a nuestro callback con un `code`. Ese code se canjea con
# grant_type=2 y la respuesta trae el `uid` de esa cuenta, que es lo que
# identifica su casa. A partir de ahí sus dispositivos se listan con su uid y
# no con el compartido del servidor.
# ─────────────────────────────────────────────────────────────────────────────

def oauth_client_id() -> str:
    """Client ID de la app de autorización (App Authorization), no el del proyecto."""
    return os.getenv("TUYA_OAUTH_CLIENT_ID", "").strip()


def oauth_client_secret() -> str:
    return os.getenv("TUYA_OAUTH_CLIENT_SECRET", "").strip()


def oauth_is_configured() -> bool:
    return bool(oauth_client_id() and oauth_client_secret())


def oauth_authorize_url(state: str = "") -> str:
    """URL del H5 de Tuya al que mandamos al usuario para que autorice.

    `state` viaja de ida y vuelta sin que Tuya lo interprete: ahí va el usuario
    firmado, para saber a quién asociar el uid cuando vuelva el callback. Sin
    ese dato el callback no podría saber quién autorizó.
    """
    client_id = oauth_client_id()
    if not client_id:
        raise RuntimeError(
            "Falta TUYA_OAUTH_CLIENT_ID en la configuración del servidor."
        )
    callback = os.getenv(
        "TUYA_OAUTH_CALLBACK",
        "https://igris.zottagroup.com/api/user/tuya/callback",
    ).strip()
    params = {"client_id": client_id, "redirect_uri": callback}
    if state:
        params["state"] = state
    query = urlencode(params)
    return f"https://h5.tuya.com/d/login?{query}"


async def oauth_exchange_code(code: str) -> dict[str, Any]:
    """Canjea el `code` del callback por un token y devuelve el uid.

    Aquí se usa la credencial OAuth de la app (TUYA_OAUTH_*), no la del
    proyecto. Son llaves distintas: la del proyecto firma las llamadas de
    control, esta autoriza cuentas de usuario.
    """
    client_id = oauth_client_id()
    client_secret = oauth_client_secret()
    if not client_id or not client_secret:
        return {"error": "La vinculación con Tuya no está configurada en el servidor."}

    _, _, endpoint = _config()
    path = f"/v1.0/token?grant_type=2&code={code}"
    timestamp = str(int(time.time() * 1000))

    # Firma igual que el resto de llamadas, pero con la credencial OAuth.
    body_hash = hashlib.sha256(b"").hexdigest()
    string_to_sign = f"GET\n{body_hash}\n\n{path}"
    sign = hmac.new(
        client_secret.encode("utf-8"),
        (client_id + timestamp + string_to_sign).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()

    headers = {
        "client_id": client_id,
        "t": timestamp,
        "sign_method": "HMAC-SHA256",
        "sign": sign,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(endpoint + path, headers=headers)
        data = response.json()
    except Exception as exc:
        logger.exception("Error canjeando el código de Tuya")
        return {"error": f"No se pudo contactar con Tuya: {exc}"}

    if not data.get("success"):
        return {"error": data.get("msg") or f"Tuya devolvió HTTP {response.status_code}"}

    result = data.get("result") or {}
    uid = result.get("uid")
    if not uid:
        return {"error": "Tuya autorizó la cuenta pero no devolvió su identificador."}
    return {"uid": uid}


async def uid_has_devices(uid: str) -> bool:
    """¿La cuenta autorizada tiene al menos un dispositivo?

    Sirve para validar en el callback que el uid es real y no una respuesta
    vacía: si no tiene aparatos, se guarda igual, pero conviene saberlo.
    """
    try:
        result = await _call(f"/v1.0/users/{uid}/devices")
    except Exception as exc:
        logger.warning("No se pudieron comprobar los dispositivos de %s: %s", uid, exc)
        return False
    devices = result if isinstance(result, list) else (result.get("devices") or [])
    return bool(devices)

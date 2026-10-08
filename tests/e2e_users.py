#!/usr/bin/env python3
"""
Prueba end-to-end del área de usuarios y del panel, contra un servidor real.

Comprueba lo que de verdad importa:
  1. Que el acceso del ADMINISTRADOR sigue funcionando igual que antes.
  2. Que la clave de admin NO sirve en /api/user y el token de usuario NO sirve
     en /api/admin (las dos superficies están separadas de verdad).
  3. Que un token manipulado (role: admin) se rechaza.
  4. Que un usuario desactivado no puede entrar ni seguir usando su token.
  5. Que el CORS responde al preflight con Authorization y DELETE, que es lo que
     rompía el área de usuarios cuando allow_headers no lo incluía.
  6. Que el historial de dos usuarios no se mezcla.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8099"
ADMIN_KEY = os.environ["IGRIS_ACCESS_KEY"]

passed = 0
failed = []


def check(name, condition, detail=""):
    global passed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed.append(name)
        print(f"  ❌ {name} {detail}")


def req(method, path, body=None, headers=None, raw=False):
    """Devuelve (status, datos). No lanza excepción en errores HTTP."""
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            payload = resp.read()
            return resp.status, (payload if raw else json.loads(payload or b"{}"))
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, (payload if raw else json.loads(payload or b"{}"))
        except Exception:
            return e.code, payload


print("\n=== IGRIS — PRUEBAS DEL ÁREA DE USUARIOS ===\n")

# ---------------------------------------------------------------- 1. ADMIN
print("1) El acceso del administrador sigue igual")
s, d = req("GET", "/api/auth/check", headers={"X-Igris-Key": ADMIN_KEY})
check("clave correcta -> 200", s == 200, f"(status {s})")

s, d = req("GET", "/api/auth/check")
check("sin clave -> 401", s == 401, f"(status {s})")

s, d = req("GET", "/api/auth/check", headers={"X-Igris-Key": "clave-mala"})
check("clave incorrecta -> 401", s == 401, f"(status {s})")

s, d = req("GET", "/api/admin/users", headers={"X-Igris-Key": ADMIN_KEY})
check("admin lista usuarios -> 200", s == 200, f"(status {s})")

# ------------------------------------------------- 2. LIMPIEZA DE PRUEBAS PREVIAS
# El script tiene que poder ejecutarse muchas veces seguidas. Si quedara un
# usuario de una ejecución anterior, crearlo daría 409 y las pruebas siguientes
# fallarían por una razón que no tiene nada que ver con el código.
print("\n2) Limpieza de ejecuciones anteriores")
s, d = req("GET", "/api/admin/users", headers={"X-Igris-Key": ADMIN_KEY})
previos = d.get("users", []) if isinstance(d, dict) else []
TEST_USERS = {"laura", "pedro"}
borrados = 0
for u in previos:
    if u.get("username") in TEST_USERS:
        req("DELETE", f"/api/admin/users/{u['id']}", headers={"X-Igris-Key": ADMIN_KEY})
        borrados += 1
check(f"usuarios de prueba eliminados ({borrados})", True)

# ------------------------------------------------- 3. SEPARACIÓN DE SUPERFICIES
print("\n3) Las dos superficies no se mezclan")
s, d = req("GET", "/api/admin/users")
check("admin sin clave -> 401", s == 401, f"(status {s})")

# ------------------------------------------------------------- 3. CREAR USUARIO
print("\n4) Crear usuarios desde el panel")
s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "laura", "email": "laura@zottagroup.com", "password": "claveSegura123"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("crear laura -> 201", s == 201, f"(status {s} {d})")
laura_id = d.get("id") if isinstance(d, dict) else None
check("la respuesta NO incluye el hash", isinstance(d, dict) and "password_hash" not in d)

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "pedro", "email": "pedro@zottagroup.com", "password": "otraClave456"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("crear pedro -> 201", s == 201, f"(status {s} {d})")

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "laura", "email": "otro@zottagroup.com", "password": "claveSegura123"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("usuario duplicado -> 409", s == 409, f"(status {s})")

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "ab", "email": "ab@zottagroup.com", "password": "claveSegura123"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("usuario demasiado corto -> 422", s == 422, f"(status {s})")

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "corto", "email": "corto@zottagroup.com", "password": "123"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("contraseña corta -> 422", s == 422, f"(status {s})")

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "malcorreo", "email": "no-es-un-correo", "password": "claveSegura123"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("correo inválido -> 422", s == 422, f"(status {s})")

# ---------------------------------------------------------------- 4. LOGIN
print("\n5) Acceso de usuarios")
s, d = req("POST", "/api/user/login", {"username": "laura", "password": "claveSegura123"})
check("laura entra -> 200", s == 200, f"(status {s} {d})")
laura_token = d.get("access_token") if isinstance(d, dict) else None
check("devuelve token", bool(laura_token))
check("el rol del usuario NO es admin", isinstance(d, dict) and not d.get("user", {}).get("is_admin"))

s, d = req("POST", "/api/user/login", {"username": "laura", "password": "incorrecta"})
check("contraseña incorrecta -> 401", s == 401, f"(status {s})")

s, d = req("POST", "/api/user/login", {"username": "noexiste", "password": "loquesea"})
msg_noexiste = d.get("detail") if isinstance(d, dict) else None
check("usuario inexistente -> 401", s == 401, f"(status {s})")

s2, d2 = req("POST", "/api/user/login", {"username": "laura", "password": "incorrecta"})
check(
    "mismo mensaje para usuario inexistente y contraseña mala",
    msg_noexiste == (d2.get("detail") if isinstance(d2, dict) else None),
    f"({msg_noexiste!r} vs {d2.get('detail')!r})",
)

# ------------------------------------------------------------ 5. TOKEN DE USUARIO
print("\n6) El token del usuario")
AUTH = {"Authorization": f"Bearer {laura_token}"}

s, d = req("GET", "/api/user/me", headers=AUTH)
check("token válido -> 200", s == 200, f"(status {s})")
check("devuelve a laura", isinstance(d, dict) and d.get("username") == "laura")

s, d = req("GET", "/api/user/me")
check("sin token -> 401", s == 401, f"(status {s})")

s, d = req("GET", "/api/user/me", headers={"Authorization": "Bearer inventado"})
check("token inventado -> 401", s == 401, f"(status {s})")

# Token firmado por nosotros con role=admin: debe seguir siendo rechazado en
# /api/user (el rol tiene que ser "user") y no servir como admin.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jose import jwt  # noqa: E402

from core.auth import ALGORITHM, SECRET_KEY  # noqa: E402

forged = jwt.encode({"user_id": laura_id, "role": "admin"}, SECRET_KEY, algorithm=ALGORITHM)
s, d = req("GET", "/api/admin/users", headers={"X-Igris-Key": forged})
check("token forjado como clave de admin -> 401", s == 401, f"(status {s})")

s, d = req("GET", "/api/user/me", headers={"Authorization": f"Bearer {forged}"})
check("token con role=admin en /api/user -> 401", s == 401, f"(status {s})")

# La clave de admin no vale como token de usuario
s, d = req("GET", "/api/user/me", headers={"Authorization": f"Bearer {ADMIN_KEY}"})
check("la clave de admin como token -> 401", s == 401, f"(status {s})")

# El token de usuario no vale como clave de admin
s, d = req("GET", "/api/admin/users", headers={"X-Igris-Key": laura_token})
check("el token de usuario como clave -> 401", s == 401, f"(status {s})")

# ------------------------------------------------------------------ 6. CHAT
print("\n7) El chat de cada usuario")
s, d = req("POST", "/api/user/chat", {"text": ""}, AUTH)
check("mensaje vacío -> 422", s == 422, f"(status {s})")

s, d = req("POST", "/api/user/chat", {"text": "hola"})
check("chat sin token -> 401", s == 401, f"(status {s})")

s, d = req("POST", "/api/user/chat", {"text": "hola", "session_id": "abc"}, AUTH)
check("chat con token -> 200", s == 200, f"(status {s})")
# Sin proveedores de IA configurados responderá status=error con su motivo:
# lo que se valida es que la ruta funciona y llega al cerebro.
check("la ruta del chat responde", s == 200 and isinstance(d, dict) and "status" in d)

# ------------------------------------------------------------------ 7. CORS
print("\n8) CORS (lo que rompía el área de usuarios)")
ORIGIN = "https://webigris.zottagroup.com"


def preflight(path, method, header_name):
    """Simula el preflight que hace el navegador antes de una petición real."""
    r = urllib.request.Request(
        BASE + path,
        method="OPTIONS",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": header_name,
        },
    )
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)


for path, method, hdr in [
    ("/api/user/login", "POST", "content-type"),
    ("/api/user/me", "GET", "authorization"),
    ("/api/user/chat", "POST", "authorization,content-type"),
    ("/api/user/tts", "POST", "authorization"),
    ("/api/admin/users", "DELETE", "x-igris-key"),
    ("/api/admin/users", "PUT", "x-igris-key,content-type"),
    ("/api/chat", "POST", "x-igris-key"),
]:
    s, h = preflight(path, method, hdr)
    allow = h.get("access-control-allow-headers", "").lower()
    ok = s in (200, 204)
    wanted = [x.strip() for x in hdr.split(",")]
    ok = ok and all(w in allow for w in wanted)
    check(f"preflight {method} {path} ({hdr})", ok, f"(status {s}, allow-headers {allow!r})")

# Un origen no autorizado no debe recibir permiso
s, h = preflight("/api/user/login", "POST", "content-type")
r = urllib.request.Request(
    BASE + "/api/user/login",
    method="OPTIONS",
    headers={
        "Origin": "https://sitio-malicioso.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    },
)
try:
    with urllib.request.urlopen(r, timeout=10) as resp:
        s_bad, h_bad = resp.status, dict(resp.headers)
except urllib.error.HTTPError as e:
    s_bad, h_bad = e.code, dict(e.headers)
check(
    "origen no autorizado rechazado",
    h_bad.get("access-control-allow-origin") != "https://sitio-malicioso.com",
    f"(status {s_bad}, allow-origin {h_bad.get('access-control-allow-origin')!r})",
)

# Las respuestas de error también necesitan la cabecera CORS: sin ella, una
# contraseña incorrecta se vería en pantalla como un fallo de red.
s, d = req(
    "POST",
    "/api/user/login",
    {"username": "laura", "password": "mala"},
    {"Origin": ORIGIN},
)
r = urllib.request.Request(
    BASE + "/api/user/login",
    data=json.dumps({"username": "laura", "password": "mala"}).encode(),
    headers={"Content-Type": "application/json", "Origin": ORIGIN},
    method="POST",
)
try:
    with urllib.request.urlopen(r, timeout=10) as resp:
        h_err = dict(resp.headers)
except urllib.error.HTTPError as e:
    h_err = dict(e.headers)
check(
    "el 401 también lleva cabecera CORS",
    h_err.get("access-control-allow-origin") == ORIGIN,
    f"(allow-origin {h_err.get('access-control-allow-origin')!r})",
)

# ------------------------------------------------- 8. DESACTIVAR UN USUARIO
print("\n9) Desactivar un usuario")
s, d = req(
    "PUT",
    f"/api/admin/users/{laura_id}",
    {"is_active": False},
    {"X-Igris-Key": ADMIN_KEY},
)
check("desactivar -> 200", s == 200, f"(status {s})")
check("queda inactiva", isinstance(d, dict) and d.get("is_active") is False)

s, d = req("POST", "/api/user/login", {"username": "laura", "password": "claveSegura123"})
check("usuario desactivado no entra -> 403", s == 403, f"(status {s})")

s, d = req("GET", "/api/user/me", headers=AUTH)
check("su token deja de valer -> 403", s == 403, f"(status {s})")

s, d = req(
    "PUT",
    f"/api/admin/users/{laura_id}",
    {"is_active": True},
    {"X-Igris-Key": ADMIN_KEY},
)
check("reactivar -> 200", s == 200, f"(status {s})")

s, d = req("POST", "/api/user/login", {"username": "laura", "password": "claveSegura123"})
check("vuelve a entrar -> 200", s == 200, f"(status {s})")
laura_token = d.get("access_token") if isinstance(d, dict) else None
AUTH = {"Authorization": f"Bearer {laura_token}"}

# ------------------------------------------------- 9. CAMBIAR CONTRASEÑA
print("\n10) Cambiar la contraseña desde el panel")
s, d = req(
    "PUT",
    f"/api/admin/users/{laura_id}",
    {"password": "nuevaClave789"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("cambiar contraseña -> 200", s == 200, f"(status {s})")

s, d = req("POST", "/api/user/login", {"username": "laura", "password": "claveSegura123"})
check("la contraseña vieja ya no vale -> 401", s == 401, f"(status {s})")

s, d = req("POST", "/api/user/login", {"username": "laura", "password": "nuevaClave789"})
check("la contraseña nueva sí vale -> 200", s == 200, f"(status {s})")

# --------------------------------------------- 10. AISLAMIENTO DEL HISTORIAL
print("\n11) El historial de cada usuario está aislado")
sessions_mod = __import__("core.session_store", fromlist=["SessionStore"])
import server.user_routes as ur  # noqa: E402

k1 = ur._session_key(1, "abc")
k2 = ur._session_key(2, "abc")
check("el mismo id de conversación NO da la misma clave a dos usuarios", k1 != k2, f"({k1} vs {k2})")
check("la clave lleva el id del usuario", k1.startswith("user:1:"))

k3 = ur._session_key(1, "../../etc/passwd")
check("un id de conversación con caracteres raros se limpia", "/" not in k3 and ".." not in k3, f"({k3})")
check("nunca queda vacío", ur._session_key(1, "") == "user:1:default")

# ------------------------------------------------- 11. LIMITE DE INTENTOS
print("\n12) Límite de intentos del login de usuarios")
for i in range(10):
    req("POST", "/api/user/login", {"username": "pedro", "password": f"mala{i}"})
s, d = req("POST", "/api/user/login", {"username": "pedro", "password": "otraClave456"})
check("tras varios fallos -> 429", s == 429, f"(status {s})")
# El bloqueo es por IP+usuario: otro usuario sigue pudiendo entrar
s, d = req("POST", "/api/user/login", {"username": "laura", "password": "nuevaClave789"})
check("otro usuario no queda bloqueado -> 200", s == 200, f"(status {s})")

# --------------------------------------------------------- 12. ELIMINAR
print("\n13) Eliminar un usuario")
s, d = req("DELETE", f"/api/admin/users/{laura_id}", headers={"X-Igris-Key": ADMIN_KEY})
check("eliminar -> 200", s == 200, f"(status {s})")

s, d = req("POST", "/api/user/login", {"username": "laura", "password": "nuevaClave789"})
check("ya no puede entrar -> 401", s == 401, f"(status {s})")

s, d = req("DELETE", "/api/admin/users/999999", headers={"X-Igris-Key": ADMIN_KEY})
check("eliminar uno que no existe -> 404", s == 404, f"(status {s})")

# ------------------------------------------- 13. PERMISOS POR FUNCIÓN
# Lo que de verdad importa de esta parte: que las herramientas NO se puedan usar
# aunque el modelo las llame. La comprobación tiene que ser del servidor.
print("\n14) Permisos por función (lo comprueba el SERVIDOR, no el prompt)")
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

s, d = req("GET", "/api/admin/features", headers={"X-Igris-Key": ADMIN_KEY})
check("catálogo de funciones -> 200", s == 200, f"(status {s})")
claves = {f["key"] for f in (d.get("features") or [])}
check("el catálogo trae las siete funciones",
      {"time", "weather", "email", "calendar", "calendar_write", "notes", "reminders"} <= claves,
      f"({sorted(claves)})")

# Usuario nuevo: por defecto solo hora y clima
s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "limitado", "email": "limitado@zottagroup.com", "password": "claveSegura123"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("crear usuario con permisos por defecto -> 201", s == 201, f"(status {s} {d})")
limitado_id = d.get("id") if isinstance(d, dict) else None
check("por defecto solo hora y clima",
      set(d.get("features") or []) == {"time", "weather"}, f"({d.get('features')})")

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "sinFunciones", "email": "sinfunciones@zottagroup.com",
     "password": "claveSegura123", "features": []},
    {"X-Igris-Key": ADMIN_KEY},
)
check("se puede crear un usuario sin ninguna función -> 201", s == 201, f"(status {s} {d})")
sin_funciones_id = d.get("id") if isinstance(d, dict) else None
check("la lista vacía se respeta (no se rellena con las de fábrica)",
      (d.get("features") or []) == [], f"({d.get('features')})")

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "malaFuncion", "email": "mala@zottagroup.com",
     "password": "claveSegura123", "features": ["telepatia"]},
    {"X-Igris-Key": ADMIN_KEY},
)
check("una función desconocida se rechaza -> 422", s == 422, f"(status {s})")

# El catálogo de capacidades en Python tiene que coincidir con lo que ve el panel
from core.capabilities import (            # noqa: E402
    FEATURES, TOOL_FEATURES, Capabilities, admin_capabilities, denial_message, tools_for,
)
from core.tools import TOOLS               # noqa: E402

nombres_esquema = {t["function"]["name"] for t in TOOLS}
check("toda herramienta del esquema tiene función asignada",
      nombres_esquema <= set(TOOL_FEATURES), f"(faltan {nombres_esquema - set(TOOL_FEATURES)})")
check("cada función del mapa existe en FEATURES",
      set(TOOL_FEATURES.values()) <= set(FEATURES),
      f"({set(TOOL_FEATURES.values()) - set(FEATURES)})")

# --- La comprobación que de verdad protege ---
import asyncio         # noqa: E402
from core.tools import run_tool   # noqa: E402

caps_limitado = Capabilities(user_id=1, features=frozenset({"time", "weather"}))


class _Sesion:
    """Sesión mínima para probar run_tool (no hace falta base de datos)."""
    user_id = 1
    capabilities = caps_limitado
    turn_no = 1
    last_user_text = ""


async def _intentos():
    resultados = {}
    for herramienta, argumentos in [
        ("add_note", '{"text": "una nota"}'),
        ("list_notes", "{}"),
        ("delete_note", '{"id": 1}'),
        ("create_reminder", '{"text": "x", "when": "2030-01-01T10:00"}'),
        ("list_reminders", "{}"),
        ("list_emails", "{}"),
        ("read_email", '{"message_id": "abc"}'),
        ("list_events", "{}"),
        ("propose_event", '{"title": "x", "start": "2030-01-01T10:00"}'),
        ("confirm_event", "{}"),
    ]:
        resultados[herramienta] = await run_tool(herramienta, argumentos, _Sesion())
    return resultados


bloqueos = asyncio.run(_intentos())
for herramienta, salida in bloqueos.items():
    check(f"'{herramienta}' queda bloqueada por permisos",
          "no tiene habilitada" in salida or "no está disponible" in salida,
          f"({salida[:90]})")

check("las herramientas permitidas NO se bloquean por permisos",
      "no tiene habilitada" not in asyncio.run(run_tool("get_time", "{}", _Sesion())))

# Sin sesión (panel del administrador) todo sigue permitido
check("sin sesión no se bloquea nada (panel del admin)",
      "no tiene habilitada" not in asyncio.run(run_tool("list_notes", "{}", None)))

# El filtrado de herramientas que ve el modelo
todas = {t["function"]["name"] for t in tools_for(None)}
solo_basicas = {t["function"]["name"] for t in tools_for(caps_limitado)}
check("sin capacidades el modelo ve todas las herramientas",
      todas == nombres_esquema, f"({len(todas)} vs {len(nombres_esquema)})")
check("con permisos limitados el modelo solo ve hora y clima",
      solo_basicas == {"get_time", "get_weather"}, f"({sorted(solo_basicas)})")
check("el administrador tiene todas las funciones",
      admin_capabilities().features == frozenset(FEATURES))
check("el mensaje de denegación nombra la función",
      "Notas" in denial_message("add_note", caps_limitado))

# Ninguna herramienta visible cuando no hay funciones
vacio = Capabilities(user_id=1, features=frozenset())
check("con cero funciones no queda ninguna herramienta visible",
      tools_for(vacio) == [], f"({[t['function']['name'] for t in tools_for(vacio)]})")

# --- El administrador puede cambiar los permisos de un usuario existente ---
s, d = req(
    "PUT",
    f"/api/admin/users/{limitado_id}",
    {"features": ["time", "weather", "notes", "reminders"]},
    {"X-Igris-Key": ADMIN_KEY},
)
check("cambiar funciones -> 200", s == 200, f"(status {s} {d})")
check("las funciones nuevas se guardan",
      set(d.get("features") or []) == {"time", "weather", "notes", "reminders"},
      f"({d.get('features')})")

# El login tiene que devolver las funciones: el frontend las usa
s, d = req("POST", "/api/user/login", {"username": "limitado", "password": "claveSegura123"})
token_limitado = d.get("access_token") if isinstance(d, dict) else None
check("el login devuelve las funciones del usuario",
      set((d.get("user") or {}).get("features") or []) ==
      {"time", "weather", "notes", "reminders"}, f"({(d.get('user') or {}).get('features')})")

s, d = req("GET", "/api/user/connections", headers={"Authorization": f"Bearer {token_limitado}"})
check("el usuario consulta sus conexiones -> 200", s == 200, f"(status {s})")
check("las conexiones no exponen ningún token",
      "refresh_token" not in json.dumps(d) and "token_enc" not in json.dumps(d))
check("las conexiones dicen qué funciones tiene",
      set(d.get("features") or []) == {"time", "weather", "notes", "reminders"}, f"({d.get('features')})")
check("Google sale como no conectado", d.get("google", {}).get("connected") is False)
check("Telegram sale como no vinculado", d.get("telegram", {}).get("linked") is False)

# ------------------------------------------- 14. VINCULACIÓN DE TELEGRAM
print("\n15) Vinculación de Telegram")
s, d = req("POST", "/api/user/telegram/code", headers={"Authorization": f"Bearer {token_limitado}"})
check("pedir código de vinculación -> 200", s == 200, f"(status {s} {d})")
codigo = d.get("code") if isinstance(d, dict) else None
check("el código tiene seis dígitos", bool(codigo) and len(codigo) == 6 and codigo.isdigit(), f"({codigo})")

from core import telegram_links     # noqa: E402

uid, msg = telegram_links.link_chat(codigo, 555001, "limitado_tg")
check("vincular el chat con el código -> funciona", uid is not None, f"({msg})")
check("el chat queda resuelto a ese usuario",
      (telegram_links.resolve_user(555001) or None) is not None)
check("un chat sin vincular no resuelve a nadie", telegram_links.resolve_user(999999) is None)

uid2, msg2 = telegram_links.link_chat(codigo, 555002, "otro")
check("el código es de un solo uso", uid2 is None, f"({msg2})")

uid3, msg3 = telegram_links.link_chat("000000", 555003, "intruso")
check("un código inventado no vincula a nadie", uid3 is None, f"({msg3})")

s, d = req("GET", "/api/user/connections", headers={"Authorization": f"Bearer {token_limitado}"})
check("las conexiones ya muestran el Telegram vinculado",
      d.get("telegram", {}).get("linked") is True, f"({d.get('telegram')})")

# El chat pasa a resolver con los permisos y los datos de SU usuario
from core.capabilities import capabilities_from_user   # noqa: E402
from core.database import User as _User, SessionLocal as _SL   # noqa: E402
with _SL() as _db:
    _u = _db.query(_User).filter(_User.username == "limitado").first()
    _caps_usuario = capabilities_from_user(_u)
check("las capacidades del chat vinculado son las del usuario",
      _caps_usuario.features == frozenset({"time", "weather", "notes", "reminders"}),
      f"({_caps_usuario.features})")
check("el chat vinculado identifica al usuario correcto", _caps_usuario.user_id == limitado_id)

s, d = req("DELETE", "/api/user/telegram", headers={"Authorization": f"Bearer {token_limitado}"})
check("desvincular Telegram -> 200", s == 200, f"(status {s})")
check("el chat ya no resuelve a nadie", telegram_links.resolve_user(555001) is None)

# ------------------------------------------- 15. AISLAMIENTO DE DATOS
print("\n16) Las notas y los recordatorios son de cada usuario")
from core.tools import notes as _notes, reminders as _rem    # noqa: E402


class _SesionUsuario:
    def __init__(self, user_id, caps):
        self.user_id = user_id
        self.capabilities = caps
        self.turn_no = 1
        self.last_user_text = "borra la nota"
        self.telegram_id = None


async def _datos():
    caps_a = Capabilities(user_id=limitado_id, features=frozenset({"notes", "reminders"}))
    caps_b = Capabilities(user_id=_caps_usuario.user_id, features=frozenset({"notes", "reminders"}))
    a = _SesionUsuario(limitado_id, caps_a)
    b = _SesionUsuario(sin_funciones_id, caps_b)

    ra = await _notes.add_note("secreto de limitado", a)
    rb = await _notes.add_note("secreto de sinFunciones", b)

    lista_a = await _notes.list_notes(a)
    lista_b = await _notes.list_notes(b)

    # A intenta borrar la nota de B usando su id
    robo = await _notes.delete_note(rb["id"], a)

    # Recordatorios
    rr_a = await _rem.create_reminder("aviso de limitado", "2030-06-01T09:00", None, a)
    lista_ra = await _rem.list_reminders(a)
    lista_rb = await _rem.list_reminders(b)
    robo_r = await _rem.delete_reminder(rr_a["id"], b) if rr_a.get("id") else {"error": "sin id"}
    return ra, rb, lista_a, lista_b, robo, rr_a, lista_ra, lista_rb, robo_r


ra, rb, lista_a, lista_b, robo, rr_a, lista_ra, lista_rb, robo_r = asyncio.run(_datos())

check("cada usuario ve SOLO sus notas",
      all(n["id"] != rb["id"] for n in lista_a["notas"]) and
      all(n["id"] != ra["id"] for n in lista_b["notas"]),
      f"(A ve {[n['id'] for n in lista_a['notas']]}, B ve {[n['id'] for n in lista_b['notas']]})")
check("un usuario NO puede borrar la nota de otro",
      "error" in robo and robo.get("id") != rb["id"], f"({robo})")
check("la nota del otro sigue existiendo tras el intento",
      asyncio.run(_notes.list_notes(_SesionUsuario(
          sin_funciones_id, Capabilities(user_id=sin_funciones_id, features=frozenset({"notes"}))
      )))["total"] >= 1)
check("cada usuario ve SOLO sus recordatorios",
      all(r["id"] != rr_a["id"] for r in lista_rb.get("recordatorios", [])) or
      lista_rb.get("total", 0) == 0, f"({lista_rb})")
check("un usuario NO puede cancelar el recordatorio de otro", "error" in robo_r, f"({robo_r})")

# Sin usuario no se escribe nada (no se puede saber de quién sería el dato)
sin_usuario = _SesionUsuario(None, None)
r_sin = asyncio.run(_notes.add_note("no debería guardarse", sin_usuario))
check("sin usuario identificado no se guarda una nota", "error" in r_sin, f"({r_sin})")
r_sin2 = asyncio.run(_rem.create_reminder("x", "2030-01-01T10:00", None, sin_usuario))
check("sin usuario identificado no se crea un recordatorio", "error" in r_sin2, f"({r_sin2})")

# ------------------------------------------- 16. CIFRADO
print("\n17) Cifrado del refresh token de Google")
from core import crypto    # noqa: E402

original = "1//0abcdefghijklmnop-refresh-token-de-prueba"
cifrado = crypto.encrypt(original)
check("el token cifrado no contiene el original", original not in cifrado)
check("el token se descifra igual", crypto.decrypt(cifrado) == original)
check("dos cifrados del mismo token son distintos (llevan nonce)",
      crypto.encrypt(original) != cifrado)
check("cifrar None no revienta", crypto.encrypt(None) is None)
check("descifrar basura devuelve None (no lanza)",
      crypto.decrypt("esto-no-es-un-token-valido") is None)

# ------------------------------------------- 17. GOOGLE
print("\n18) Google: cada usuario necesita SU cuenta")
from core.tools import google_client as _gc    # noqa: E402

check("los permisos de Google se piden solo para lo habilitado",
      _gc.scopes_for({"time"}) == [_gc.SCOPE_IDENTITY], f"({_gc.scopes_for({'time'})})")
check("'email' añade el permiso de Gmail",
      _gc.SCOPE_EMAIL in _gc.scopes_for({"email"}))
check("'calendar' añade el de lectura de calendario",
      _gc.SCOPE_CALENDAR_READ in _gc.scopes_for({"calendar"}))
check("'calendar_write' añade el de escritura",
      _gc.SCOPE_CALENDAR_WRITE in _gc.scopes_for({"calendar_write"}))
check("a quien no tiene escritura NO se le pide ese permiso",
      _gc.SCOPE_CALENDAR_WRITE not in _gc.scopes_for({"calendar"}))

# Un usuario normal sin cuenta conectada recibe un error claro, no el correo de otro.
# Se simula que el servidor SÍ tiene sus credenciales de aplicación (como en el
# despliegue real): así lo que se prueba es el caso del usuario, no el del servidor.
_gc.client_config_original = _gc.client_config
_gc.client_config = lambda: ("id-de-prueba.apps.googleusercontent.com", "secreto-de-prueba")
try:
    _gc.resolve_credentials(limitado_id)
    check("un usuario sin cuenta conectada no obtiene credenciales", False, "(no lanzó)")
except _gc.GoogleNotConfigured as e:
    # El aviso tiene que decirle al usuario QUÉ hacer; si no, se queda sin correo
    # ni calendario y sin saber por qué.
    check("un usuario sin cuenta conectada recibe un aviso claro",
          "conectado" in str(e) and "Conexiones" in str(e), f"({e})")

# Si el servidor no tiene las credenciales de aplicación, el problema NO es del
# usuario: decirle "no has conectado" le haría buscar algo que nunca podrá hacer.
_gc.client_config = lambda: (None, None)
try:
    _gc.resolve_credentials(limitado_id)
    check("sin configurar en el servidor no se culpa al usuario", False, "(no lanzó)")
except _gc.GoogleNotConfigured as e:
    check("sin configurar en el servidor se avisa de la configuración",
          "servidor" in str(e) and "GOOGLE_CLIENT_ID" in str(e), f"({e})")

# Con la cuenta guardada pero ILEGIBLE (cambió SECRET_KEY), el mensaje debe decir
# que vuelva a conectarla, no que nunca la conectó.
from core.database import GoogleAccount as _GA, SessionLocal as _SL    # noqa: E402
_gc.client_config = _gc.client_config_original
_gc.client_config = lambda: ("id-de-prueba.apps.googleusercontent.com", "secreto-de-prueba")
with _SL() as _db:
    _db.query(_GA).filter(_GA.user_id == limitado_id).delete(synchronize_session=False)
    _db.add(_GA(user_id=limitado_id, refresh_token_enc="token-que-no-se-puede-descifrar"))
    _db.commit()
try:
    _gc.resolve_credentials(limitado_id)
    check("con cuenta ilegible no se obtienen credenciales", False, "(no lanzó)")
except _gc.GoogleNotConfigured as e:
    check("con cuenta ilegible se pide reconectar (no se dice que nunca conectó)",
          "vuelve a conectarla" in str(e) and "No has conectado" not in str(e), f"({e})")
finally:
    _gc.client_config = _gc.client_config_original
with _SL() as _db:
    _db.query(_GA).filter(_GA.user_id == limitado_id).delete(synchronize_session=False)
    _db.commit()

# ------------------------------------------- 18. AVISOS EN HTML
print("\n19) El aviso que Google devuelve no puede inyectar HTML")
import re as _re    # noqa: E402

_fuente = open(os.path.join(os.path.dirname(__file__), "..", "server", "user_routes.py"),
               encoding="utf-8").read()
_cb = _fuente[_fuente.index("def google_callback"):]
_cb = _cb[:_cb.index("\ndef ", 10)] if "\ndef " in _cb[10:] else _cb
check("el título se escapa", "escape(title)" in _cb)
check("el detalle se escapa", "escape(detail)" in _cb)
check("se importa 'escape'", "from html import escape" in _cb)

# ------------------------------------------- 20. LIMPIEZA FINAL
for uid_borrar in (limitado_id, sin_funciones_id):
    if uid_borrar:
        req("DELETE", f"/api/admin/users/{uid_borrar}", headers={"X-Igris-Key": ADMIN_KEY})

# ---------------------------------------------------------------- RESUMEN
print(f"\n{'='*58}")
print(f"  RESULTADO: {passed} pruebas superadas, {len(failed)} fallidas")
if failed:
    print("\n  Fallidas:")
    for f in failed:
        print(f"    - {f}")
print(f"{'='*58}\n")

sys.exit(1 if failed else 0)

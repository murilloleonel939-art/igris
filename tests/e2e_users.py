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

# ---------------------------------------------------------------- RESUMEN
print(f"\n{'='*58}")
print(f"  RESULTADO: {passed} pruebas superadas, {len(failed)} fallidas")
if failed:
    print("\n  Fallidas:")
    for f in failed:
        print(f"    - {f}")
print(f"{'='*58}\n")

sys.exit(1 if failed else 0)

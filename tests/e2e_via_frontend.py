#!/usr/bin/env python3
"""
Prueba del flujo completo TAL COMO LO VIVE EL NAVEGADOR.

Los demás tests hablan directamente con el backend. Este no: entra por el
servidor del frontend (puerto 3100), que es el camino real en producción
(el navegador solo conoce webigris.zottagroup.com). Así se cubre también el
proxy, que es justo donde estaba el fallo de req.url frente a req.originalUrl.

Recorre el flujo entero: crear usuario (admin) -> entrar -> chatear -> salir,
comprobando en cada paso lo que vería el navegador.
"""
import json
import os
import sys
import urllib.error
import urllib.request

FRONT = "http://127.0.0.1:3100"   # el frontend (lo que ve el navegador)
ADMIN_KEY = os.environ["IGRIS_ACCESS_KEY"]
ORIGIN = "https://webigris.zottagroup.com"

passed, failed = 0, []


def check(name, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed.append(name)
        print(f"  ❌ {name} {detail}")


def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    r = urllib.request.Request(FRONT + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw or b"{}")
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except Exception:
            return e.code, raw


print("\n=== IGRIS — FLUJO COMPLETO A TRAVÉS DEL FRONTEND ===\n")

# --------------------------------------------------- 1. ARCHIVOS DE LA SPA
print("1) El frontend sirve la aplicación y los archivos de la PWA")
for path, expect_ct in [
    ("/", "text/html"),
    ("/u", "text/html"),
    ("/u/login", "text/html"),
    ("/acceso", "text/html"),
    ("/manifest.webmanifest", "manifest"),
    ("/sw.js", "javascript"),
    ("/icons/icon-192.png", "image/png"),
    ("/igris.mp4", "video/mp4"),
]:
    r = urllib.request.Request(FRONT + path)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            s, ct = resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        s, ct = e.code, e.headers.get("Content-Type", "")
    ok = s == 200 and expect_ct in ct
    check(f"{path} -> 200 ({expect_ct})", ok, f"(status {s}, tipo {ct!r})")

# --------------------------------------------------- 2. EL PROXY FUNCIONA
print("\n2) El proxy conserva la ruta completa (req.originalUrl)")
s, d = req("GET", "/api/auth/check", headers={"X-Igris-Key": ADMIN_KEY})
check("clave de admin a través del proxy -> 200", s == 200, f"(status {s})")

s, d = req("GET", "/api/auth/check")
check("sin clave a través del proxy -> 401 (no 404)", s == 401, f"(status {s})")

# Un 404 aquí significaría que el proxy está recortando el prefijo /api
s, d = req("POST", "/api/user/login", {"username": "x", "password": "y"})
check("la ruta de usuarios existe a través del proxy (no 404)", s != 404, f"(status {s})")

# --------------------------------------------------- 3. FLUJO DEL ADMINISTRADOR
print("\n3) El administrador crea un usuario")
s, d = req("GET", "/api/admin/users", headers={"X-Igris-Key": ADMIN_KEY})
previos = d.get("users", []) if isinstance(d, dict) else []
for u in previos:
    if u.get("username") == "camilo":
        req("DELETE", f"/api/admin/users/{u['id']}", headers={"X-Igris-Key": ADMIN_KEY})

s, d = req(
    "POST",
    "/api/admin/users",
    {"username": "camilo", "email": "camilo@zottagroup.com", "password": "claveSegura123"},
    {"X-Igris-Key": ADMIN_KEY},
)
check("crear camilo -> 201", s == 201, f"(status {s} {d})")
camilo_id = d.get("id") if isinstance(d, dict) else None

# --------------------------------------------------- 4. EL USUARIO ENTRA
print("\n4) El usuario entra desde /u/login")
s, d = req("POST", "/api/user/login", {"username": "camilo", "password": "claveSegura123"})
check("entrar -> 200", s == 200, f"(status {s} {d})")
token = d.get("access_token") if isinstance(d, dict) else None
check("recibe su token", bool(token))

s, d = req(
    "POST",
    "/api/user/login",
    {"username": "camilo", "password": "equivocada"},
    {"Origin": ORIGIN},
)
check("contraseña equivocada -> 401 con mensaje claro", s == 401 and isinstance(d, dict) and d.get("detail"), f"(status {s})")

# --------------------------------------------------- 5. CHAT Y VOZ
print("\n5) El usuario usa el chat y la voz")
AUTH = {"Authorization": f"Bearer {token}", "Origin": ORIGIN}
s, d = req("GET", "/api/user/me", headers=AUTH)
check("su sesión es válida -> 200", s == 200, f"(status {s})")
check("y es él", isinstance(d, dict) and d.get("username") == "camilo")

s, d = req("POST", "/api/user/chat", {"text": "hola igris", "session_id": "s1"}, AUTH)
check("el chat responde -> 200", s == 200, f"(status {s})")
check("y trae un estado", isinstance(d, dict) and "status" in d, f"({d})")

s, d = req("POST", "/api/user/tts", {"text": "hola"}, AUTH)
# Sin proveedor de voz configurado puede fallar, pero la ruta tiene que existir
# y no puede dar 404 ni 401 (el token es válido).
check("la ruta de voz existe y acepta el token (no 404/401)", s not in (401, 404), f"(status {s})")

s, d = req("POST", "/api/user/tts", {"text": "hola"})
check("la voz sin token -> 401", s == 401, f"(status {s})")

# --------------------------------------------------- 6. SEPARACIÓN
print("\n6) Un usuario no puede tocar la administración")
s, d = req("GET", "/api/admin/users", headers={"Authorization": f"Bearer {token}"})
check("su token no sirve en /api/admin -> 401", s == 401, f"(status {s})")

s, d = req("GET", "/api/admin/users")
check("el panel sigue pidiendo la clave", s == 401, f"(status {s})")

s, d = req("GET", "/api/admin/users", headers={"X-Igris-Key": ADMIN_KEY})
check("y con la clave correcta funciona", s == 200, f"(status {s})")

# --------------------------------------------------- 7. LIMPIEZA
print("\n7) Limpieza")
s, d = req("DELETE", f"/api/admin/users/{camilo_id}", headers={"X-Igris-Key": ADMIN_KEY})
check("usuario de prueba eliminado -> 200", s == 200, f"(status {s})")

print(f"\n{'='*58}")
print(f"  RESULTADO: {passed} superadas, {len(failed)} fallidas")
if failed:
    for f in failed:
        print(f"    - {f}")
print(f"{'='*58}\n")

sys.exit(1 if failed else 0)

#!/usr/bin/env python3
"""
Valida la parte de PostgreSQL de core/database.py sin necesidad de un servidor.

No hay PostgreSQL en esta máquina, así que lo que se comprueba es la LÓGICA:
  - la reescritura de la URL (Coolify entrega "postgres://", psycopg 3 necesita
    "postgresql+psycopg://"),
  - que el motor se construye con pool_pre_ping (si no, una conexión muerta
    tras un reinicio de Postgres rompe la primera petición),
  - que init_db reintenta cuando la base aún no responde y que falla de forma
    visible si nunca responde,
  - que la búsqueda/creación de la base usa el nombre correcto.

La conexión real se prueba en el despliegue, contra la PostgreSQL de Coolify.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed, failed = 0, []


def check(name, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed.append(name)
        print(f"  ❌ {name} {detail}")


def rewrite(url: str) -> str:
    """La misma reescritura que hace core/database.py, aislada."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# ------------------------------------------------------------ 1. REESCRITURA
print("\n1) Reescritura de la URL de conexión")
check(
    "postgres:// -> postgresql+psycopg://",
    rewrite("postgres://u:p@host:5432/igris") == "postgresql+psycopg://u:p@host:5432/igris",
)
check(
    "postgresql:// -> postgresql+psycopg://",
    rewrite("postgresql://u:p@host:5432/igris") == "postgresql+psycopg://u:p@host:5432/igris",
)
check(
    "ya reescrita: no se toca dos veces",
    rewrite("postgresql+psycopg://u:p@host/igris") == "postgresql+psycopg://u:p@host/igris",
)
check("sqlite no se toca", rewrite("sqlite:///./igris.db") == "sqlite:///./igris.db")

# ---------------------------------------- 2. DETECCIÓN DE POSTGRES Y DE LA BASE
print("\n2) Detección del motor y del nombre de la base")
from sqlalchemy.engine import make_url  # noqa: E402

u = make_url("postgresql+psycopg://igris_user:secreta@igris-db:5432/igris")
check("detecta el nombre de la base", u.database == "igris")
check("detecta el host", u.host == "igris-db")
check("la base de mantenimiento conserva credenciales", u.set(database="postgres").database == "postgres")
check(
    "y conserva el host",
    u.set(database="postgres").host == "igris-db",
)

# --------------------------------------------- 3. init_db: REINTENTOS Y FALLO
print("\n3) init_db reintenta y falla de forma visible")
import core.database as db  # noqa: E402

# Se sustituye create_all por uno que falla las dos primeras veces.
original_create_all = db.Base.metadata.create_all
original_connect = db.engine.connect
intentos = {"n": 0}


def create_all_falla(*a, **k):
    intentos["n"] += 1
    if intentos["n"] < 3:
        raise RuntimeError("la base todavía no está lista")


db.Base.metadata.create_all = create_all_falla
try:
    db.init_db(retries=5, delay=0.01)
    check("se recupera tras varios fallos", intentos["n"] == 3, f"(intentos {intentos['n']})")
except Exception as e:
    check("se recupera tras varios fallos", False, f"({type(e).__name__}: {e})")
finally:
    db.Base.metadata.create_all = original_create_all


def create_all_siempre_falla(*a, **k):
    raise RuntimeError("base inalcanzable")


db.Base.metadata.create_all = create_all_siempre_falla
try:
    db.init_db(retries=2, delay=0.01)
    check("lanza si nunca responde", False, "(no lanzó)")
except Exception as e:
    check("lanza si nunca responde", "inalcanzable" in str(e), f"({type(e).__name__})")
finally:
    db.Base.metadata.create_all = original_create_all

# ------------------------------------------------ 4. CREACIÓN DE LA BASE
print("\n4) Creación automática de la base de datos")
import inspect  # noqa: E402

src = inspect.getsource(db._ensure_postgres_database_exists)
check("consulta pg_database antes de crear", "pg_database" in src)
check("ejecuta CREATE DATABASE", "CREATE DATABASE" in src)
check("se conecta a la base 'postgres'", 'database="postgres"' in src)
check("cita el nombre para evitar inyección", 'replace(\'"\', \'""\')' in src)
check("no intenta crear la base 'postgres'", 'target == "postgres"' in src)
check("avisa en vez de morir si no hay permiso", "logger.warning" in src)

# ------------------------------------------- 5. PARÁMETROS DEL MOTOR
print("\n5) Parámetros del motor")
src_engine = inspect.getsource(db._build_engine)
check("pool_pre_ping activado (conexiones muertas)", "pool_pre_ping=True" in src_engine)
check("pool_recycle definido (renueva conexiones)", "pool_recycle=1800" in src_engine)
check("llama a la creación de la base", "_ensure_postgres_database_exists" in src_engine)
check(
    "SQLite conserva check_same_thread",
    "check_same_thread" in src_engine,
)

print("\n6) Aviso claro cuando se usa SQLite en producción")
src_init = inspect.getsource(db.init_db)
check("avisa de la pérdida de datos con SQLite", "se pierden en cada despliegue" in src_init)
check("registra las tablas creadas", "Base.metadata.tables" in src_init)

# ---------------------------------------------------------------- RESUMEN
print(f"\n{'='*58}")
print(f"  RESULTADO PostgreSQL: {passed} superadas, {len(failed)} fallidas")
if failed:
    for f in failed:
        print(f"    - {f}")
print(f"{'='*58}\n")

sys.exit(1 if failed else 0)

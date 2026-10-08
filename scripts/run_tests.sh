#!/usr/bin/env bash
#
# run_tests.sh — Ejecuta las tres suites de IGRIS en el orden correcto.
#
# POR QUÉ HACE FALTA ESTE SCRIPT
#
# Las suites e2e_users.py y e2e_via_frontend.py hablan con un backend real, y
# las dos usan la MISMA base SQLite (igris_test.db). Si se levantan los dos
# backends a la vez (uno en 8000 para el frontend y otro en 8099 para el área
# de usuarios), ocurre esto:
#
#   - El segundo backend abre el archivo de base de datos.
#   - Si se borra la base para empezar limpio, el primer backend se queda con
#     el archivo viejo abierto (en Linux, borrar un archivo abierto no lo
#     elimina: sigue existiendo mientras alguien lo tenga abierto) y empieza a
#     fallar con "attempt to write a readonly database".
#   - Además los tests fallan de formas confusas: 500 al crear un usuario, 409
#     de "ya existe" para un usuario que se acababa de borrar...
#
# Por eso aquí se levanta UN SOLO backend cada vez, se borra la base antes de
# cada suite, y se para el backend antes de pasar a la siguiente.
#
# USO
#   scripts/run_tests.sh            # las cuatro suites
#   scripts/run_tests.sh users      # solo el área de usuarios
#   scripts/run_tests.sh frontend   # solo el frontend (necesita el frontend vivo)
#   scripts/run_tests.sh telegram   # solo Telegram y recordatorios
#   scripts/run_tests.sh postgres   # solo la parte de PostgreSQL
#
# Para la suite del frontend hace falta, además, el servidor del frontend:
#   cd web && PORT=3100 node server.js
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
RAIZ="$(pwd)"

PY="$RAIZ/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

if [ ! -f .env.test ]; then
  echo "Falta .env.test (hace falta IGRIS_ACCESS_KEY y SECRET_KEY)." >&2
  exit 1
fi

# Las variables del entorno de pruebas (clave de admin, clave de firma, base)
set -a
# shellcheck disable=SC1091
. ./.env.test
set +a

BASE_DATOS="$RAIZ/igris_test.db"
LOG_DIR="${TMPDIR:-/tmp}"

resultado_usuarios=SKIP
resultado_frontend=SKIP
resultado_postgres=SKIP
resultado_telegram=SKIP

# ---------------------------------------------------------------- utilidades

# Mata los backends de las pruebas.
#
# No se usa `ss -p` porque en este entorno NO devuelve el PID (hace falta
# privilegio), y sin PID el kill no haría nada: el backend viejo seguiría vivo
# con la base ya borrada y todo fallaría con "readonly database".
#
# Tampoco se usa `pgrep -f "uvicorn server.main"`: el propio comando del script
# contiene ese texto, así que pgrep encontraría su propia línea y se mataría a
# sí mismo. Se lee /proc, que es fiable: la línea de este script es
# "bash scripts/run_tests.sh" y nunca coincide con la de un backend.
parar_backends() {
  local pid cmd
  for pid in /proc/[0-9]*; do
    [ -r "$pid/cmdline" ] || continue
    cmd="$(tr '\0' ' ' < "$pid/cmdline" 2>/dev/null)" || continue
    case "$cmd" in
      *uvicorn*server.main*)
        local num="${pid#/proc/}"
        kill -9 "$num" 2>/dev/null && echo "   (parado el backend $num)"
        ;;
    esac
  done
  sleep 1
}

# ¿Sigue alguien escuchando en este puerto?
ocupado() {
  ss -ltn 2>/dev/null | grep -q ":$1 "
}

# Levanta un backend y espera a que responda.
# Un 401 en /api/auth/check es la señal de que está vivo: la ruta existe y pide
# la clave, que es justo lo que se espera sin enviarla.
arrancar_backend() {
  local puerto="$1" log="$2"

  # Si el puerto está ocupado, el uvicorn nuevo no arranca: se queda el viejo
  # (posiblemente con la base ya borrada) y los tests fallan sin motivo claro.
  if ocupado "$puerto"; then
    echo "   El puerto $puerto estaba ocupado; se libera antes de arrancar." >&2
    parar_backends
    if ocupado "$puerto"; then
      echo "   No se pudo liberar el puerto $puerto." >&2
      return 1
    fi
  fi

  setsid nohup "$PY" -m uvicorn server.main:app --host 0.0.0.0 --port "$puerto" \
    > "$log" 2>&1 < /dev/null &
  disown

  for _ in $(seq 1 40); do
    sleep 0.5
    local codigo
    codigo="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$puerto/api/auth/check" 2>/dev/null)"
    [ "$codigo" = "401" ] && return 0
  done
  echo "   El backend del puerto $puerto no arrancó (ver $log)" >&2
  return 1
}

limpiar_base() {
  parar_backends
  rm -f "$BASE_DATOS"
}

# Resumen: lee la línea "RESULTADO: N superadas, M fallidas" de cada suite.
resumir() {
  local log="$1"
  grep -a "RESULTADO" "$log" | tail -1 | sed 's/^ *//'
}

# ------------------------------------------------------------------- suites

suite_usuarios() {
  echo
  echo "=== 1/4 · Área de usuarios y panel  (puerto 8099) ==="
  limpiar_base
  arrancar_backend 8099 "$LOG_DIR/igris-test-8099.log" || { resultado_usuarios=FALLO; return 1; }

  "$PY" tests/e2e_users.py 2>&1 | tee "$LOG_DIR/igris-test-users.log" | tail -30
  resultado_usuarios="$(resumir "$LOG_DIR/igris-test-users.log")"

  parar_backends
  sleep 1
}

suite_frontend() {
  echo
  echo "=== 2/4 · Todo a través del frontend  (frontend 3100 + backend 8000) ==="

  if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:3100/ 2>/dev/null; then
    echo "   El frontend no está corriendo en el 3100."
    echo "   Levántalo en otra terminal con:  cd web && PORT=3100 node server.js"
    resultado_frontend="NO EJECUTADA (frontend apagado)"
    return 1
  fi

  limpiar_base
  arrancar_backend 8000 "$LOG_DIR/igris-test-8000.log" || { resultado_frontend=FALLO; return 1; }

  "$PY" tests/e2e_via_frontend.py 2>&1 | tee "$LOG_DIR/igris-test-frontend.log" | tail -30
  resultado_frontend="$(resumir "$LOG_DIR/igris-test-frontend.log")"

  parar_backends
  sleep 1
}

suite_postgres() {
  echo
  echo "=== 4/4 · PostgreSQL y arranque de la base  (sin servidor) ==="
  limpiar_base
  "$PY" tests/test_postgres.py 2>&1 | tee "$LOG_DIR/igris-test-postgres.log" | tail -30
  resultado_postgres="$(resumir "$LOG_DIR/igris-test-postgres.log")"
}

# Telegram y recordatorios: no necesita servidor (llama a las funciones
# directamente), pero SÍ que no haya un backend vivo usando la misma base.
suite_telegram() {
  echo
  echo "=== 3/4 · Telegram y recordatorios  (sin servidor) ==="
  parar_backends
  "$PY" tests/test_telegram.py 2>&1 | tee "$LOG_DIR/igris-test-telegram.log" | tail -30
  resultado_telegram="$(resumir "$LOG_DIR/igris-test-telegram.log")"
}

# ------------------------------------------------------------------- arranque

case "${1:-todo}" in
  users)    suite_usuarios ;;
  frontend) suite_frontend ;;
  telegram) suite_telegram ;;
  postgres) suite_postgres ;;
  todo)
    suite_usuarios
    suite_frontend
    suite_telegram
    suite_postgres
    ;;
  *)
    echo "Uso: $0 [todo|users|frontend|telegram|postgres]" >&2
    exit 2
    ;;
esac

echo
echo "============================================================"
echo "  RESUMEN"
echo "   · Área de usuarios : $resultado_usuarios"
echo "   · Frontend         : $resultado_frontend"
echo "   · Telegram         : $resultado_telegram"
echo "   · PostgreSQL       : $resultado_postgres"
echo "============================================================"
echo

# El script falla si alguna suite que SÍ se ejecutó dejó fallos. Las que no se
# ejecutaron (SKIP) o no se pudieron ejecutar no cuentan como fallo.
for r in "$resultado_usuarios" "$resultado_frontend" "$resultado_telegram" "$resultado_postgres"; do
  case "$r" in
    *", 0 fallidas"*) : ;;
    SKIP|*"NO EJECUTADA"*) : ;;
    *) exit 1 ;;
  esac
done
exit 0

# IGRIS — Plan único de arreglo y capacidad

Un solo documento. El orden de ejecución manda; el detalle técnico va dentro de cada bloque. Cuando algo está fuera de alcance, se dice aquí mismo.

---

## Situación de partida

**Objetivo:** 100+ usuarios simultáneos de voz y texto sin caídas, con Deepgram primario y local de respaldo.

**Lo que se midió:**

| Dato | Valor |
|---|---|
| RAM / CPU del host | 7.75 GB / 2 cores, sin límite de cgroup |
| PostgreSQL `max_connections` | 100 |
| Disco | 77 GB, 44 % libre, 6 % de inodos |
| STT en base de datos | `provider=deepgram`, `local_engine=faster-whisper`, `small`, `int8` |
| Verificación de voz | en cada turno, 4 sitios |
| JWT acceso / refresh | 30 min / 7 días |
| Sesiones | TTL 7200 s, máximo 200 por proceso |

**Causa de la caída con 2 usuarios:** `core/voice.py:19` carga NeMo TitaNet en una global sin lock. Dos turnos simultáneos cargan el modelo dos veces (800 MB). Descartadas por medición: disco lleno, inodos, swap. El cambio a local solo obligaba a reiniciar, y el reinicio resetea la global: por eso parecía culpa del STT.

**Lo que NO es alcanzable** (dicho aquí, sin remitir a otro sitio):

- **Local como STT primario para 100 usuarios:** imposible con 2 cores y tampoco con 6 vCPU. Requiere GPU.
- **hands-free:** fuera de este plan.
- **Ampliación a 6 vCPU / 12 GB:** no se hace ahora. El plan queda preparado para que al migrar solo cambien variables de entorno.

---

## Mapa de bloques

| Bloque | Resuelve | Riesgo | Toca voz/chat |
|---|---|---|---|
| **A — Estabilizar** | La caída con 2 usuarios | Muy bajo | Poco |
| **B — Ver** | Diagnosticar sin adivinar | Nulo | No |
| **C — Blindar** | Un fallo no tumba PostgreSQL | Bajo | No |
| **D — Higiene** | Disco y caché | Bajo | No |
| **E — Pool** | Login bloqueado | Medio | Sí |
| **F — Voz robusta** | Cola, fallback, capacidad | Alto | Sí |
| **G — Escalar** | Multi-worker, Redis | Alto | Sí |

Regla: **no se avanza de bloque si el anterior rompe `/health`.** Cada paso es un commit reversible.

Los bloques A–D son aditivos: no cambian el comportamiento actual y se pueden desplegar sin riesgo.

---

# BLOQUE A — Estabilizar la caída

No requiere tocar STT.

## A1 — Confirmar la causa

Buscar en los logs de Coolify de la ventana de la caída:

```text
EncDecSpeakerLabelModel
from_pretrained
Killed
```

Señal inequívoca: `from_pretrained` **dos veces** en menos de un segundo.

Alternativa sin reiniciar producción:

```bash
docker exec CONTENEDOR python -c "
import threading, time
from core.voice import _get_encoder
def w(n):
    t=time.time(); _get_encoder(); print(f'hilo {n}: {time.time()-t:.1f}s')
ts=[threading.Thread(target=w,args=(i,)) for i in range(2)]
[t.start() for t in ts]; [t.join() for t in ts]
"
```

Dos líneas de ~8 s = dos cargas = bug confirmado.

**Cierre:** causa identificada por escrito.

## A2 — Lock en `_get_encoder()` (`core/voice.py`)

```python
_encoder = None
_encoder_lock = threading.Lock()

def _get_encoder():
    global _encoder
    if _encoder is not None:
        return _encoder
    with _encoder_lock:
        if _encoder is None:
            ...  # cargar una sola vez
    return _encoder
```

- Doble comprobación: fuera (camino rápido) y dentro del lock.
- Lock de `threading`, no de `asyncio` (corre en un hilo del executor).
- Si la carga falla, dejar `None` para permitir reintento, sin bucle.
- Registrar duración de la carga.

**Cierre:** dos turnos simultáneos tras reiniciar → `from_pretrained` aparece una sola vez.

## A3 — Locks en las demás cargas diferidas

Mismo patrón en `core/stt.py:30` (whisper / faster-whisper) y `core/tts.py` (Piper). Todos usan "global None + cargar si None" sin protección.

**Cierre:** ninguna carga de modelo se duplica con peticiones concurrentes.

## A4 — Executor acotado

El executor por defecto son `min(32, cpu+4) = 6` hilos con 2 cores. Hay 34 llamadas a `to_thread()`.

- `ThreadPoolExecutor` explícito y configurable.
- Separar CPU pesada (STT, NeMo, TTS) de I/O (BD, HTTP).
- La saturación de voz no debe bloquear login ni `/health`.

**Cierre:** con voz saturada, `/health` y login siguen respondiendo.

---

# BLOQUE B — Ver

## B1 — `/health/deep`

Mantener `/health` liviano: `{"status":"ok","name":"igris"}`, sin BD ni STT, menos de 200 ms incluso con carga. Es lo que Coolify usa para decidir si el contenedor vive; si consulta la BD, un pool saturado provoca reinicios en cadena.

`/health/deep` (nuevo), con timeout total de 3 s:

- BD con `SELECT 1`.
- Pool: en uso, overflow, tamaño.
- Cola STT: workers, tamaño, en curso.
- Modelo local: no cargado / calentando / listo / error.
- Disco: libre %, archivos en `/app/tmp`.
- Redis, solo si está habilitado.

Nunca lanza descarga de modelo, nunca espera una transcripción. `200` si es usable, `503` solo si está inservible. No expone claves ni datos de usuario.

```json
{
  "status": "healthy",
  "db": {"ok": true, "latency_ms": 3},
  "pool": {"in_use": 4, "overflow": 0, "size": 20},
  "stt": {"provider": "deepgram", "queue": 0, "workers": 3, "local_model": "not_loaded"},
  "disk": {"free_pct": 56, "tmp_files": 3}
}
```

## B2 — `/api/stt-stats`

Protegido con credenciales de admin. Estado de cola y contadores. Nunca audio, texto reconocido ni tokens.

## B3 — HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1
```

`start-period=180s` cubre migraciones y reintentos de BD. En el panel de Coolify: ruta `/health`, intervalo 30 s, reintentos 3, timeout 5 s.

Advertencia: si Coolify construye con Nixpacks en vez del Dockerfile, el `HEALTHCHECK` no aplica; configurarlo en la interfaz.

**Cierre:** estado `healthy`; matar el proceso reinicia el contenedor solo y sin bucle.

---

# BLOQUE C — Blindar

Hoy `memory.max = max` y `cpu.max = max`. El kernel puede elegir matar `postgresIgris` en vez del backend.

## C1 — Límites

| Recurso | Límite | Razón |
|---|---|---|
| Memoria | 4 GB | Deja 3.75 GB a PostgreSQL, frontend y sistema |
| CPU | 1.5 cores | Evita que Whisper deje sin CPU a la BD |

Coolify → `igris:cerebro2` → Resource Limits.

**Cierre:** `cat /sys/fs/cgroup/memory.max` muestra el límite.

## C2 — Probar el aislamiento

Forzar consumo hasta superar el límite. **Cierre:** se reinicia `cerebro2`; `postgresIgris` sigue vivo.

---

# BLOQUE D — Higiene

## D1 — Rutas persistentes

```dockerfile
ENV HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache \
    TMPDIR=/app/tmp
RUN mkdir -p /app/.cache/huggingface /app/tmp
```

Volumen en Coolify: `/app/.cache` → `igris-cache`. **No** montar volumen en `/app/tmp`: los temporales deben morir con el contenedor.

Sin esto, cada redeploy re-descarga modelos al activar local. Dato medido: `/root/.cache` contiene `Microsoft`, `pip` y `whisper`, pero **no** `huggingface/` — faster-whisper nunca llegó a descargar, así que el motor que se ejecutó no era el configurado.

## D2 — Fuga de temporales en `core/tts.py:93`

El `.mp3` de edge-tts solo se borra si `save()` tiene éxito. Si falla, queda en `/tmp`. Envolver en `try/finally`.

Las demás rutas están correctas: `stt.py:77`, `stt.py:198`, `voice.py:36`, `tts.py:71`.

**Cierre:** forzar un error de síntesis y verificar que `/app/tmp` queda vacío.

## D3 — Limpieza automática

Tarea periódica sobre `/app/tmp`:

- Cada hora.
- Borrar por antigüedad (> 1 h), nunca por patrón de nombre.
- No tocar archivos con menos de 10 min (transcripción en curso).
- Nunca tocar `/app/.cache`.
- Registrar cuántos borró y cuánto liberó.

**Cierre:** `/app/tmp` acotado tras 24 h de uso.

## D4 — Logs

**No cambiar nada.** `logging.basicConfig` (`server/main.py:40`) escribe a stdout y Coolify lo retiene fuera del contenedor: no consume disco del contenedor. Solo si en el futuro se persistieran en disco, usar `RotatingFileHandler` con 10 MB × 3.

---

# BLOQUE E — Pool

## E1 — WebSocket sin sesión retenida (`user_routes.py:1302`)

Hoy abre `SessionLocal()` al aceptar y la conserva durante toda la conexión, incluido `receive()`. Con 100 WebSockets ociosos, el pool muere y el login se bloquea.

Reestructurar:

1. Sesión corta para validar el JWT.
2. Cerrar.
3. Recibir audio sin sesión.
4. Transcribir sin sesión.
5. Sesión corta para perfil y persistencia.
6. Cerrar **antes** del TTS.

Todas las salidas deben cerrar: auth fallida, cancelación, desconexión, excepción.

**Cierre:** 100 WebSockets ociosos → `pg_stat_activity` no sube de 40.

## E2 — Pool 20+15

`core/database.py:94`. Presupuesto sobre `max_connections=100`:

| Concepto | Conexiones |
|---|---|
| `max_connections` | 100 |
| Reserva administrativa | 5 |
| Otros servicios | 10 |
| Techo operativo (80 %) | 80 |
| **Asignado a IGRIS** | **40** |

Con 1 worker Uvicorn: `pool_size=20, max_overflow=15, pool_timeout=15, pool_recycle=1800, pool_pre_ping=true` → 35 conexiones.

Regla: `(pool_size + max_overflow) × workers <= 60`.

**Descartado:** el `50+50` del plan anterior consumiría las 100 conexiones.

Debe leerse de variables de entorno, para no tocar código al migrar.

Verificar desde el Terminal de `postgresIgris` (el backend no tiene `psql`):

```bash
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

Si supera 80 de forma sostenida, reducir el pool, no ampliarlo.

## E3 — Transacciones

`try/finally` con commit, rollback y cierre. Nunca una consulta larga dentro de la sesión que atiende un WebSocket.

**Cierre E:** 100 WebSockets + login + chat funcionando, conteo total < 80.

---

# BLOQUE F — Voz robusta

## F1 — Cola STT común (`core/stt_queue.py`)

- Cola acotada: `STT_QUEUE_MAX_SIZE=32`.
- Workers configurables: `STT_WORKERS=1` (Whisper local en CPU).
- **Un `Future` por trabajo** para devolver resultado, error y timeout. Sin esto el WebSocket recibiría el objeto de trabajo, no el texto.
- Timeout en cola y por transcripción.
- `task_done()` garantizado en `finally`.
- Cancelación ordenada en shutdown.
- Contadores para `/api/stt-stats`.

Concepto: `result = await stt_queue.submit(audio, mime, callback, timeout=...)`

Cola llena → error controlado `STT ocupado`, sin bloquear el event loop.

En startup: crear cola, iniciar workers, registrar cuántos. No cargar modelos si el proveedor es Deepgram.
En shutdown: dejar de aceptar, esperar un poco, cancelar, cerrar clientes HTTP.

## F2 — Integrar la cola en todas las rutas de voz

`user_routes.py` (voice-ws, voice-chat) y `main.py` (4 sitios). La verificación de voz corre en un límite separado: NeMo también consume CPU y no debe saturar a la vez que el STT.

## F3 — Deepgram: cliente y semáforo

- `httpx.AsyncClient` persistente, no uno por request.
- Límites de conexión y keep-alive; timeouts de conexión, escritura, lectura y pool.
- Semáforo `DEEPGRAM_CONCURRENCY=8`.
- Cierre en shutdown.

Deepgram Live: timeout de conexión, límite de duración, cierre en `finally`, tarea lectora cancelada, límite de conexiones.

## F4 — Fallback sin bucle

1. Deepgram con timeout.
2. Si falla, ¿fallback habilitado?
3. Enviar local a la cola.
4. Cola llena → `STT temporalmente ocupado`.
5. **Nunca** reintentos mutuos indefinidos.
6. Registrar proveedor inicial, fallback, duración y causa.

## F5 — Verificación de voz por niveles

| Nivel | Acciones | Re-verificación |
|---|---|---|
| 1 | hora, clima, búsqueda, notas, recordatorios | caché toda la sesión |
| 2 | Gmail lectura, Calendar lectura, Spotify | tras 5 min sin voz |
| 3 | enviar correo/WhatsApp, borrar evento, **Tuya/Home Assistant**, config | **siempre** |

Parámetros: `VOICE_VERIFY_CACHE_TTL=1800`, `VOICE_VERIFY_IDLE_LEVEL2=300`.

Estado en `BrainSession`: nivel verificado, instante, último turno, IP. No en Redis ni BD: es volátil.

El nivel se decide por la **herramienta a ejecutar**, no por palabras clave del texto. Nivel 3 reutiliza el patrón `propose/confirm` de `calendar_write.py`. Tuya y Home Assistant exigen además confirmación hablada explícita: una luz se apaga, un cerrojo no.

Casos límite: cambio de IP o de dispositivo invalida la caché; sesión expirada con WebSocket abierto re-verifica en el siguiente turno; usuario sin `voice_print` sigue bloqueado.

Efecto: de 1.83 cores a 0.18 cores con 100 usuarios.

## F6 — Cliente LLM persistente (`core/brain.py:214`)

Un cliente por proveedor, no uno por request. Invalidar si cambia base o clave. Cerrar en shutdown.

## F7 — SQL fuera del event loop

Agrupar consultas en una función síncrona con sesión propia, ejecutada con `to_thread()`. Nunca reutilizar una sesión creada en otro contexto. Prioridad: chat, voz tras transcripción, configuración.

## F8 — STT local

**Arrancar con `whisper.cpp`**, no con faster-whisper. El modelo `ggml-medium-q5_0.bin` ya está en la imagen: cero descargas, cero volumen nuevo, cero cambios de código. Basta cambiar `local_engine` a `whisper.cpp` en configuración. Es más preciso que `small` y de menor riesgo operativo.

Después, si hace falta, `faster-whisper`: `download_root` persistente, verificar la firma real de `WhisperModel` en la versión 1.1.1 antes de pasar argumentos nuevos, lock por `motor+modelo+compute_type`, una sola descarga nunca concurrente.

Cambio de motor en caliente: no destruir el que atiende; cargar el nuevo en background; cambiar el activo al terminar; liberar el viejo sin trabajos; si falla la carga, conservar el anterior.

Límites: `STT_WORKERS=1`, `OMP_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=2`, `MKL_NUM_THREADS=2`.

Warmup: en background, con timeout, sin impedir `/health`, una sola carga por modelo, estado `warming/ready/error`. No calentar local si el proveedor efectivo es Deepgram.

---

# BLOQUE G — Escalar

Solo si hace falta, y **Redis antes que nada**.

## G1 — Redis

Obligatorio antes de `UVICORN_WORKERS > 1`: `SessionStore` vive en memoria y un usuario perdería su conversación al cambiar de proceso.

- Servicio en Coolify.
- Dependencia fijada en `requirements.txt`.
- Conexión, timeout, reconexión y cierre.
- Fallback explícito si Redis no responde.
- Serializar solo lo serializable de `BrainSession`: no modelos ni clientes.

## G2 — Multi-worker

| Workers | pool_size | max_overflow | Total |
|---|---|---|---|
| 1 | 20 | 15 | 35 |
| 2 | 12 | 8 | 40 |

Con 4 workers no usar sin subir `max_connections` a 200+.

## G3 — Migración a 6 vCPU / 12 GB

No se hace ahora. Al migrar, **solo cambian variables de entorno**:

| Variable | Hoy | Tras migrar |
|---|---|---|
| `UVICORN_WORKERS` | 1 | 2 |
| `STT_WORKERS` | 1 | 2 |
| `DEEPGRAM_CONCURRENCY` | 8 | 16 |
| Límite memoria cgroup | 4 GB | 8 GB |
| Límite CPU cgroup | 1.5 | 5 |

Requisito de diseño: ninguna capacidad codificada en Python; todo por entorno.

Qué compra 6 vCPU: Deepgram holgado, local viable para 35–45, texto sin presión. **No** vuelve local un Jarvis para 100: sin GPU sigue fuera de alcance.

---

# Verificación final

| Prueba | Criterio |
|---|---|
| 100 WebSockets ociosos 2 min | `/health` < 500 ms, conexiones < 40 |
| 1 / 3 / 10 transcripciones locales | 1 funciona, 3 se encolan, 10 dan error controlado; `/health` responde |
| Sin `DEEPGRAM_API_KEY` | flujo local funciona, no se intenta Deepgram |
| Fallo de Deepgram | cae a local una vez, sin bucle |
| Cola local llena | error controlado |
| Cambio en caliente de proveedor | conversaciones no se cortan, carga en background |
| 10 transcripciones simultáneas × 3 tandas | sin `OOMKilled`, memoria estable, CPU < 80 % |
| Matar worker y Uvicorn | recupera solo, configuración intacta |
| Redeploy | config desde PostgreSQL, caché sobrevive, primer turno no cuelga |
| 100 turnos nivel 1–2 | menos de 20 verificaciones biométricas |

Comandos de apoyo, desde `postgresIgris`:

```bash
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM pg_stat_activity;"
```

Y desde fuera:

```bash
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' https://igris.zottagroup.com/health
```

---

# Orden de ejecución

Cada paso es un commit. No avanzar si rompe `/health`.

**Bloque A — Estabilizar**
1. Confirmar causa en logs (A1)
2. Lock en `_get_encoder()` (A2)
3. Locks en stt y tts (A3)
4. Executor acotado (A4)

**Bloque B — Ver**
5. `/health/deep` (B1)
6. `/api/stt-stats` (B2)
7. HEALTHCHECK en Docker y Coolify (B3)

**Bloque C — Blindar**
8. Límites de cgroup (C1)
9. Probar aislamiento (C2)

**Bloque D — Higiene**
10. Rutas persistentes y volumen (D1)
11. Fuga de `tts.py:93` (D2)
12. Limpieza automática (D3)

**Bloque E — Pool**
13. Pool 20+15 (E2)
14. WebSocket sin sesión retenida (E1)

**Bloque F — Voz robusta**
15. Cola STT (F1)
16. Integrar cola en todas las rutas (F2)
17. Verificación por niveles (F5)
18. Deepgram cliente y semáforo (F3)
19. Fallback sin bucle (F4)
20. Cliente LLM persistente (F6)
21. SQL fuera del event loop (F7)
22. `whisper.cpp` como local (F8)

**Bloque G — Escalar**
23. Redis (G1)
24. Multi-worker (G2)

**Cierre**
25. Verificación final

---

## Qué se construye primero

1. **A1–A2** — confirmar y arreglar la caída (medio día)
2. **B1, B3** — visibilidad y healthcheck (un día)
3. **C1** — límites de cgroup (una hora, solo configuración)
4. **A3–A4** — locks restantes y executor (medio día)
5. **D1–D2** — caché persistente y fuga de tts (un día)
6. **E1–E2** — WebSocket y pool (dos días, lo más delicado)

Con eso el sistema **no se cae**. Los bloques F y G son para los 100 usuarios y la conversación fluida.

E1 va al final de la primera semana a propósito: reescribe el ciclo de vida de una conexión completa. Debe hacerse con A–D ya estables para que, si algo falla, se sepa que fue E.

---

# Rollback

```bash
git log --oneline | head -20
git revert COMMIT_ID
git push origin main
```

Cada paso debe revertirse sin tocar los demás.

Rollback de emergencia sin código:

1. En `/config`, volver el proveedor STT a `deepgram`.
2. Reducir `STT_WORKERS` a 1 en Coolify.
3. Si el problema es memoria, bajar el límite del cgroup y reiniciar.

Nunca rollback de configuración de STT a la vez que se revierte código: si falla, no se sabrá cuál fue.

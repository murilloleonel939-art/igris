# Plan de Arreglo IGRIS — Escalado para 100+ usuarios

**Objetivo:** Arreglar el cuelgue inmediato (STT + pool agotado) Y escalar a **100+ usuarios concurrentes** (voz + texto simultáneamente).

**Caso de uso:** 50 usuarios en conversaciones de voz, 50 en chat de texto, ambos escribiendo/hablando al mismo tiempo sin bloqueos.

**Causa raíz del cuelgue actual:**
1. STT local descarga modelo (~1 GB) en request → bloquea 18–34 s.
2. Pool BD limitado (15 conexiones) se agota con WebSockets ociosos → login bloqueado.
3. Sin HEALTHCHECK → Coolify no detecta muerte.
4. LLM client creado por request (TLS handshake cada vez).
5. 84 queries síncronas en contexto async → thread pool saturado.
6. Sesiones in-memory, máx 200 → usuarios nuevos pierden sesión.

---

## FASE 0 — Diagnóstico (sin código, 10 min)

**Después de cada deploy, ejecutar:**

```bash
# 0.1 — Exit code del contenedor
docker inspect CONTAINER_ID | grep -A 5 "State"

# 0.2 — Límite de memoria
docker inspect CONTAINER_ID | grep -A 3 "Memory"

# 0.3 — Config real de la BD
docker exec CONTAINER_ID psql -U igris_user -d igris -c \
  "SELECT value FROM global_settings WHERE key = 'settings.stt';"

# 0.4 — Conexiones activas en PostgreSQL
docker exec CONTAINER_ID psql -U igris_user -d igris -c \
  "SELECT count(*) as total_connections FROM pg_stat_activity;"
```

**Anotar:**
- Exit 137 = OOM (kernel mató el proceso). Aumentar memoria del contenedor.
- Exit 0 pero sin logs = CPU saturado. Aumentar workers o threads.
- Conexiones > 30 = pool insuficiente.

---

## FASE 1 — Quitar el cuelgue del STT (inmediato)

### 1.1 — Red de seguridad: cambiar a Deepgram (5 min, reversible)

**Desde `/config`:**
- Provider STT: `deepgram`
- Guardar

Los usuarios pueden hablar hoy. Volvemos a `local` cuando 1.6 esté listo.

---

### 1.2 — Caché persistente de modelos STT

**Dockerfile:**
```dockerfile
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_OFFLINE=0
RUN mkdir -p $HF_HOME
```

**Volumen Coolify:** Mount `/app/.cache/huggingface` → volumen persistente `igris-cache`.

**core/stt.py — línea 20:**
```python
import os
os.environ.setdefault("HF_HOME", "/app/.cache/huggingface")

# En _load_faster_whisper_model() línea ~130:
model = WhisperModel(
    model_size, 
    device=device, 
    compute_type=compute_type,
    local_files_only=os.path.exists(
        f"/app/.cache/huggingface/models--openai--whisper-{model_size}"
    ),
    download_root="/app/.cache/huggingface"
)
```

**Efecto:** Primera carga larga (descarga). Redeploys posteriores < 1 s (caché).

---

### 1.3 — Warmup STT en startup (agnóstico al motor)

**server/main.py — en `on_startup()`:**

```python
@app.on_event("startup")
async def on_startup():
    # ... código existente ...
    logger.info("Iniciando warmup de STT en background...")
    asyncio.create_task(_warmup_stt())

async def _warmup_stt():
    """Carga el motor STT en background."""
    try:
        stt_config = settings_manager.get_stt_config()
        provider = stt_config.get("provider", "local")
        
        if provider == "local":
            engine = stt_config.get("engine", "faster-whisper")
            model_size = stt_config.get("model_size", "base")
            
            if engine == "faster-whisper":
                from core.stt import _load_faster_whisper_model
                model = _load_faster_whisper_model(model_size)
                logger.info(f"✓ faster-whisper/{model_size} warmup completo")
            elif engine == "whisper":
                from core.stt import _load_whisper_model
                model = _load_whisper_model(model_size)
                logger.info(f"✓ whisper/{model_size} warmup completo")
        else:
            logger.info(f"✓ STT provider {provider} (sin warmup local)")
    except Exception as e:
        logger.error(f"Warmup STT falló (no es crítico): {e}")
```

**Efecto:** Primer turno < 500 ms, no 20 s.

---

### 1.4 — Cola de STT con workers paralelos configurable (CRÍTICO para 100+ usuarios)

**core/stt_queue.py — archivo nuevo:**

```python
import asyncio
import os
from dataclasses import dataclass
from typing import Callable, Any
from loguru import logger

@dataclass
class STTJob:
    audio_data: bytes
    language: str
    callback: Callable
    timeout: float = 120.0

class STTQueueManager:
    def __init__(self, num_workers: int = None):
        # Determinar workers: env var > default 3
        if num_workers is None:
            num_workers = int(os.getenv("STT_WORKERS", "3"))
        
        self.num_workers = num_workers
        self.queue = asyncio.Queue()
        self.workers = []
        self.stats = {
            "processed": 0,
            "failed": 0,
            "queue_size": 0,
            "max_queue_size": 0,
            "total_wait_time": 0.0
        }
        logger.info(f"STT Queue inicializado con {num_workers} workers")
    
    async def start(self):
        """Inicia N workers de transcripción."""
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
            logger.info(f"STT Worker {i}/{self.num_workers} iniciado")
    
    async def _worker(self, worker_id: int):
        """Cada worker procesa trabajos de la cola."""
        while True:
            try:
                job = await asyncio.wait_for(self.queue.get(), timeout=300)
                import time
                start_time = time.time()
                
                logger.info(f"Worker {worker_id}: procesando job (cola: {self.queue.qsize()})")
                result = await job.callback(job.audio_data, job.language)
                
                elapsed = time.time() - start_time
                self.stats["processed"] += 1
                self.stats["total_wait_time"] += elapsed
                self.queue.task_done()
                
                logger.info(f"Worker {worker_id}: job completado en {elapsed:.2f}s")
            except asyncio.TimeoutError:
                logger.debug(f"Worker {worker_id}: timeout esperando job")
            except Exception as e:
                logger.error(f"Worker {worker_id}: error {e}")
                self.stats["failed"] += 1
    
    async def enqueue(self, audio_data: bytes, language: str, callback: Callable):
        """Encola un job de transcripción."""
        job = STTJob(audio_data, language, callback)
        await self.queue.put(job)
        
        queue_size = self.queue.qsize()
        self.stats["queue_size"] = queue_size
        if queue_size > self.stats["max_queue_size"]:
            self.stats["max_queue_size"] = queue_size
        
        logger.info(f"STT encolado: cola={queue_size}, workers={self.num_workers}")
        return job
    
    async def wait_all(self):
        """Espera a que se procesen todos los jobs."""
        await self.queue.join()
    
    def get_stats(self):
        """Retorna estadísticas para monitoreo."""
        avg_time = (
            self.stats["total_wait_time"] / self.stats["processed"]
            if self.stats["processed"] > 0
            else 0
        )
        return {
            "workers": self.num_workers,
            "processed": self.stats["processed"],
            "failed": self.stats["failed"],
            "queue_size": self.stats["queue_size"],
            "max_queue_size": self.stats["max_queue_size"],
            "avg_duration_s": round(avg_time, 2)
        }

# Instancia global
stt_queue = STTQueueManager()
```

**server/main.py — en `on_startup()` agregar:**

```python
await stt_queue.start()
logger.info(f"STT Queue activo: {stt_queue.num_workers} workers")
```

**server/main.py — agregar endpoint de monitoreo:**

```python
@app.get("/api/stt-stats")
async def stt_stats():
    """Estadísticas de la cola STT (DEBUG)."""
    return stt_queue.get_stats()
```

**server/user_routes.py — en `user_voice_ws()`:**

```python
# En lugar de llamar directamente a stt.transcribe_with_deepgram():
async def transcribe_callback(audio, lang):
    return await stt.transcribe_with_deepgram(audio, lang)

await stt_queue.enqueue(audio_data, language, transcribe_callback)
```

**Dockerfile — agregar variable de control:**

```dockerfile
# Número de workers STT paralelos
# 1 = baseline (cuelgue actual)
# 3 = por defecto (100 usuarios)
# 6 = muchos usuarios (200+ simultáneos)
# 10+ = corporativo (1000+)
ENV STT_WORKERS=3
```

**Coolify:**
- En **Environment Variables**, agregar: `STT_WORKERS=3` (o el valor que quieras)
- En **Resource Limits**:
  - CPU: 2 cores (mínimo)
  - RAM: 3 GB (por defecto)
  - Para STT_WORKERS=6: CPU 4, RAM 6 GB
  - Para STT_WORKERS=10: CPU 8, RAM 8 GB

**Efecto:**
- Hasta N transcripciones simultáneas (configurable sin redeploy).
- Las demás esperan en cola, no se cuelgan.
- Estadísticas disponibles en `/api/stt-stats` para monitoreo.
- Escala de 1 a 10+ workers según necesidad.

---

### 1.5 — CPU threads limitado para STT

**core/stt.py — en `_load_faster_whisper_model()`:**

```python
import os
import multiprocessing

def _load_faster_whisper_model(model_size: str):
    # Calcular threads: máximo (CPU cores - 2) para dejar margen a FastAPI
    cpu_count = multiprocessing.cpu_count()
    cpu_threads = max(1, cpu_count - 2)
    
    logger.info(f"STT: usando {cpu_threads} threads (CPU tiene {cpu_count})")
    
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,  # ← Límite explícito
        local_files_only=...,
        download_root=...
    )
    return model
```

**Dockerfile — agregar:**

```dockerfile
ENV OMP_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
```

**Efecto:** ctranslate2 no monopoliza el CPU. El resto del sistema responde.

---

### 1.6 — Lock por motor para evitar carga duplicada

**core/stt.py — al inicio:**

```python
import threading

_model_locks = {}
_loaded_models = 

def _get_model_lock(motor: str) -> threading.Lock:
    if motor not in _model_locks:
        _model_locks[motor] = threading.Lock()
    return _model_locks[motor]

def _load_faster_whisper_model(model_size: str):
    lock = _get_model_lock("faster-whisper")
    with lock:
        if "faster-whisper" in _loaded_models:
            return _loaded_models["faster-whisper"]
        
        model = WhisperModel(...)
        _loaded_models["faster-whisper"] = model
        return model
```

**Efecto:** Si 2 requests llegan simultáneamente, uno espera el lock en vez de cargar el modelo 2 veces.

---

## FASE 2 — Pool de BD y sesiones (escalabilidad)

### 2.1 — Reestructurar WebSocket para no retener conexión

**server/user_routes.py — `user_voice_ws()`:**

**ANTES:**
```python
async def user_voice_ws(websocket: WebSocket, ...):
    await websocket.accept()
    db = SessionLocal()  # ← Se abre aquí
    # ... todo el ciclo del socket usa esta sesión ...
    db.close()  # ← Se cierra solo cuando se desconecta (minutos)
```

**DESPUÉS:**
```python
async def user_voice_ws(websocket: WebSocket, ...):
    await websocket.accept()
    
    # Paso 1: Validar JWT SIN retener conexión
    try:
        db = SessionLocal()
        user = _validate_and_get_user(websocket.headers, db)
        db.close()
    except:
        await websocket.close()
        return
    
    # Paso 2: Recibir audio (no abre BD)
    audio_data = await websocket.receive_bytes()
    
    # Paso 3: Transcribir (no abre BD)
    await stt_queue.enqueue(audio_data, "es", transcribe_callback)
    
    # Paso 4: Abrir SOLO para guardar resultados
    db = SessionLocal()
    try:
        # _bind_identity, remember_from_text, neural_memory_context, learn_from_assistant
        user_obj = db.query(User).filter(User.id == user.id).first()
        # ... guardar ...
        db.commit()
    finally:
        db.close()
    
    # Paso 5: Responder (no abre BD)
    await websocket.send_json({"transcript": result, ...})
```

**Archivo:** `server/user_routes.py` líneas ~1292–1560.

**Efecto:** Cada WebSocket ocioso libera conexión tras validarse. 100 sockets ociosos = 0 conexiones en uso.

---

### 2.2 — Aumentar pool BD dramáticamente

**core/database.py — línea ~93:**

```python
# ANTES: pool_size=5, max_overflow=10 (total 15)

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=50,          # ← Conexiones "calientes"
    max_overflow=50,       # ← Conexiones temporales extra
    pool_timeout=15,       # ← Timeout de espera
    pool_recycle=3600,     # ← Reciclar cada hora
    echo=False,
)
```

**Parámetros justificados:**
- `pool_size=50`: con 2.1 hecho, un pool de 50 soporta ~200 WebSockets ociosos (uno abre conexión cada ~2 s para operaciones cortas).
- `max_overflow=50`: picos de 100 conexiones simultáneas en Fase 3 (queries async con `to_thread`).
- `pool_timeout=15`: si esperas > 15 s por una conexión, algo está bloqueado.

**Efecto:** Arregla el acantilado de 15 conexiones. Ahora es 100.

---

### 2.3 — Redis para sesiones (persistencia + escalabilidad)

**docker-compose.yml — agregar servicio:**

```yaml
services:
  igris-backend:
    # ... config existente ...
    environment:
      REDIS_URL: redis://redis:6379/1
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - igris-redis:/data
    command: redis-server --appendonly yes
```

**core/session_store.py — reemplazar:**

```python
import redis.asyncio as redis
from dataclasses import dataclass

class RedisSessionStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        self.redis_url = redis_url
        self.client: redis.Redis = None
    
    async def connect(self):
        self.client = await redis.from_url(self.redis_url)
    
    async def save_session(self, session_id: str, data: dict, ttl: int = 7200):
        await self.client.setex(
            f"session:{session_id}",
            ttl,
            json.dumps(data)
        )
    
    async def get_session(self, session_id: str) -> dict:
        data = await self.client.get(f"session:{session_id}")
        return json.loads(data) if data else None
    
    async def delete_session(self, session_id: str):
        await self.client.delete(f"session:{session_id}")
```

**server/main.py:**

```python
session_store = RedisSessionStore()

@app.on_event("startup")
async def on_startup():
    await session_store.connect()
    # ... resto ...
```

**Efecto:** 
- Sesiones persisten entre redeploys.
- Soporta N workers (multi-process scaling).
- Capacidad ilimitada (Redis, no memoria local).

---

## FASE 3 — Queries síncronas → async (eliminación de bloqueos)

### 3.1 — Envolver queries síncronas en `to_thread()`

**core/database.py — agregar helper:**

```python
import asyncio
from functools import wraps

async def async_query(func):
    """Ejecuta una query síncrona en thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)
```

**Encontrar las 84 queries en handlers async:**

```bash
grep -rn "db.query\|db.execute" server/ | grep "async def" -B 5
```

**Patrón de conversión:**

```python
# ANTES (bloquea el event loop):
async def user_chat(request, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    history = db.query(Chat).filter(...).limit(6).all()

# DESPUÉS (no bloquea):
async def user_chat(request):
    user = await async_query(
        lambda: db.query(User).filter(User.id == user_id).first()
    )
    history = await async_query(
        lambda: db.query(Chat).filter(...).limit(6).all()
    )
```

**Archivo:** `server/user_routes.py` líneas ~1559–1600 (inicio).

**Efecto:** 
- Event loop no se bloquea.
- Otros usuarios no sienten lag mientras se procesan queries.
- CPU thread pool maneja queries, worker FastAPI atiende WebSockets.

---

### 3.2 — LLM client único (singleton)

**core/brain.py — reemplazar `_build_client()`:**

```python
from functools import lru_cache

_client_cache = {}

@lru_cache(maxsize=1)
def _get_singleton_client(provider: str):
    """Mantiene un solo client por proveedor en memoria."""
    spec = PROVIDERS.get(provider)
    if not spec:
        return None
    
    # ... lógica de _build_client pero cache persistente ...
    api_key = os.environ.get(spec["key_env"], "")
    base = os.environ.get(spec.get("base_env", ""), "") or spec["base_default"]
    
    client = AsyncOpenAI(api_key=api_key, base_url=base)
    _client_cache[provider] = client
    return client

def _build_client(name: str):
    """Devuelve (cliente singleton, modelo)."""
    if name in _client_cache:
        return _client_cache[name], _get_model(name)
    return _get_singleton_client(name), _get_model(name)
```

**Efecto:** 
- Un client por proveedor (no por request).
- Sin TLS handshake repetido.
- ~200 ms ahorrados por request.

---

## FASE 4 — Multi-worker scaling (Coolify)

### 4.1 — Uvicorn con N workers

**Dockerfile — cambiar:**

```dockerfile
# ANTES:
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

# DESPUÉS:
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Valor de workers:**
- **4 workers** = 4 procesos con event loop propio cada uno. Tolera bloqueos mejor.
- Con Redis sesiones (Fase 2.3), los workers comparten estado.
- Con pool BD 50+50, cada worker toma ~4 conexiones en pico.

**Coolify:** Aumentar CPU limit a `2` cores, RAM a `4 GB`.

**Efecto:** 
- Si un worker cuelga, los otros siguen sirviendo.
- Paralelismo real en CPU multi-core.
- 2–3x throughput en texto.

---

### 4.2 — HEALTHCHECK

**Dockerfile:**

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1
```

**server/main.py:**

```python
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/health/deep")
async def health_deep():
    """Verifica BD, Redis, y STT."""
    try:
        # Test BD
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        
        # Test Redis
        await session_store.client.ping()
        
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}, 503
```

**Coolify:** Activar health checks en la UI.

---

## FASE 5 — Monitoreo y debugging (observabilidad)

### 5.1 — Logging estructurado

**core/logger.py — crear:**

```python
import json
from datetime import datetime

def log_event(event_type: str, **kwargs):
    """Log estructurado para análisis."""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "data": kwargs
    }
    logger.info(json.dumps(log_data))
```

**Uso en handlers:**

```python
# En user_voice_ws()
log_event("STT_START", user_id=user.id, audio_size=len(audio_data))
result = await stt_queue.enqueue(...)
log_event("STT_END", user_id=user.id, duration_ms=elapsed)
```

**Efecto:** Exportable a ELK, Datadog, etc. para alertas en tiempo real.

---

### 5.2 — Métricas Prometheus

**core/metrics.py — crear:**

```python
from prometheus_client import Counter, Histogram, Gauge

stt_requests = Counter("stt_requests_total", "Total STT requests")
stt_duration = Histogram("stt_duration_seconds", "STT latency")
db_pool_size = Gauge("db_pool_size", "DB pool connections in use")
queue_size = Gauge("stt_queue_size", "STT queue size")

@app.middleware("http")
async def metrics_middleware(request, call_next):
    db_pool_size.set(engine.pool.size())
    queue_size.set(stt_queue.stats["queue_size"])
    response = await call_next(request)
    return response
```

**Coolify:** Exponer en `/metrics` para Prometheus scrape.

---

## MATRIZ DE VERIFICACIÓN (100+ usuarios)

| Escenario | Config STT_WORKERS | Esperado | Comando |
|---|---|---|---|
| 100 WebSockets ociosos | 3 | Pool < 50 conexiones | `SELECT count(*) FROM pg_stat_activity;` |
| 10 transcripciones simultáneas | 6 | Cola < 2, timeouts 0 | `curl http://localhost:8000/api/stt-stats` |
| 30 transcripciones simultáneas | 10 | Cola < 5, timeouts 0 | `curl http://localhost:8000/api/stt-stats` |
| 50 requests/s texto | 3 | Latencia p95 < 2 s | `wrk -t 12 -c 50 -d 60 http://...` |
| 1 worker STT muere | 6 | 5 workers siguen | Ver logs, cola no explota |
| 1 worker Uvicorn muere | N/A | Otros 3 siguen | Enviar request |
| Redeploy sin desconectar clientes | 3 | Sesiones persisten | Login post-redeploy = funciona |
| Memoria en pico (STT_WORKERS=3) | 3 | < 4 GB | `docker stats` durante prueba carga |
| Memoria en pico (STT_WORKERS=6) | 6 | < 6 GB | `docker stats` durante prueba carga |
| CPU en pico (STT_WORKERS=3, 4 cores) | 3 | < 70% | `top` en host durante prueba |
| CPU en pico (STT_WORKERS=6, 4 cores) | 6 | < 80% (contienda OK) | `top` en host durante prueba |

---

## ORDEN DE IMPLEMENTACIÓN (14 tareas)

1. **0** — Diagnóstico (anotaciones).
2. **1.1** — Red seguridad (cambiar a deepgram).
3. **1.2** — Caché HF_HOME.
4. **1.3** — Warmup STT.
5. **1.4** — Cola STT (3 workers).
6. **1.5** — CPU threads.
7. **1.6** — Lock.
8. **2.1** — WebSocket sin retener BD.
9. **2.2** — Pool 50+50.
10. **2.3** — Redis sesiones.
11. **3.1** — Queries async con `to_thread()`.
12. **3.2** — LLM client singleton.
13. **4.1** — 4 workers Uvicorn + Coolify resources.
14. **4.2** — HEALTHCHECK.
15. **5.1** — Logging estructurado.
16. **5.2** — Métricas Prometheus.

Cada una es **1 commit independiente, reversible**.

---

## ROLLBACK

```bash
git revert COMMIT_ID
git push origin main
# Coolify redeploy automático
```

---

## ESTIMACIÓN FINAL (100+ usuarios — configurable por STT_WORKERS)

### Nivel 1: Baseline (STT_WORKERS=3, 2 cores, 3 GB RAM)

| Métrica | Valor |
|---|---|
| **WebSockets simultáneos** | 200–300 |
| **Transcripciones simultáneas** | 3 |
| **Requests texto/s** | 30–50 |
| **Latencia chat (p95)** | < 2 s |
| **Latencia STT (p95)** | 10–15 s (con cola pequeña) |
| **Memoria** | 3 GB |
| **CPU** | 2 cores |
| **Usuarios únicos persistidos** | Ilimitados (Redis) |
| **Redeploy sin downtime** | Sí (Redis sesiones) |
| **Recomendado para** | 50–100 usuarios ocasionales |

### Nivel 2: Escalado medio (STT_WORKERS=6, 4 cores, 6 GB RAM)

| Métrica | Valor |
|---|---|
| **WebSockets simultáneos** | 300–500 |
| **Transcripciones simultáneas** | 6 |
| **Requests texto/s** | 50–100 |
| **Latencia chat (p95)** | < 1.5 s |
| **Latencia STT (p95)** | 5–8 s (cola minimal) |
| **Memoria** | 6 GB |
| **CPU** | 4 cores |
| **Usuarios únicos persistidos** | Ilimitados (Redis) |
| **Redeploy sin downtime** | Sí (Redis sesiones) |
| **Recomendado para** | 150–300 usuarios activos |

### Nivel 3: Corporativo (STT_WORKERS=10, 8 cores, 8 GB RAM)

| Métrica | Valor |
|---|---|
| **WebSockets simultáneos** | 500–1000 |
| **Transcripciones simultáneas** | 10 |
| **Requests texto/s** | 100–200 |
| **Latencia chat (p95)** | < 1 s |
| **Latencia STT (p95)** | 2–3 s (casi sin cola) |
| **Memoria** | 8 GB |
| **CPU** | 8 cores |
| **Usuarios únicos persistidos** | Ilimitados (Redis) |
| **Redeploy sin downtime** | Sí (Redis sesiones) |
| **Recomendado para** | 500+ usuarios concurrentes |

### Cómo cambiar nivel

**En Coolify:**
1. Environment Variables → `STT_WORKERS=6` (o 10, etc.)
2. Resource Limits → CPU y RAM según tabla arriba
3. Deploy

**Sin redeploy (solo env var):**
```bash
# En el contenedor
docker exec CONTAINER_ID bash -c "export STT_WORKERS=6 && supervisorctl restart all"
```

**Monitoreo en tiempo real:**
```bash
curl http://localhost:8000/api/stt-stats
# Respuesta:
# {
#   "workers": 6,
#   "processed": 1250,
#   "failed": 3,
#   "queue_size": 0,
#   "max_queue_size": 12,
#   "avg_duration_s": 8.4
# }
```

---

## NOTAS CRÍTICAS

1. **No toques `hands-free` aún.** Va en plan separado (deshabilitarla del DOM).
2. **Redis es OBLIGATORIO para multi-worker.** Sin él, cada worker tiene su propia sesión → usuarios se pierden al saltar workers.
3. **`to_thread()` (Fase 3.1) es el cambio más delicado.** Prueba bien cada query convertida.
4. **Coolify memory limit debe ser ≥ 4 GB.** Menos es frágil con 4 workers + STT.
5. **Monitoreo (Fase 5) es opcional, pero ALTAMENTE RECOMENDADO** para detectar dónde está el cuello nuevo tras cada fase.


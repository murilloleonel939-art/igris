# ⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram

> Igris, el caballero de las sombras: un asistente personal tipo Jarvis, leal y formal, que habla en español neutro. Se usa desde una interfaz web con avatar animado a pantalla completa y modo manos libres (le hablas y te responde en voz alta) y desde Telegram (texto, notas de voz y archivos de audio), con modelos de IA intercambiables, una cadena de fallback automática entre proveedores y herramientas para consultar la hora, el clima, el correo y el calendario, y para guardar recordatorios y notas.

[![GitHub](https://img.shields.io/badge/GitHub-murilloleonel939--art%2Figris-blue)](https://github.com/murilloleonel939-art/igris) [![Python](https://img.shields.io/badge/Python-3.12%2B-green)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/) [![Vue](https://img.shields.io/badge/Vue-3.3-4FC08D)](https://vuejs.org/)

---

## ✅ Qué hace Igris hoy

| Capacidad | Estado |
| --- | --- |
| 💬 Chat web con Igris | Funcional |
| 🔑 Acceso a la web con clave única (`IGRIS_ACCESS_KEY`) | Funcional |
| 🧑‍🎤 Avatar animado (video) a pantalla completa que cambia según escucha, piensa o habla | Funcional |
| 🎧 Modo manos libres siempre activo: solo le hablas | Funcional (Chrome/Edge) |
| 🔊 Respuesta hablada automática (`/api/tts`) y botón de altavoz para repetir cada respuesta | Funcional |
| ⌨️ Botón Enviar que abre un cuadro de texto para escribir | Funcional |
| 🤖 Bot de Telegram (texto) | Funcional |
| 🎤 Notas de voz y audios por Telegram (transcripción con Whisper) | Funcional |
| ⚙️ Configuración de proveedor activo y cadena de fallback (web y Telegram) | Funcional |
| 🔁 Fallback automático entre proveedores de IA | Funcional |
| 🔐 Acceso al bot restringido por ID de Telegram + secreto de webhook | Funcional |
| 🧠 Memoria de conversación (por sesión: `web:<id>` y `tg:<id>`) | Funcional |
| 🕒 Hora y fecha de Colombia | Funcional |
| 🌦️ Clima de una ciudad | Funcional |
| 📧 Gmail (lectura de la bandeja) | Funcional |
| 📅 Google Calendar: consultar agenda y crear eventos con confirmación obligatoria | Funcional |
| ⏰ Recordatorios con aviso por Telegram (únicos, diarios o semanales) | Nuevo |
| 📝 Notas: anotar, listar, buscar y borrar | Nuevo |

**Personalidad:** caballero de las sombras, leal y formal, con español neutro (sin acento peninsular). El prompt vive en `core/config.py`; las instrucciones de herramientas, en `TOOLS_PROMPT` de `core/brain.py`.

---

## 🧰 Capacidades de Igris (herramientas)

Igris usa *tool calling*: el modelo decide cuándo llamar a una herramienta. Las herramientas viven en `core/tools/` y se registran en `core/tools/__init__.py`. Todas devuelven textos cortos pensados para decirse en voz alta.

| Herramienta | Qué hace | Ejemplo de orden |
| --- | --- | --- |
| `get_time` | Hora y fecha (Colombia por defecto) | "¿Qué hora es?" |
| `get_weather` | Clima actual y pronóstico de hoy | "¿Va a llover en Medellín?" |
| `list_emails`, `read_email` | Lee la bandeja de Gmail | "¿Tengo correos nuevos?" |
| `list_events` | Consulta el calendario | "¿Qué tengo mañana?" |
| `propose_event`, `confirm_event` | Crea eventos con confirmación (ver abajo) | "Agéndame una reunión con Ana mañana a las 3" |
| `create_reminder` | Crea un recordatorio con aviso por Telegram | "Recuérdame mañana a las 8 llamar al banco" |
| `list_reminders` | Lista los recordatorios pendientes | "¿Qué recordatorios tengo?" |
| `delete_reminder` | Cancela UN recordatorio por id | "Borra el recordatorio del banco" |
| `add_note` | Guarda una nota | "Anota que la clave del wifi de la oficina es X" |
| `list_notes`, `search_notes` | Lista o busca notas (sin importar tildes) | "¿Qué anoté sobre el wifi?" |
| `delete_note` | Borra UNA nota por id | "Borra la nota del wifi" |

### Crear eventos del calendario (confirmación obligatoria)

La confirmación se hace cumplir **en el servidor**, no solo con el prompt:

1. `propose_event` no crea nada: guarda una propuesta pendiente en la sesión y Igris te lee título, día, fecha y hora, y los choques con otros eventos.
2. Solo si tu **siguiente mensaje real** es un "sí" claro (y no han pasado más de 10 minutos) se crea el evento. Un texto malicioso dentro de un correo o evento no puede fabricar tu mensaje, así que no puede agendar nada.
3. No se invita a nadie: no se envían correos a terceros.
4. Requiere el permiso OAuth `https://www.googleapis.com/auth/calendar.events`.

### Recordatorios y notas

- **Recordatorios.** Se guardan en PostgreSQL con la fecha en UTC y se muestran en hora de Colombia (`America/Bogota`). Se rechazan fechas pasadas. Opcionalmente se repiten cada día o cada semana. Máximo 100 pendientes.
- **Aviso.** Una tarea en segundo plano (`core/scheduler.py`) revisa cada 30 segundos los vencidos y envía el aviso por Telegram: *"Mi señor, le recuerdo: llamar al banco."*
  - Si lo creaste desde **Telegram**, el aviso llega a ese chat.
  - Si lo creaste desde la **web**, llega a todos los IDs de `ALLOWED_TELEGRAM_IDS`.
  - No hay duplicados: cada recordatorio se reclama con una actualización atómica antes de enviarse. Si el envío falla, vuelve a pendiente y se reintenta.
  - Si el servidor estuvo caído, los vencidos se envían al arrancar con la nota "con retraso" (si pasaron más de 10 minutos).
  - Requiere `TELEGRAM_TOKEN`; sin él los recordatorios se guardan pero **no se envían** (se avisa en el log al arrancar).
- **Notas.** Texto libre (hasta 1000 caracteres). La búsqueda ignora mayúsculas y tildes y ordena por coincidencias.
- **Seguridad del borrado.** No existe el borrado masivo: se borra un solo elemento por id. El servidor exige que tu último mensaje real pida borrar ("borra…", "elimina…", "quita…") o sea un "sí" claro, y permite un borrado por mensaje. Los recordatorios cancelados quedan en la tabla con estado `cancelado`; las **notas se borran de verdad** y no se pueden recuperar.
- **Contenido de terceros.** Lo guardado en notas y recordatorios, y el contenido de correos y eventos, se trata como información, nunca como instrucciones.
- Los textos de notas y recordatorios **no se escriben en los logs** (solo sus ids). Las notas se guardan en texto plano en la base de datos: ten en cuenta esto antes de anotar claves sensibles.

---

## 🚀 Características

### Interfaz web (estilo Jarvis)

La pantalla del chat funciona como un asistente de voz:

- **Acceso con clave:** al abrir la web, si el navegador no tiene la clave guardada, se muestra la pantalla `/acceso`. Al escribir la clave correcta se guarda en el navegador y se entra al chat. El botón **Salir** del menú la borra.
- **Avatar a pantalla completa:** un video de Igris en bucle (`web/public/igris.mp4`) ocupa todo el fondo. El menú y los controles quedan encima, semitransparentes.
- **Estados del avatar:** el estado se muestra arriba ("Escuchando…", "Pensando…", "Hablando…") y cambia la animación:

  | Estado | Cuándo ocurre | Efecto en el video |
  | --- | --- | --- |
  | `idle` | En reposo | Reproducción normal |
  | `listening` | Está escuchando tu voz | Más rápido y más brillante |
  | `thinking` | Esperando la respuesta del modelo | Lento, más oscuro y con tono violeta |
  | `speaking` | Reproduciendo su voz | Rápido, con pulso de brillo según el volumen real del audio |

- **Manos libres siempre activo:** al abrir el chat empieza a escuchar solo, en bucle. Hablas, Igris responde con voz y, al terminar, vuelve a escuchar. Mientras piensa o habla, el micrófono se pausa para que no se oiga a sí mismo. Un botón pequeño ("Manos libres: activo/pausado") permite pausarlo y reanudarlo.
- **Escribir un mensaje:** el botón ✉️ Enviar abre el cuadro de texto con su botón "Enviar" (Enter también envía, Esc lo cierra). Mientras escribes, el micrófono se pausa.
- **Historial:** panel translúcido en la parte inferior con los mensajes (`user:` / `igris:`) y un botón de altavoz para repetir cualquier respuesta.
- **Menú:** 💬 Chat, ⚙️ Configuración y Salir.

### Requisitos y límites del navegador

- **Voz:** usa la Web Speech API del navegador (idioma `es-CO`), por lo que requiere Chrome o Edge y HTTPS. Firefox y Safari no la soportan completa; en ese caso se puede escribir con el botón Enviar. Este reconocimiento ocurre en el navegador y no pasa por `core/stt.py` (ese solo se usa para Telegram).
- **Micrófono:** la primera vez el navegador pide permiso; hay que aceptarlo. Si se bloquea, se corrige desde el candado de la barra de direcciones y pulsando "Manos libres".
- **Sonido:** los navegadores no reproducen audio hasta que haya un clic o toque en la página. Si lo bloquean, aparece el aviso "Toca la pantalla para activar el sonido"; con un toque basta.
- **Video:** el video es vertical (480×800). En un monitor horizontal ocupa todo el alto y los costados se funden con el fondo; en el celular llena toda la pantalla.

### Bot de Telegram

- Recibe updates por webhook (`/telegram/webhook`); el webhook se registra solo al iniciar el backend.
- Acepta texto, notas de voz y archivos de audio. El audio se transcribe a texto y se trata como una orden normal.
- Solo responde a los IDs de Telegram autorizados (`ALLOWED_TELEGRAM_IDS`); al resto les indica que no están autorizados.
- Valida el secreto del webhook (`TELEGRAM_WEBHOOK_SECRET`) y responde 200 de inmediato, procesando el update en segundo plano para evitar reintentos duplicados de Telegram.
- Cada ID de Telegram tiene su propia conversación con memoria (`tg:<id>`), y es el destino de los avisos de los recordatorios que creó.

**Comandos:**

| Comando | Qué hace |
| --- | --- |
| `/start`, `/help` | Saludo de Igris |
| `/config` | Muestra el proveedor activo y la cadena de fallback |
| `/setprovider <nombre>` | Cambia el proveedor activo (solo acepta proveedores válidos) |
| `/setfallback <p1,p2,...>` | Cambia el orden de la cadena de fallback (solo acepta proveedores válidos) |

### Memoria de conversación

- Cada conversación tiene su historial (`core/session_store.py`): `web:<id>` en la web (si el frontend no envía `session_id`, usa `web:default`) y `tg:<id de Telegram>` en Telegram.
- Se recuerdan los últimos 6 turnos (`IGRIS_HISTORY_TURNS`). Las sesiones expiran tras 2 horas sin uso y hay un máximo de 200.
- **Viven en memoria:** se pierden al reiniciar o redesplegar el backend (también una propuesta de evento pendiente de confirmar). Funciona con un solo worker de Uvicorn.

### Voz

- **Web (entrada):** reconocimiento de voz del navegador (Web Speech API), en modo manos libres.
- **STT en el backend (Telegram):** `core/stt.py`. Proveedor `local` (Whisper, requiere ffmpeg en la imagen) u `openai` (API de Whisper).
- **TTS (texto a voz):** `core/tts.py`, expuesto en `POST /api/tts`. La web lo reproduce automáticamente tras cada respuesta y mide su volumen con la Web Audio API para animar al avatar.

### Configuración de IA

- **Proveedores:** `nemotron`, `openai`, `anthropic`, `local` (Ollama). Todos se consumen con el SDK de OpenAI (APIs compatibles). La lista válida está en `PROVIDERS` de `core/brain.py` y debe coincidir con `AVAILABLE_PROVIDERS` de `core/config.py`.
- **Cadena por defecto:** nemotron → openai → anthropic → local.
- Si un proveedor falla (clave inválida, sin créditos, respuesta vacía, sin conexión), Igris pasa al siguiente automáticamente y deja el motivo en el log.
- Los cambios hechos desde la web o Telegram se guardan en `core/settings.json` y aplican de inmediato, pero **no sobreviven a un redeploy completo**. Para dejarlos permanentes, usa variables de entorno en Coolify.
- Un `settings.json` antiguo que contenga un proveedor que ya no existe (por ejemplo `groq`) se limpia al cargarse y no rompe nada. `GET /status` y `GET /api/ai-config` solo listan proveedores válidos, y `PUT /api/ai-config` y `/setprovider` rechazan los inválidos.

### API del backend

Los endpoints `/api/*` requieren el header `X-Igris-Key` con la clave de acceso (`IGRIS_ACCESS_KEY`). Sin clave o con una incorrecta responden `401`; tras 10 intentos fallidos desde la misma IP en 5 minutos responden `429`.

| Endpoint | Descripción |
| --- | --- |
| `GET /api/auth/check` | Valida la clave. Responde `{"ok": true}`. La usa la pantalla de acceso |
| `POST /api/chat` | Chat con Igris. Body: `{"text": "...", "session_id": "..."}` (`session_id` es opcional). Responde `{"status": "ok", "reply": "..."}` |
| `GET /api/ai-config` | Configuración actual de IA |
| `PUT /api/ai-config` | Actualiza proveedor activo y cadena de fallback |
| `POST /api/tts` | Texto a voz. Body: `{"text": "..."}`. Devuelve audio (`audio/mpeg`) |
| `POST /telegram/webhook` | Webhook de Telegram (usa su propio secreto, no la clave de acceso) |
| `GET /health`, `GET /status` | Verificación del servicio (públicos) |

---

## 🛠️ Stack tecnológico

- **Frontend:** Vue 3 (Composition API), Vue Router, Axios, Tailwind CSS, Vite. Web Speech API (entrada de voz) y Web Audio API (volumen del avatar).
- **Backend:** Python 3.12, FastAPI, Uvicorn, Pydantic, OpenAI SDK, python-telegram-bot, openai-whisper (+ ffmpeg), httpx.
- **Base de datos:** PostgreSQL (SQLAlchemy + psycopg 3). Guarda recordatorios y notas.
- **Despliegue:** Docker, en una instancia EC2 administrada con Coolify (backend y frontend como servicios separados).

---

## 🧩 Estructura del proyecto

```
igris/
├── core/
│   ├── brain.py               # Orquesta proveedores con fallback, bucle de tool calling y TOOLS_PROMPT
│   ├── config.py              # Proveedores válidos, modelos por defecto y system prompt
│   ├── settings_manager.py    # core/settings.json (configuración de IA persistente, con limpieza de proveedores inválidos)
│   ├── session_store.py       # Sesiones de conversación en memoria (web:<id>, tg:<id>)
│   ├── database.py            # SQLAlchemy: modelos (incluye Reminder y Note) e init_db
│   ├── scheduler.py           # Planificador de avisos de recordatorios (tarea en segundo plano)
│   ├── stt.py, tts.py         # Voz
│   ├── settings.json
│   └── tools/                 # Herramientas de Igris (ver lista abajo)
├── server/            # main.py (FastAPI: chat, configuración, TTS, acceso con clave, webhook de Telegram y arranque del planificador)
├── node/              # cliente_voice.py, cliente_text.py, cliente_speak.py (Raspberry Pi - opcional)
├── tests/
│   └── test_logic.py          # Pruebas sin red de validaciones, protección del borrado y planificador
├── web/               # Aplicación Vue
│   ├── public/
│   │   └── igris.mp4              # Video del avatar (se sirve como /igris.mp4)
│   └── src/
│       ├── App.vue                # Menú (con botón Salir) + avatar de fondo (solo en la ruta Chat)
│       ├── router.js              # Rutas: Chat (/), Configuration (/config) y Access (/acceso) + guard de clave
│       ├── api.js                 # Cliente Axios (añade X-Igris-Key y maneja el 401)
│       ├── components/
│       │   ├── IgrisAvatar.vue    # Video con efectos según estado y volumen
│       │   └── IgrisHero.vue      # Avatar a pantalla completa + texto de estado
│       ├── composables/
│       │   └── useIgris.js        # Estado compartido: igris.state y igris.level
│       └── pages/
│           ├── Access.vue         # Pantalla de acceso con clave única
│           ├── Dashboard.vue      # Chat: voz, manos libres, TTS, historial y cuadro de texto
│           └── Configuration.vue  # Proveedor activo y cadena de fallback
├── Dockerfile         # Imagen del backend (Python 3.12-slim + ffmpeg + PyTorch solo CPU)
├── Dockerfile.web     # Imagen del frontend (Node.js + vite build)
├── requirements.txt
└── README.md
```

### Archivos de `core/tools/`

| Archivo | Contenido |
| --- | --- |
| `__init__.py` | Registro: esquemas `TOOLS`, mapa `_HANDLERS`, herramientas que reciben la sesión (`_SESSION_TOOLS`) y `run_tool` (nunca lanza excepciones) |
| `time_tools.py` | `get_time` y utilidades de fecha en español (`_format`, `now_context`, `DEFAULT_TZ`) |
| `weather.py` | `get_weather` |
| `gmail.py` | `list_emails`, `read_email` |
| `gcalendar.py` | `list_events` |
| `calendar_write.py` | `propose_event`, `confirm_event` (confirmación forzada en el servidor) |
| `google_client.py` | Cliente OAuth/HTTP compartido por Gmail y Calendar |
| `reminders.py` | `create_reminder`, `list_reminders`, `delete_reminder` |
| `notes.py` | `add_note`, `list_notes`, `search_notes`, `delete_note` |
| `_common.py` | Utilidades de recordatorios y notas: conversión de fechas (UTC ↔ Colombia), normalización de texto y protección del borrado |

Para añadir una herramienta nueva: crea su función `async` (devuelve un dict en español), agrega su esquema a `TOOLS`, regístrala en `_HANDLERS` y, si necesita la sesión, añádela a `_SESSION_TOOLS` (recibe `_session`; el modelo nunca puede inyectarlo).

### Cómo funciona el avatar

- `useIgris.js` expone un estado reactivo compartido: `igris.state` (`idle`, `listening`, `thinking`, `speaking`) e `igris.level` (volumen de 0 a 1; `-1` significa "simulado").
- `Dashboard.vue` cambia el estado con `setIgrisState(...)` según lo que ocurre: al escuchar, al esperar la respuesta del backend y al reproducir el audio de `/api/tts`.
- Mientras suena la voz, `Dashboard.vue` mide el volumen real con un `AnalyserNode` y lo escribe en `igris.level`.
- `IgrisAvatar.vue` lee ese estado y ajusta la velocidad de reproducción, el brillo y el color del video con transiciones suaves.

### Cambiar el video del avatar

Reemplaza `web/public/igris.mp4` por otro video y haz **Rebuild and Deploy** del frontend. Recomendaciones: formato vertical (9:16), sin marca de agua, de pocos MB (GitHub no acepta archivos de más de 25 MB desde el navegador) y, idealmente, en bucle continuo. Si el video tiene otra proporción, ajusta `RATIO` y el `aspect-ratio` en `IgrisAvatar.vue`.

---

## ⚙️ Variables de entorno (Coolify)

Se configuran en el servicio de **backend** en Coolify. Después de cambiarlas hay que hacer redeploy o restart. **Recordatorios y notas no añaden variables nuevas**: usan `DATABASE_URL`, `TELEGRAM_TOKEN` y `ALLOWED_TELEGRAM_IDS`.

### Acceso web

| Variable | Descripción | Ejemplo / por defecto |
| --- | --- | --- |
| `IGRIS_ACCESS_KEY` | Clave única para entrar a la web. **Obligatoria:** si falta o está vacía, el backend rechaza todo `/api/*` con 401 (falla cerrado). Usa solo letras y números | `openssl rand -hex 24` |

### IA

| Variable | Descripción | Ejemplo / por defecto |
| --- | --- | --- |
| `IGRIS_PROVIDER` | Proveedor activo (se intenta primero). Debe ser `nemotron`, `openai`, `anthropic` o `local` | `nemotron` |
| `IGRIS_FALLBACK_CHAIN` | Orden de fallback, separado por comas | `nemotron,openai,anthropic,local` |
| `IGRIS_MAX_TOKENS` | Tokens máximos por respuesta | `2048` |
| `IGRIS_HISTORY_TURNS` | Turnos de conversación que Igris recuerda | `6` |
| `NEMOTRON_API_KEY` | Clave de NVIDIA NIM | `nvapi-...` |
| `NEMOTRON_API_BASE` | URL base de NVIDIA NIM (opcional) | `https://integrate.api.nvidia.com/v1` |
| `IGRIS_NEMOTRON_MODEL` | Modelo de Nemotron (opcional) | `nvidia/nemotron-3-super-120b-a12b` |
| `OPENAI_API_KEY` | Clave de OpenAI | `sk-...` |
| `IGRIS_OPENAI_MODEL` | Modelo de OpenAI (opcional) | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Clave de Anthropic | `sk-ant-...` |
| `IGRIS_ANTHROPIC_MODEL` | Modelo de Anthropic (opcional) | `claude-sonnet-5-5` |
| `IGRIS_LOCAL_URL` | URL de Ollama (debe ser alcanzable desde el contenedor) | `http://localhost:11434` |
| `IGRIS_LOCAL_MODEL` | Modelo local de Ollama (opcional) | `llama3.1` |

### Google (Gmail y Calendar)

Las credenciales OAuth que usan `core/tools/google_client.py`, `gmail.py` y `gcalendar.py` se configuran también en el backend; consulta ese módulo para ver los nombres exactos de las variables. Para **crear eventos** el refresh token debe haberse generado con el permiso `https://www.googleapis.com/auth/calendar.events`; si no, Igris avisará de que falta el permiso de escritura.

### Voz

| Variable | Descripción | Ejemplo / por defecto |
| --- | --- | --- |
| `IGRIS_STT_PROVIDER` | Proveedor de transcripción (Telegram): `local` u `openai` | `local` |
| `IGRIS_WHISPER_MODEL` | Modelo de Whisper local (`tiny`, `base`, `small`, `medium`) | `base` |
| `IGRIS_STT_MODEL` | Modelo de Whisper para el proveedor `openai` (no aplica al local) | `whisper-1` |
| `IGRIS_STT_LANGUAGE` | Idioma del audio a transcribir (código de 2 letras) | `es` |
| `IGRIS_TTS_PROVIDER` | Proveedor de síntesis de voz | `local` |
| `IGRIS_TTS_VOICE` | Voz a usar (los valores válidos dependen del proveedor de TTS) | según proveedor |
| `IGRIS_TTS_RATE` | Velocidad de la voz | según proveedor |
| `IGRIS_TTS_PITCH` | Tono de la voz | según proveedor |
| `IGRIS_TTS_INSTRUCTIONS` | Instrucciones de estilo para la voz (en proveedores que lo soporten) | texto libre |
| `IGRIS_PIPER_VOICE` | Voz del modelo Piper (cuando se usa Piper) | según modelo instalado |

> Los valores aceptados por las variables `IGRIS_TTS_*` y `IGRIS_PIPER_VOICE` los define `core/tts.py`; revísalo antes de cambiarlos.

### Telegram

| Variable | Descripción |
| --- | --- |
| `TELEGRAM_TOKEN` | Token del bot (de @BotFather). También lo usa el planificador para enviar los avisos de recordatorios |
| `ALLOWED_TELEGRAM_IDS` | IDs de Telegram autorizados, separados por comas. Reciben los avisos de los recordatorios creados desde la web |
| `TELEGRAM_WEBHOOK_URL` | URL pública del webhook, p. ej. `https://igris.zottagroup.com/telegram/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | Secreto para validar que las peticiones vienen de Telegram. **Obligatorio en producción:** si está vacío, el webhook no valida el origen |

### Base de datos

| Variable | Descripción |
| --- | --- |
| `DATABASE_URL` | Conexión a PostgreSQL. Acepta `postgresql://`, `postgres://` o `postgresql+psycopg://`; el backend la convierte solo al prefijo del driver psycopg 3. **Es obligatoria en producción:** sin ella se usa SQLite local (`./igris.db`) dentro del contenedor y los recordatorios y notas se pierden en cada despliegue. Al arrancar, el log dice `Base de datos activa: postgresql` (o `sqlite`) |

### Otras

| Variable | Descripción |
| --- | --- |
| `NODE_TOKEN` | Token reservado para los clientes `node/` (Raspberry Pi). Hoy ningún endpoint lo exige |

> ⚠️ Las variables `VITE_*` son del frontend: se configuran en el servicio del frontend y se incrustan en el JavaScript público al compilar. **Nunca pongas secretos en ellas** ni las agregues al backend. La clave de acceso (`IGRIS_ACCESS_KEY`) vive solo en el backend; en el navegador se guarda únicamente en `localStorage` cuando el usuario la escribe.

### Ejemplo mínimo

```
IGRIS_PROVIDER=nemotron
IGRIS_FALLBACK_CHAIN=nemotron,openai,anthropic,local
NEMOTRON_API_KEY=nvapi-your-key-here
DATABASE_URL=postgresql://usuario:clave@host:5432/igris

IGRIS_ACCESS_KEY=una-clave-larga-solo-letras-y-numeros

TELEGRAM_TOKEN=123456:ABC...
ALLOWED_TELEGRAM_IDS=123456789
TELEGRAM_WEBHOOK_URL=https://igris.zottagroup.com/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=un-secreto-largo-y-aleatorio

IGRIS_STT_PROVIDER=local
IGRIS_WHISPER_MODEL=base
```

> 🔒 **Nunca subas el archivo `.env` al repositorio.** Las claves viven solo en las variables de Coolify. Si alguna clave se publicó alguna vez, regenérala.

---

## ▶️ Despliegue

1. **Variables de entorno:** configúralas en Coolify → servicio de backend (ver tablas anteriores). No olvides `IGRIS_ACCESS_KEY` y `DATABASE_URL`.
2. **Backend:** Rebuild and Deploy (si cambiaste el `Dockerfile` o `requirements.txt`, usa Deploy sin caché). Al arrancar, las tablas nuevas (`reminders`, `notes`) se crean solas.
3. **Revisar los logs del backend:** deben aparecer `Base de datos activa: postgresql` y `Planificador de recordatorios iniciado (cada 30 s)`.
4. **Frontend:** Rebuild and Deploy en el servicio del frontend. Verifica que `web/public/igris.mp4` esté en el repositorio.
5. **Probar la web:** abre `https://webigris.zottagroup.com` con Chrome o Edge. Escribe la clave de acceso, acepta el permiso del micrófono y toca la pantalla una vez. Deberías ver a Igris de fondo; háblale o usa ✉️ Enviar para escribir "hola".
6. **Probar Telegram:** escribe a tu bot desde un ID autorizado, envía texto y luego una nota de voz.
7. **Probar la configuración:** en ⚙️ Configuración (o con `/config` y `/setprovider` en Telegram) cambia el proveedor y verifica que el siguiente mensaje lo usa. `GET /status` no debe listar `groq`.

Para probar el frontend en local: entra a `web/` y ejecuta `npm install` y `npm run dev`.

Si cambias `IGRIS_ACCESS_KEY`, haz redeploy del backend: los navegadores que tengan guardada la clave anterior volverán solos a la pantalla de acceso.

### Cómo probar cada función de Igris

Pruébalas desde la web (por voz o con ✉️ Enviar) y desde Telegram:

| Función | Qué decir | Resultado esperado |
| --- | --- | --- |
| Hora y clima | "¿Qué hora es?" / "¿Va a llover hoy?" | Hora en palabras naturales; clima de la ciudad por defecto |
| Gmail | "¿Tengo correos nuevos?" | Resumen de a lo sumo tres correos |
| Calendario (lectura) | "¿Qué tengo mañana?" | Lista de eventos |
| Calendario (crear) | "Agéndame una reunión con Ana mañana a las 3 de la tarde" y luego "sí" | Igris propone y, tras el "sí", crea el evento (verifícalo en Google Calendar). Si en vez de "sí" dices "no, mejor a las 4", no crea nada y vuelve a proponer |
| Memoria | "Mi perro se llama Max" y luego "¿cómo se llama mi perro?" | Recuerda el dato dentro de la misma sesión |
| Recordatorio | "Recuérdame en 2 minutos probar a Igris" | A los 2 minutos llega a Telegram: "Mi señor, le recuerdo: probar a Igris." |
| Recordatorio repetido | "Recuérdame todos los días a las 8 tomar agua" | Se crea con repetición diaria |
| Listar y cancelar | "¿Qué recordatorios tengo?" y luego "Borra el recordatorio de probar a Igris" | Lo lista con su id y lo cancela |
| Notas | "Anota que la clave del wifi de la oficina es X" y luego "¿Qué anoté sobre el wifi?" | Guarda y recupera la nota |
| Borrar nota | "Borra la nota del wifi" | La borra y dice cuál borró |
| Seguridad del borrado | "¿Tengo correos?" | No debe borrar nada, aunque un correo contenga instrucciones |
| Recuperación | Crea un recordatorio para dentro de 2 minutos, detén el backend 3 minutos y reinícialo | El aviso llega "con retraso" al arrancar |
| Persistencia | Crea un recordatorio lejano, redespliega y pregunta "¿qué recordatorios tengo?" | Sigue ahí (confirma que usas PostgreSQL) |

Para ejecutar las pruebas automáticas de lógica (no requieren red ni base de datos): `python tests/test_logic.py` desde la raíz del repositorio. No cubren las consultas SQL; esas se validan con la prueba de persistencia de arriba.

### Verificar el acceso con `curl`

```bash
API=https://igris.zottagroup.com
curl -i $API/api/auth/check                                  # sin clave: 401
curl -i -H "X-Igris-Key: TU_CLAVE" $API/api/auth/check       # con clave: 200 {"ok":true}
curl -i -X OPTIONS $API/api/chat \
  -H "Origin: https://webigris.zottagroup.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-igris-key"   # preflight: 200 y x-igris-key permitido
```

### Recomendación: caché del modelo de Whisper

La primera nota de voz tras un despliegue descarga el modelo de Whisper (unos 140 MB para `base`). Para no repetirlo en cada redeploy, monta un volumen persistente en `/root/.cache/whisper` (Coolify → backend → Storages).

### PyTorch solo CPU

El servidor no tiene GPU, así que el `Dockerfile` instala `torch==2.3.0` desde el índice de CPU de PyTorch **antes** de `requirements.txt`. Así `openai-whisper` encuentra `torch` ya instalado y no descarga la versión con CUDA (varios GB). La versión del `Dockerfile` debe coincidir con la de `requirements.txt`. Para comprobarlo dentro del contenedor del backend: `pip list | grep -i -E "^(torch|nvidia)"` debe mostrar solo `torch 2.3.0+cpu`.

### Mantenimiento del disco

Coolify limpia Docker cada día a las 00:00 UTC (Servers → Docker Cleanup). Si varios builds seguidos llenan el disco antes de esa hora, o un deploy se cuelga sin avisar, mira `df -h /` y `docker system df`, y libera con `docker builder prune -f` y `docker image prune -a -f`. **No uses `--volumes`**: ahí vive PostgreSQL.

---

## 🩺 Solución de problemas

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| La web vuelve siempre a `/acceso` o dice "Clave incorrecta" | La clave no coincide con `IGRIS_ACCESS_KEY`, o la variable falta o está vacía en el backend (falla cerrado) | Revisar la variable en Coolify (servicio de backend), hacer redeploy y escribir la clave de nuevo |
| 401 en `/api/*` desde `curl` | Falta el header `X-Igris-Key` o la clave es incorrecta | Enviar `-H "X-Igris-Key: TU_CLAVE"`. `/health`, `/status` y el webhook de Telegram no la usan |
| 429 "Demasiados intentos, espera unos minutos" | 10 intentos fallidos desde la misma IP en 5 minutos | Esperar 5 minutos o reiniciar el backend (el contador está en memoria) |
| "No se pudo conectar con el servidor" o error de CORS en la consola del navegador | El backend no está desplegado con los cambios, está caído, o el origen no está permitido | Redesplegar el backend y confirmar que el frontend se sirve desde `https://webigris.zottagroup.com` (o `http://localhost:5173` en local). Los orígenes permitidos están en `server/main.py` |
| El avatar no aparece o dice "No se encontró igris.mp4" | El video no está en `web/public/` o no se redesplegó el frontend | Subir `igris.mp4` a `web/public/`, hacer Rebuild and Deploy y recargar con Ctrl+Shift+R. Comprobar que `https://webigris.zottagroup.com/igris.mp4` abre |
| El avatar se ve pero no cambia de estado | El frontend desplegado es una versión anterior | Confirmar que `Dashboard.vue` importa `useIgris` y volver a desplegar el frontend |
| Aviso rojo "Micrófono bloqueado" | Permiso denegado en el navegador | Permitir el micrófono en el candado de la barra de direcciones y pulsar "Manos libres" |
| "Tu navegador no soporta la voz" | Firefox o Safari | Usar Chrome o Edge, o escribir con el botón ✉️ Enviar |
| Aviso "Toca la pantalla para activar el sonido" | El navegador bloquea el audio hasta que haya una interacción | Hacer clic o tocar la página una vez |
| Igris responde en texto pero no habla | Falla de `/api/tts` en el backend | Revisar los logs del backend y la configuración de `IGRIS_TTS_*` |
| Igris se responde a sí mismo en bucle | Altavoces muy fuertes cerca del micrófono | Usar audífonos o bajar el volumen |
| `Proveedor 'nemotron' falló: respuesta vacía` | El modelo razona y agota los tokens antes de responder | Subir `IGRIS_MAX_TOKENS` (2048 o más); el log indica el `finish_reason` |
| `Proveedor 'openai'/'anthropic' falló: ... crédito/quota` | Cuenta sin saldo | Recargar saldo o quitar el proveedor de la cadena |
| `Proveedor 'local' falló: Connection error` | `localhost` dentro del contenedor no es el host de Ollama | Definir `IGRIS_LOCAL_URL` con la IP/servicio correcto o quitar `local` de la cadena |
| Telegram: `No such file or directory: 'ffmpeg'` | Falta ffmpeg en la imagen | Añadir `ffmpeg` al `apt-get install` del `Dockerfile` y reconstruir sin caché |
| Telegram: audio lento la primera vez | Descarga del modelo de Whisper | Montar volumen en `/root/.cache/whisper` |
| `422 Unprocessable Entity` en `/api/chat` | El body del frontend no coincide con el modelo (`{"text": "..."}`) | Revisar el `detail` de la respuesta en la pestaña Network |
| Telegram responde 403 en el webhook | El secreto no coincide | Verificar `TELEGRAM_WEBHOOK_SECRET` y redeploy (se vuelve a registrar al iniciar) |
| El deploy del backend se cuelga o el disco se llena | Caché de build e imágenes viejas acumuladas, o `torch` con CUDA en la imagen | Ver "Mantenimiento del disco" y "PyTorch solo CPU" en la sección de despliegue |
| Igris pregunta "¿en qué desea confirmar?" al decir "sí" | La conversación no llega con historial (sesión nueva) o se redesplegó entre el mensaje y el "sí" | Repetir la orden. Revisar en los logs la línea `say: ... historial=N pendiente=...` |
| Igris dice que falta el permiso de escritura del calendario | El refresh token de Google no incluye `calendar.events` | Generar un refresh token nuevo con ese permiso |
| Los recordatorios no llegan | Falta `TELEGRAM_TOKEN`, `ALLOWED_TELEGRAM_IDS` vacío (si se crearon desde la web), o el planificador no arrancó | Ver en los logs `Planificador de recordatorios iniciado`; si aparece `TELEGRAM_TOKEN no definido` o `no hay a quién avisar`, definir las variables y redesplegar |
| Un recordatorio se reintenta cada 30 s en el log | El envío a Telegram falla de forma persistente (por ejemplo, el chat bloqueó al bot) | Revisar el aviso `no llegó a un destino` del log; se reintenta sin límite para no perder avisos tras una caída |
| Los recordatorios y notas desaparecen tras cada despliegue | El backend usa SQLite (falta `DATABASE_URL`) | Definir `DATABASE_URL` hacia PostgreSQL; el log debe decir `Base de datos activa: postgresql` |
| `No module named 'psycopg2'` al arrancar | URL de PostgreSQL sin el prefijo del driver y versión antigua de `core/database.py` | Usar el `database.py` actual (convierte la URL solo) o definir `postgresql+psycopg://...` |
| Aparece `groq` en `/status` o en la configuración | `IGRIS_FALLBACK_CHAIN` o `IGRIS_PROVIDER` de Coolify aún lo contienen | Quitarlo de esas variables (y borrar `GROQ_API_KEY` e `IGRIS_GROQ_MODEL`); aunque quede, se filtra y no rompe nada |

---

## 📝 Notas importantes

- **Acceso con clave única en la web:** la interfaz pide una clave (`IGRIS_ACCESS_KEY`) en `/acceso`. El navegador la guarda en `localStorage` y la envía en el header `X-Igris-Key` a `/api/chat`, `/api/tts`, `/api/ai-config` y `/api/auth/check`. El backend compara la clave en tiempo constante, rechaza todo si la variable no está definida y responde 429 tras 10 intentos fallidos desde una IP en 5 minutos. `/health`, `/status` y el webhook de Telegram no usan esta clave. No hay usuarios, sesiones ni base de datos para el acceso.
- **CORS:** el backend solo acepta peticiones del frontend (`https://webigris.zottagroup.com`) y de `http://localhost:5173` para desarrollo, con los métodos `GET`, `POST`, `PUT` y `OPTIONS` y los headers `Content-Type` y `X-Igris-Key`.
- **El bot de Telegram tiene su propia protección:** solo responde a los IDs de `ALLOWED_TELEGRAM_IDS` y valida el secreto del webhook.
- **System prompt** (en `core/config.py`): Igris es un caballero de las sombras leal, formal, de respuestas breves y sin markdown (sus respuestas están pensadas para decirse en voz alta), y se dirige al usuario como "mi señor".
- **Texto de terceros:** el contenido de correos, eventos y notas se trata siempre como información, nunca como instrucciones.
- Backend y frontend son servicios separados en Coolify; ambos necesitan sus propias variables de entorno.
- **Video del avatar:** Igris es un personaje de *Solo Leveling* y el video es un recurso externo. Si vas a publicar el proyecto o usarlo comercialmente, asegúrate de tener derecho a usar ese material o reemplázalo por uno propio.

---

## 🔗 Enlaces útiles

- [NVIDIA NIM](https://docs.nvidia.com/nim/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [python-telegram-bot](https://python-telegram-bot.org/)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Vue 3](https://vuejs.org/)
- [Web Speech API (MDN)](https://developer.mozilla.org/es/docs/Web/API/Web_Speech_API)
- [Tailwind CSS](https://tailwindcss.com/)
- [Coolify](https://coolify.io/)

---

## 🙏 Créditos

- Modelo **NVIDIA Nemotron 3 Super 120B** por NVIDIA
- **FastAPI** por @tiangolo, **Vue 3** por el equipo de Vue, **Tailwind CSS** por el equipo de Tailwind
- **Whisper** por OpenAI
- **Coolify** por simplificar el despliegue con Docker
- Personaje **Igris** de *Solo Leveling*

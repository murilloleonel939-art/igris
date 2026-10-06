# ⚔️ IGRIS - Asistente de IA con Chat Web, Telegram y Voz

> Igris, el caballero de las sombras: un asistente personal tipo Jarvis, leal y formal, que habla en español neutro. Se usa desde una **interfaz web** y desde **Telegram** (texto, notas de voz y archivos de audio), con modelos de IA intercambiables y una **cadena de fallback** automática entre proveedores.

[![GitHub](https://img.shields.io/badge/GitHub-murilloleonel939--art%2Figris-blue)](https://github.com/murilloleonel939-art/igris)
[![Python](https://img.shields.io/badge/Python-3.12%2B-green)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.3-4FC08D)](https://vuejs.org/)

---

## ✅ Qué hace Igris hoy

| Capacidad | Estado |
|-----------|--------|
| 💬 Chat web con Igris | Funcional |
| 🎙️ Entrada de voz en la web (micrófono) | Funcional |
| 🔊 Síntesis de voz (`/api/tts`) | Implementada en el backend; el botón de altavoz puede no verse en algunos despliegues |
| 🤖 Bot de Telegram (texto) | Funcional |
| 🎤 Notas de voz y audios por Telegram (transcripción con Whisper) | Funcional |
| ⚙️ Configuración de proveedor activo y cadena de fallback (web y Telegram) | Funcional |
| 🔁 Fallback automático entre proveedores de IA | Funcional |
| 🔐 Acceso al bot restringido por ID de Telegram + secreto de webhook | Funcional |

**Personalidad**: caballero de las sombras, leal y formal, con español neutro (sin acento peninsular). El prompt vive en `core/config.py`.

---

## 🚀 Características

### Chat web
- Interfaz limpia y responsiva en Vue 3.
- Historial de mensajes del usuario y de Igris (el remitente se muestra como "**igris:**").
- Envío con Enter, botón o micrófono.
- Menú: **💬 Chat** y **⚙️ Configuración**.

### Bot de Telegram
- Recibe updates por **webhook** (`/telegram/webhook`); el webhook se registra solo al iniciar el backend.
- Acepta **texto**, **notas de voz** y **archivos de audio**. El audio se transcribe a texto y se trata como una orden normal.
- Solo responde a los IDs de Telegram autorizados (`ALLOWED_TELEGRAM_IDS`); al resto les indica que no están autorizados.
- Valida el secreto del webhook (`TELEGRAM_WEBHOOK_SECRET`) y responde 200 de inmediato, procesando el update en segundo plano para evitar reintentos duplicados de Telegram.

**Comandos:**

| Comando | Qué hace |
|---------|----------|
| `/start`, `/help` | Saludo de Igris |
| `/config` | Muestra el proveedor activo y la cadena de fallback |
| `/setprovider <nombre>` | Cambia el proveedor activo |
| `/setfallback <p1,p2,...>` | Cambia el orden de la cadena de fallback |

### Voz
- **STT (voz a texto)**: `core/stt.py`. Proveedor `local` (Whisper, requiere `ffmpeg` en la imagen) u `openai` (API de Whisper).
- **TTS (texto a voz)**: `core/tts.py`, expuesto en `POST /api/tts`.

### Configuración de IA
- **Proveedores**: `nemotron`, `openai`, `anthropic`, `local` (Ollama). Todos se consumen con el SDK de OpenAI (APIs compatibles).
- **Cadena por defecto**: `nemotron → openai → anthropic → local`.
- Si un proveedor falla (clave inválida, sin créditos, respuesta vacía, sin conexión), Igris pasa al siguiente automáticamente y deja el motivo en el log.
- Los cambios hechos desde la web o Telegram se guardan en `core/settings.json` y aplican de inmediato, pero **no sobreviven a un redeploy completo**. Para dejarlos permanentes, usa variables de entorno en Coolify.

### API del backend

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/chat` | Chat con Igris |
| `GET /api/ai-config` | Configuración actual de IA |
| `PUT /api/ai-config` | Actualiza proveedor activo y cadena de fallback |
| `POST /api/tts` | Texto a voz (devuelve audio) |
| `POST /telegram/webhook` | Webhook de Telegram |
| `GET /health`, `GET /status` | Verificación del servicio |

---

## 🛠️ Stack tecnológico

- **Frontend**: Vue 3 (Composition API), Vue Router, Axios, Tailwind CSS, Vite.
- **Backend**: Python 3.12, FastAPI, Uvicorn, Pydantic, OpenAI SDK, python-telegram-bot, openai-whisper (+ ffmpeg).
- **Base de datos**: PostgreSQL (SQLAlchemy + psycopg2).
- **Despliegue**: Docker, en una instancia **EC2** administrada con **Coolify** (backend y frontend como servicios separados).

---

## 🧩 Estructura del proyecto

```
igris/
├── core/              # brain.py, config.py, stt.py, tts.py, settings_manager.py, database.py, settings.json
├── server/            # main.py (FastAPI: chat, configuración, TTS y webhook de Telegram)
├── node/              # cliente_voice.py, cliente_text.py, cliente_speak.py (Raspberry Pi - opcional)
├── web/               # Aplicación Vue (index.html, package.json, vite.config.js, src/)
├── Dockerfile         # Imagen del backend (Python 3.12-slim + ffmpeg)
├── Dockerfile.web     # Imagen del frontend (Node.js + vite build)
├── requirements.txt
└── README.md
```

---

## ⚙️ Variables de entorno (Coolify)

Se configuran en el servicio de **backend** en Coolify. Después de cambiarlas hay que hacer redeploy o restart.

### IA

| Variable | Descripción | Ejemplo / por defecto |
|----------|-------------|-----------------------|
| `IGRIS_PROVIDER` | Proveedor activo (se intenta primero) | `nemotron` |
| `IGRIS_FALLBACK_CHAIN` | Orden de fallback, separado por comas | `nemotron,openai,anthropic,local` |
| `IGRIS_MAX_TOKENS` | Tokens máximos por respuesta | `2048` |
| `NEMOTRON_API_KEY` | Clave de NVIDIA NIM | `nvapi-...` |
| `NEMOTRON_API_BASE` | URL base de NVIDIA NIM (opcional) | `https://integrate.api.nvidia.com/v1` |
| `IGRIS_NEMOTRON_MODEL` | Modelo de Nemotron (opcional) | `nvidia/nemotron-3-super-120b-a12b` |
| `OPENAI_API_KEY` | Clave de OpenAI | `sk-...` |
| `IGRIS_OPENAI_MODEL` | Modelo de OpenAI (opcional) | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Clave de Anthropic | `sk-ant-...` |
| `IGRIS_ANTHROPIC_MODEL` | Modelo de Anthropic (opcional) | `claude-sonnet-5-5` |
| `IGRIS_LOCAL_URL` | URL de Ollama (debe ser alcanzable desde el contenedor) | `http://localhost:11434` |
| `IGRIS_LOCAL_MODEL` | Modelo local de Ollama (opcional) | `llama3.1` |

### Voz

| Variable | Descripción | Ejemplo / por defecto |
|----------|-------------|-----------------------|
| `IGRIS_STT_PROVIDER` | Proveedor de transcripción: `local` u `openai` | `local` |
| `IGRIS_WHISPER_MODEL` | Modelo de Whisper local (`tiny`, `base`, `small`, `medium`) | `base` |
| `IGRIS_STT_MODEL` | Modelo de Whisper para el proveedor `openai` | `whisper-1` |
| `IGRIS_TTS_PROVIDER` | Proveedor de síntesis de voz | `local` |

### Telegram

| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_TOKEN` | Token del bot (de @BotFather) |
| `ALLOWED_TELEGRAM_IDS` | IDs de Telegram autorizados, separados por comas |
| `TELEGRAM_WEBHOOK_URL` | URL pública del webhook, p. ej. `https://igris.zottagroup.com/telegram/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | Secreto para validar que las peticiones vienen de Telegram |

### Base de datos

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | Conexión a PostgreSQL (usa el prefijo `postgresql://`, no `postgres://`) |

### Ejemplo mínimo

```
IGRIS_PROVIDER=nemotron
IGRIS_FALLBACK_CHAIN=nemotron,openai,anthropic,local
NEMOTRON_API_KEY=nvapi-your-key-here
DATABASE_URL=postgresql://usuario:clave@host:5432/igris

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

1. **Variables de entorno**: configúralas en Coolify → servicio de **backend** (ver tablas anteriores).
2. **Backend**: *Rebuild and Deploy* (si cambiaste el `Dockerfile`, usa *Deploy sin caché*).
3. **Frontend**: *Rebuild and Deploy* en el servicio del frontend.
4. **Probar la web**: abre `https://webigris.zottagroup.com`, ve a **💬 Chat** y escribe "hola".
5. **Probar Telegram**: escribe a tu bot desde un ID autorizado, envía texto y luego una nota de voz.
6. **Probar la configuración**: en **⚙️ Configuración** (o con `/config` y `/setprovider` en Telegram) cambia el proveedor y verifica que el siguiente mensaje lo usa.

### Recomendación: caché del modelo de Whisper
La primera nota de voz tras un despliegue descarga el modelo de Whisper (unos 140 MB para `base`). Para no repetirlo en cada redeploy, monta un **volumen persistente** en `/root/.cache/whisper` (Coolify → backend → Storages).

---

## 🩺 Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `Proveedor 'nemotron' falló: respuesta vacía` | El modelo razona y agota los tokens antes de responder | Subir `IGRIS_MAX_TOKENS` (2048 o más); el log indica el `finish_reason` |
| `Proveedor 'openai'/'anthropic' falló: ... crédito/quota` | Cuenta sin saldo | Recargar saldo o quitar el proveedor de la cadena |
| `Proveedor 'local' falló: Connection error` | `localhost` dentro del contenedor no es el host de Ollama | Definir `IGRIS_LOCAL_URL` con la IP/servicio correcto o quitar `local` de la cadena |
| Telegram: `No such file or directory: 'ffmpeg'` | Falta `ffmpeg` en la imagen | Añadir `ffmpeg` al `apt-get install` del `Dockerfile` y reconstruir sin caché |
| Telegram: audio lento la primera vez | Descarga del modelo de Whisper | Montar volumen en `/root/.cache/whisper` |
| `422 Unprocessable Entity` en `/api/chat` | El body del frontend no coincide con el modelo (`{"text": "..."}`) | Revisar el `detail` de la respuesta en la pestaña Network |
| Telegram responde 403 en el webhook | El secreto no coincide | Verificar `TELEGRAM_WEBHOOK_SECRET` y redeploy (se vuelve a registrar al iniciar) |

---

## 📝 Notas importantes

- **Sin autenticación en la web**: la interfaz y los endpoints `/api/*` son públicos (versión de uso personal). Cualquiera que conozca la URL puede usar tu cuota de IA y cambiar la configuración; considera restringirlos (por ejemplo, con autenticación en el proxy de Coolify).
- **El bot de Telegram sí está protegido**: solo responde a los IDs de `ALLOWED_TELEGRAM_IDS` y valida el secreto del webhook.
- **System prompt** (en `core/config.py`): Igris es un caballero de las sombras leal, formal, de respuestas breves y sin markdown (sus respuestas están pensadas para decirse en voz alta), y se dirige al usuario como "mi señor".
- **Backend y frontend** son servicios separados en Coolify; ambos necesitan sus propias variables de entorno.

---

## 🔗 Enlaces útiles

- [NVIDIA NIM](https://docs.nvidia.com/nim/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [python-telegram-bot](https://docs.python-telegram-bot.org/)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Vue 3](https://vuejs.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Coolify](https://coolify.io/)

---

## 🙏 Créditos

- Modelo **NVIDIA Nemotron 3 Super 120B** por [NVIDIA](https://www.nvidia.com/)
- **FastAPI** por @tiangolo, **Vue 3** por el equipo de Vue, **Tailwind CSS** por el equipo de Tailwind
- **Whisper** por OpenAI
- **Coolify** por simplificar el despliegue con Docker

---

*Última actualización: Octubre 2026*

**¡Disfruta conversando con Iris usando el poder de NVIDIA Nemotron 3 Super 120B y la flexibilidad de cambiar entre proveedores de IA según tus necesidades!** 🚀

---
*Última actualización: Octubre 2026*

# ⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram

> Igris, el caballero de las sombras: un asistente personal tipo Jarvis, leal y formal, que habla en español neutro. Se usa desde una interfaz web con avatar animado a pantalla completa y modo manos libres (le hablas y te responde en voz alta) y desde Telegram (texto, notas de voz y archivos de audio), con modelos de IA intercambiables y una cadena de fallback automática entre proveedores.

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

**Personalidad:** caballero de las sombras, leal y formal, con español neutro (sin acento peninsular). El prompt vive en `core/config.py`.

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

**Comandos:**

| Comando | Qué hace |
| --- | --- |
| `/start`, `/help` | Saludo de Igris |
| `/config` | Muestra el proveedor activo y la cadena de fallback |
| `/setprovider <nombre>` | Cambia el proveedor activo |
| `/setfallback <p1,p2,...>` | Cambia el orden de la cadena de fallback |

### Voz

- **Web (entrada):** reconocimiento de voz del navegador (Web Speech API), en modo manos libres.
- **STT en el backend (Telegram):** `core/stt.py`. Proveedor `local` (Whisper, requiere ffmpeg en la imagen) u `openai` (API de Whisper).
- **TTS (texto a voz):** `core/tts.py`, expuesto en `POST /api/tts`. La web lo reproduce automáticamente tras cada respuesta y mide su volumen con la Web Audio API para animar al avatar.

### Configuración de IA

- **Proveedores:** `nemotron`, `openai`, `anthropic`, `local` (Ollama). Todos se consumen con el SDK de OpenAI (APIs compatibles).
- **Cadena por defecto:** nemotron → openai → anthropic → local.
- Si un proveedor falla (clave inválida, sin créditos, respuesta vacía, sin conexión), Igris pasa al siguiente automáticamente y deja el motivo en el log.
- Los cambios hechos desde la web o Telegram se guardan en `core/settings.json` y aplican de inmediato, pero **no sobreviven a un redeploy completo**. Para dejarlos permanentes, usa variables de entorno en Coolify.

### API del backend

Los endpoints `/api/*` requieren el header `X-Igris-Key` con la clave de acceso (`IGRIS_ACCESS_KEY`). Sin clave o con una incorrecta responden `401`; tras 10 intentos fallidos desde la misma IP en 5 minutos responden `429`.

| Endpoint | Descripción |
| --- | --- |
| `GET /api/auth/check` | Valida la clave. Responde `{"ok": true}`. La usa la pantalla de acceso |
| `POST /api/chat` | Chat con Igris. Body: `{"text": "..."}`. Responde `{"status": "ok", "reply": "..."}` |
| `GET /api/ai-config` | Configuración actual de IA |
| `PUT /api/ai-config` | Actualiza proveedor activo y cadena de fallback |
| `POST /api/tts` | Texto a voz. Body: `{"text": "..."}`. Devuelve audio (`audio/mpeg`) |
| `POST /telegram/webhook` | Webhook de Telegram (usa su propio secreto, no la clave de acceso) |
| `GET /health`, `GET /status` | Verificación del servicio (públicos) |

---

## 🛠️ Stack tecnológico

- **Frontend:** Vue 3 (Composition API), Vue Router, Axios, Tailwind CSS, Vite. Web Speech API (entrada de voz) y Web Audio API (volumen del avatar).
- **Backend:** Python 3.12, FastAPI, Uvicorn, Pydantic, OpenAI SDK, python-telegram-bot, openai-whisper (+ ffmpeg).
- **Base de datos:** PostgreSQL (SQLAlchemy + psycopg2).
- **Despliegue:** Docker, en una instancia EC2 administrada con Coolify (backend y frontend como servicios separados).

---

## 🧩 Estructura del proyecto

```
igris/
├── core/              # brain.py, config.py, stt.py, tts.py, settings_manager.py, database.py, settings.json
├── server/            # main.py (FastAPI: chat, configuración, TTS, acceso con clave y webhook de Telegram)
├── node/              # cliente_voice.py, cliente_text.py, cliente_speak.py (Raspberry Pi - opcional)
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

### Cómo funciona el avatar

- `useIgris.js` expone un estado reactivo compartido: `igris.state` (`idle`, `listening`, `thinking`, `speaking`) e `igris.level` (volumen de 0 a 1; `-1` significa "simulado").
- `Dashboard.vue` cambia el estado con `setIgrisState(...)` según lo que ocurre: al escuchar, al esperar la respuesta del backend y al reproducir el audio de `/api/tts`.
- Mientras suena la voz, `Dashboard.vue` mide el volumen real con un `AnalyserNode` y lo escribe en `igris.level`.
- `IgrisAvatar.vue` lee ese estado y ajusta la velocidad de reproducción, el brillo y el color del video con transiciones suaves.

### Cambiar el video del avatar

Reemplaza `web/public/igris.mp4` por otro video y haz **Rebuild and Deploy** del frontend. Recomendaciones: formato vertical (9:16), sin marca de agua, de pocos MB (GitHub no acepta archivos de más de 25 MB desde el navegador) y, idealmente, en bucle continuo. Si el video tiene otra proporción, ajusta `RATIO` y el `aspect-ratio` en `IgrisAvatar.vue`.

---

## ⚙️ Variables de entorno (Coolify)

Se configuran en el servicio de **backend** en Coolify. Después de cambiarlas hay que hacer redeploy o restart.

### Acceso web

| Variable | Descripción | Ejemplo / por defecto |
| --- | --- | --- |
| `IGRIS_ACCESS_KEY` | Clave única para entrar a la web. **Obligatoria:** si falta o está vacía, el backend rechaza todo `/api/*` con 401 (falla cerrado). Usa solo letras y números | `openssl rand -hex 24` |

### IA

| Variable | Descripción | Ejemplo / por defecto |
| --- | --- | --- |
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
| `TELEGRAM_TOKEN` | Token del bot (de @BotFather) |
| `ALLOWED_TELEGRAM_IDS` | IDs de Telegram autorizados, separados por comas |
| `TELEGRAM_WEBHOOK_URL` | URL pública del webhook, p. ej. `https://igris.zottagroup.com/telegram/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | Secreto para validar que las peticiones vienen de Telegram. **Obligatorio en producción:** si está vacío, el webhook no valida el origen |

### Base de datos

| Variable | Descripción |
| --- | --- |
| `DATABASE_URL` | Conexión a PostgreSQL (usa el prefijo `postgresql://`, no `postgres://`) |

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

1. **Variables de entorno:** configúralas en Coolify → servicio de backend (ver tablas anteriores). No olvides `IGRIS_ACCESS_KEY`.
2. **Backend:** Rebuild and Deploy (si cambiaste el `Dockerfile`, usa Deploy sin caché).
3. **Frontend:** Rebuild and Deploy en el servicio del frontend. Verifica que `web/public/igris.mp4` esté en el repositorio.
4. **Probar la web:** abre `https://webigris.zottagroup.com` con Chrome o Edge. Escribe la clave de acceso, acepta el permiso del micrófono y toca la pantalla una vez. Deberías ver a Igris de fondo; háblale o usa ✉️ Enviar para escribir "hola".
5. **Probar Telegram:** escribe a tu bot desde un ID autorizado, envía texto y luego una nota de voz.
6. **Probar la configuración:** en ⚙️ Configuración (o con `/config` y `/setprovider` en Telegram) cambia el proveedor y verifica que el siguiente mensaje lo usa.

Para probar el frontend en local: entra a `web/` y ejecuta `npm install` y `npm run dev`.

Si cambias `IGRIS_ACCESS_KEY`, haz redeploy del backend: los navegadores que tengan guardada la clave anterior volverán solos a la pantalla de acceso.

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

---

## 📝 Notas importantes

- **Acceso con clave única en la web:** la interfaz pide una clave (`IGRIS_ACCESS_KEY`) en `/acceso`. El navegador la guarda en `localStorage` y la envía en el header `X-Igris-Key` a `/api/chat`, `/api/tts`, `/api/ai-config` y `/api/auth/check`. El backend compara la clave en tiempo constante, rechaza todo si la variable no está definida y responde 429 tras 10 intentos fallidos desde una IP en 5 minutos. `/health`, `/status` y el webhook de Telegram no usan esta clave. No hay usuarios, sesiones ni base de datos para el acceso.
- **CORS:** el backend solo acepta peticiones del frontend (`https://webigris.zottagroup.com`) y de `http://localhost:5173` para desarrollo, con los métodos `GET`, `POST`, `PUT` y `OPTIONS` y los headers `Content-Type` y `X-Igris-Key`.
- **El bot de Telegram tiene su propia protección:** solo responde a los IDs de `ALLOWED_TELEGRAM_IDS` y valida el secreto del webhook.
- **System prompt** (en `core/config.py`): Igris es un caballero de las sombras leal, formal, de respuestas breves y sin markdown (sus respuestas están pensadas para decirse en voz alta), y se dirige al usuario como "mi señor".
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

---

*Última actualización: Octubre 2026*

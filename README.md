# ⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram
> Igris, el caballero de las sombras: un asistente personal tipo Jarvis, leal y formal, que habla en español neutro. Se usa desde una interfaz web con avatar animado a pantalla completa y modo manos libres (le hablas y te responde en voz alta) y desde Telegram (texto, notas de voz y archivos de audio), con modelos de IA intercambiables, una cadena de fallback automática entre proveedores y herramientas para consultar la hora, el clima, el correo y el calendario, y para guardar recordatorios y notas.
[![GitHub](https://img.shields.io/badge/GitHub-murilloleonel939--art%2Figris-blue)](https://github.com/murilloleonel939-art/igris) [![Python](https://img.shields.io/badge/Python-3.12%2B-green)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/) [![Vue](https://img.shields.io/badge/Vue-3.3-4FC08D)](https://vuejs.org/)
---
## ✅ Qué hace Igris hoy
| Capacidad | Estado |
| --- | --- |
| 💬 Chat web con Igris | Funcional |
| 🔑 Acceso a la web con clave única (`IGRIS_ACCESS_KEY`) | Funcional |
| 👥 **Área de usuarios**: cuentas con usuario y contraseña, chat propio | Funcional |
| 🛠️ **Panel de gestión de usuarios** (crear, activar/desactivar, borrar, cambiar contraseña) | Funcional |
| 🗣️ **Trato personalizado por usuario**: el administrador configura cómo se dirige Igris a cada cuenta | Funcional |
| 📲 **Instalable como app (PWA)**, con una app para el administrador y otra para los usuarios | Funcional |
| 🧑‍🎤 Avatar animado (video) a pantalla completa que cambia según escucha, piensa o habla | Funcional |
| 🎧 Modo manos libres siempre activo: solo le hablas | Funcional (Chrome/Edge) |
| 🔊 Respuesta hablada automática (`/api/tts`) y botón de altavoz para repetir cada respuesta | Funcional |
| ⌨️ Botón Enviar que abre un cuadro de texto para escribir | Funcional |
| 🤖 Bot de Telegram (texto) | Funcional |
| 🎤 Notas de voz y audios por Telegram (transcripción con Whisper) | Funcional |
| ⚙️ Configuración de proveedor activo y cadena de fallback (web y Telegram) | Funcional |
| 🔁 Fallback automático entre proveedores de IA | Funcional |
| 🔐 Acceso al bot restringido por ID de Telegram + secreto de webhook | Funcional |
| 🧠 Memoria de conversación (por sesión: `web:<id>`, `tg:<id>` y `user:<id>:<conv>`) | Funcional |
| 🕒 Hora y fecha de Colombia | Funcional |
| 🌦️ Clima de una ciudad | Funcional |
| 📧 Gmail (lectura de la bandeja) | Funcional |
| 📅 Google Calendar: consultar agenda y crear eventos con confirmación obligatoria | Funcional |
| ⏰ Recordatorios con aviso por Telegram (únicos, diarios o semanales) | Nuevo |
| 📝 Notas: anotar, listar, buscar y borrar | Nuevo |
| 🧪 Suite de pruebas end-to-end (226 comprobaciones, reejecutable) | Funcional |
**Personalidad:** caballero de las sombras, leal y formal, con español neutro (sin acento peninsular). El prompt vive en `core/config.py`; las instrucciones de herramientas, en `TOOLS_PROMPT` de `core/brain.py`.
---
## 🔐 Las dos superficies de acceso

Igris tiene **dos formas de entrar que no se mezclan**. Un token de usuario nunca sirve en las rutas de administración, y la clave de administrador nunca sirve en las de usuario. El rol va firmado dentro del token, así que el navegador no puede añadirlo ni modificarlo.

| | Administrador | Usuarios |
| --- | --- | --- |
| Pantalla | `/acceso` | `/u/login` |
| Cómo se autentica | Clave única en el header `X-Igris-Key` | Usuario + contraseña → token JWT (`Authorization: Bearer`) |
| Dónde se guarda | `localStorage` (sobrevive al cierre del navegador) | `sessionStorage` (la sesión termina al cerrar) |
| Duración | Mientras no se borre la clave | 12 horas |
| Rutas | `/`, `/config`, `/panel/usuarios` | `/u` |

La clave del administrador vive **solo** en la variable de entorno `IGRIS_ACCESS_KEY` (Coolify). El frontend nunca la contiene: se escribe a mano en la pantalla `/acceso` y se envía en cada petición.

**Límites de intentos**, independientes entre sí para que nadie pueda bloquear el acceso del otro:

| Superficie | Fallos permitidos | Ventana | Cuenta por |
| --- | --- | --- | --- |
| Clave de administrador | 10 | 5 minutos | IP |
| Login de usuario | 8 | 5 minutos | IP + usuario |

Los dos límites viven en memoria, así que se reinician al reiniciar el backend.

### Herramienta de administración de usuarios (`/panel/usuarios`)

| Método | Ruta | Qué hace |
| --- | --- | --- |
| `GET` | `/api/admin/users` | Lista los usuarios (nunca devuelve el hash de la contraseña) |
| `POST` | `/api/admin/users` | Crea un usuario (`username`, `email`, `password`) |
| `PUT` | `/api/admin/users/{id}` | Edita, activa/desactiva o cambia la contraseña |
| `DELETE` | `/api/admin/users/{id}` | Borra un usuario |
| `GET` | `/api/admin/features` | Catálogo de funciones que se pueden habilitar |

Reglas de validación: usuario de 3 a 32 caracteres (`A-Z a-z 0-9 . _ -`), correo con formato válido y contraseña de **8 caracteres como mínimo**. Un usuario desactivado no puede entrar ni seguir usando el token que ya tuviera.

El historial de conversación de cada usuario se aísla con una clave que construye **el servidor**:

```
user:<id del token>:<identificador de conversación>
```

El identificador que manda el navegador solo separa las conversaciones propias de ese usuario: no puede alcanzar la sesión de otro aunque lo manipule.

### Funciones por usuario (permisos)

El administrador decide **qué puede hacer cada usuario**, y ese permiso se comprueba en el servidor, no en el texto que se le envía al modelo. Son dos capas:

1. **El modelo solo ve las herramientas permitidas.** `core/brain.py` filtra los esquemas que se le ofrecen; si no tiene el correo habilitado, la herramienta ni siquiera aparece en su lista.
2. **El servidor rechaza lo no permitido.** `core/tools/__init__.py` vuelve a comprobar el permiso en `run_tool()` antes de ejecutar nada. Aunque el modelo intentara llamar a una herramienta que no le corresponde (por un prompt inyectado en un correo, por ejemplo), la ejecución se corta y se le responde que esa función no está habilitada.

| Función | Qué abre | Necesita Google |
| --- | --- | --- |
| `time` | Hora y fecha | No |
| `weather` | El tiempo | No |
| `email` | Leer el correo | Sí |
| `calendar` | Leer el calendario | Sí |
| `calendar_write` | **Crear** eventos en el calendario | Sí |
| `notes` | Notas propias (anotar, buscar, borrar) | No |
| `reminders` | Recordatorios con aviso por Telegram | No |

`time` y `weather` vienen activas de fábrica; el resto hay que abrirlas desde `/panel/usuarios`. El catálogo vive en `core/capabilities.py`, y el panel se construye a partir de él: añadir una función ahí la hace aparecer sola en la interfaz.

**Aislamiento de datos.** Cada nota, recordatorio y sesión lleva su `user_id`, que el servidor deriva **solo** de la identidad autenticada (el token de la web o el chat de Telegram vinculado), nunca de lo que envíe el cliente. Un usuario no puede leer, borrar ni alcanzar los datos de otro. `calendar_write` es un permiso aparte a propósito: quien puede leer su agenda no tiene por qué poder escribir en ella.

### Área de usuarios (`/u`)

| Método | Ruta | Qué hace |
| --- | --- | --- |
| `POST` | `/api/user/login` | Entra y devuelve el token |
| `GET` | `/api/user/me` | Devuelve la sesión actual |
| `POST` | `/api/user/chat` | Habla con Igris (historial aislado por usuario) |
| `POST` | `/api/user/tts` | Convierte texto en voz |
| `GET` | `/api/user/connections` | Qué tiene conectado y qué le falta (alimenta «Conexiones» en `/u`) |
| `GET` | `/api/user/google/start` | Devuelve la URL de consentimiento de Google |
| `GET` | `/api/user/google/callback` | Recibe el código de Google y guarda el permiso del usuario |
| `DELETE` | `/api/user/google` | Desconecta su cuenta de Google |
| `POST` | `/api/user/telegram/code` | Genera el código de vinculación de Telegram |
| `DELETE` | `/api/user/telegram` | Desvincula su Telegram |

La sección **«Conexiones»** de `/u` es donde el usuario conecta su Google y vincula su Telegram. Solo aparecen las que le hacen falta: a quien no tiene correo ni calendario habilitados no se le pide conectar Google.

---
## 📲 Instalable como aplicación (PWA)

El frontend se puede instalar como app en el teléfono. **Son dos aplicaciones distintas**, porque el administrador y los usuarios entran por pantallas diferentes y cada una tiene que abrir donde le corresponde:

| | App del administrador | App de los usuarios |
| --- | --- | --- |
| Pantalla desde la que se instala | `/acceso` | `/u/login` |
| Abre en | `/acceso` | `/u/login` |
| Nombre | IGRIS Admin | IGRIS |
| Manifest | `/manifest-admin.webmanifest` | `/manifest.webmanifest` |

Puedes tener **las dos instaladas a la vez** en el mismo teléfono: llevan `id` distinto, y eso es lo que hace que el navegador las trate como dos apps en lugar de sobrescribir una con la otra. Se distinguen por el nombre bajo el icono.

**Cómo funciona.** El navegador decide qué manifest usa leyendo el `<link rel="manifest">` del HTML, así que `web/server.js` sirve el mismo `index.html` cambiando ese enlace según la ruta: `/u` y `/u/*` llevan el de usuarios, todo lo demás el del administrador. El HTML se sirve **sin caché** a propósito — si el navegador guardara el de una ruta, se quedaría con el enlace equivocado y volvería a abrir en el área que no es. Para la navegación interna de la SPA (que no recarga) está `syncManifest()` en `web/src/pwa.js`, llamado desde el router.

**Iconos.** `scripts/generate_icons.py` los genera con Pillow a partir de `web/src-assets/igris-icon-source.png`. Los `maskable` llevan el personaje al 82% sobre un fondo del mismo color, porque Android recorta esos iconos en círculo y si no se comería las puntas de las hombreras.

**iOS:** Safari no ofrece el aviso automático de instalación, hay que hacerlo a mano con **Compartir → Añadir a pantalla de inicio**. En Android/Chrome aparece un botón **📲 Instalar** en las pantallas de acceso.

> Al cambiar de versión, el icono de una app ya instalada puede tardar en actualizarse: hay que desinstalarla y volver a instalarla.

---
## 🧪 Pruebas

**226 comprobaciones, 0 fallidas**, y todas se pueden ejecutar las veces que haga falta sin limpiar nada a mano.

| Suite | Qué cubre | Comprobaciones |
| --- | --- | --- |
| `tests/e2e_users.py` | Área de usuarios y panel: separación de las dos superficies, token manipulado, usuario desactivado, CORS, aislamiento del historial, límite de intentos, borrado, permisos por función, vinculación de Telegram, aislamiento de notas y recordatorios, cifrado, permisos de Google | 127 |
| `tests/e2e_via_frontend.py` | Todo **a través del servidor del frontend**, que es el camino real en producción: proxy, PWA, manifests por ruta, flujo completo de usuario | 40 |
| `tests/test_telegram.py` | Webhook de Telegram y enrutado de recordatorios: quién entra y quién no, vinculación con código de un solo uso, identidad y permisos por chat, que un usuario no pueda cambiar la configuración global, y que ningún aviso acabe en el chat de otra persona | 37 |
| `tests/test_postgres.py` | Traducción de la URL de conexión, reintentos al arrancar, creación automática de la base, parámetros del motor, aviso de SQLite en producción | 22 |

```bash
bash scripts/run_tests.sh            # las cuatro suites
bash scripts/run_tests.sh users      # solo el área de usuarios
bash scripts/run_tests.sh frontend   # solo el frontend (necesita el frontend vivo)
bash scripts/run_tests.sh telegram   # solo Telegram y recordatorios
bash scripts/run_tests.sh postgres   # solo la parte de PostgreSQL
```

Para la suite del frontend hace falta, además, el servidor del frontend levantado:

```bash
cd web && PORT=3100 node server.js
```

**Por qué un script y no los archivos sueltos.** Las dos suites end-to-end hablan con un backend real y usan la **misma** base SQLite (`igris_test.db`). Si se levantan los dos backends a la vez, al borrar la base para empezar limpio el primero se queda con el archivo viejo abierto (en Linux, borrar un archivo abierto no lo elimina mientras alguien lo tenga abierto) y todo empieza a fallar con `attempt to write a readonly database`, 500 al crear usuarios y 409 de "ya existe" para usuarios recién borrados. El script levanta **un solo backend cada vez**, borra la base antes de cada suite y para el backend antes de pasar a la siguiente.

### PostgreSQL

En producción la base es PostgreSQL (`DATABASE_URL`); SQLite solo se usa en local y **pierde los datos en cada despliegue** si no hay un volumen persistente (el propio backend avisa de esto en los logs).

`core/database.py` se encarga de:

- Traducir `postgres://` a `postgresql+psycopg://` (Coolify y Heroku entregan el primero, que SQLAlchemy ya no acepta).
- `pool_pre_ping` y `pool_recycle`, para no reutilizar conexiones que el servidor ya cerró.
- Reintentar la conexión al arrancar y fallar con un mensaje claro si nunca responde.
- Crear la base automáticamente si no existe (consultando antes `pg_database`, y con el nombre entrecomillado para evitar inyección).

**Lo que no cubre la suite:** el chat con IA no se puede probar en vivo sin claves de proveedor — sin ninguna configurada responde `Todos los proveedores fallaron`, y eso es lo esperado. El resto del flujo (autenticación, aislamiento, permisos, proxy, PWA) sí está cubierto de extremo a extremo.

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
Hay **dos interfaces**: la del administrador (la que se describe aquí) y la del área de usuarios (`/u`), más simple y sin menú de administración.

La pantalla del chat del administrador funciona como un asistente de voz:
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
- **Menú (administrador):** 💬 Chat, ⚙️ Configuración, 👥 Usuarios y Salir.
- **Área de usuarios (`/u`):** interfaz propia y más simple, sin menú de administración. El usuario solo ve su chat y su nombre con un botón para salir. No puede alcanzar Configuración ni el panel de usuarios.
- **Instalar como app:** en las pantallas de acceso (`/acceso` y `/u/login`) aparece un botón **📲 Instalar** (ver **Instalable como aplicación (PWA)**).
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
- Cada conversación tiene su historial (`core/session_store.py`): `web:<id>` en la web del administrador (si el frontend no envía `session_id`, usa `web:default`), `tg:<id de Telegram>` en Telegram, y `user:<id>:<conv>` en el área de usuarios (la clave la construye el servidor, ver **Las dos superficies de acceso**).
- El chat de cada usuario está aislado: el identificador que manda el navegador no puede alcanzar la conversación de otro.
- Se recuerdan los últimos 6 turnos (`IGRIS_HISTORY_TURNS`). Las sesiones expiran tras 2 horas sin uso y hay un máximo de 200.
- **Viven en memoria:** se pierden al reiniciar o redesplegar el backend (también una propuesta de evento pendiente de confirmar). Funciona con un solo worker de Uvicorn. Las cuentas de usuario, los recordatorios y las notas sí se guardan en la base de datos.
### Voz
- **Web (entrada):** reconocimiento de voz del navegador (Web Speech API), en modo manos libres.
- **STT en el backend (Telegram):** `core/stt.py`. Proveedor `local` (Whisper, requiere ffmpeg en la imagen) u `openai` (API de Whisper). Ojo con los nombres: `IGRIS_WHISPER_MODEL` elige el modelo **local** y `IGRIS_STT_MODEL` el de la API; cada uno solo se lee en su propia ruta, así que definir el que no corresponde no tiene efecto.
- **TTS (texto a voz):** `core/tts.py`, expuesto en `POST /api/tts`. La web lo reproduce automáticamente tras cada respuesta y mide su volumen con la Web Audio API para animar al avatar.
### Configuración de IA
- **Proveedores:** `nemotron`, `openai`, `anthropic`, `local` (Ollama). `nemotron`, `openai` y `local` se consumen con el SDK de OpenAI (APIs compatibles con `/v1/chat/completions`). **`anthropic` es la excepción:** Claude solo se sirve por el protocolo nativo de Anthropic (`/v1/messages`, con `x-api-key`), así que usa el SDK `anthropic` y su propio bucle de herramientas (`_complete_with_anthropic`); enviarlo por `/v1/chat/completions` devuelve `protocol_mismatch`. Por eso su URL base **no lleva `/v1`**: el SDK añade `/v1/messages`. La lista válida está en `PROVIDERS` de `core/brain.py` y debe coincidir con `AVAILABLE_PROVIDERS` de `core/config.py`.
- **Cadena por defecto:** nemotron → openai → anthropic → local.
- Si un proveedor falla (clave inválida, sin créditos, respuesta vacía, sin conexión), Igris pasa al siguiente automáticamente y deja el motivo en el log.
- Los cambios hechos desde la web o Telegram se guardan en `core/settings.json` y aplican de inmediato, pero **no sobreviven a un redeploy completo**. Para dejarlos permanentes, usa variables de entorno en Coolify.
- Un `settings.json` antiguo que contenga un proveedor que ya no existe (por ejemplo `groq`) se limpia al cargarse y no rompe nada. `GET /status` y `GET /api/ai-config` solo listan proveedores válidos, y `PUT /api/ai-config` y `/setprovider` rechazan los inválidos.
### API del backend
Los endpoints `/api/*` del administrador requieren el header `X-Igris-Key` con la clave de acceso (`IGRIS_ACCESS_KEY`). Sin clave o con una incorrecta responden `401`; tras 10 intentos fallidos desde la misma IP en 5 minutos responden `429`.

Los del área de usuarios (`/api/user/*`) se autentican con `Authorization: Bearer <token>`, y los del panel (`/api/admin/*`) con la misma clave del administrador. La tabla completa de unos y otros está en **Las dos superficies de acceso**.

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
## 🧩 Estructura del proyecto
```
igris/
├── core/
│   ├── brain.py               # Orquesta proveedores con fallback, bucle de tool calling y TOOLS_PROMPT
│   ├── config.py              # Proveedores válidos, modelos por defecto y system prompt
│   ├── settings_manager.py    # core/settings.json (configuración de IA persistente, con limpieza de proveedores inválidos)
│   ├── session_store.py       # Sesiones de conversación en memoria (web:<id>, tg:<id>, user:<id>:<conv>)
│   ├── database.py            # SQLAlchemy: modelos (incluye User, Reminder y Note) e init_db
│   ├── scheduler.py           # Planificador de avisos de recordatorios (tarea en segundo plano)
│   ├── stt.py, tts.py         # Voz
│   ├── settings.json
│   └── tools/                 # Herramientas de Igris (ver lista abajo)
├── server/
│   ├── main.py                # FastAPI: chat, configuración, TTS, acceso con clave, webhook de Telegram y planificador
│   └── user_routes.py         # Área de usuarios (/api/user/*) y panel de administración (/api/admin/*)
├── node/              # cliente_voice.py, cliente_text.py, cliente_speak.py (Raspberry Pi - opcional)
├── scripts/
│   ├── run_tests.sh           # Ejecuta las cuatro suites en el orden correcto (ver Pruebas)
│   └── generate_icons.py      # Genera los iconos de la PWA con Pillow
├── tests/
│   ├── e2e_users.py           # Área de usuarios y panel (127 comprobaciones)
│   ├── e2e_via_frontend.py    # Flujo real a través del frontend (40 comprobaciones)
│   ├── test_telegram.py       # Telegram y recordatorios (37 comprobaciones)
│   └── test_postgres.py       # PostgreSQL y arranque de la base (22 comprobaciones)
├── web/               # Aplicación Vue
│   ├── server.js              # Sirve dist/, inyecta el manifest según la ruta y hace de proxy hacia el backend
│   ├── index.html             # HTML de la SPA (manifest del administrador como predeterminado)
│   ├── public/
│   │   ├── igris.mp4              # Video del avatar (se sirve como /igris.mp4)
│   │   ├── sw.js                  # Service worker (red primero, caché como rescate)
│   │   ├── manifest-admin.webmanifest  # App del administrador (abre en /acceso)
│   │   ├── manifest.webmanifest        # App de los usuarios (abre en /u/login)
│   │   └── icons/                 # Iconos generados (192, 512, maskable, apple-touch, favicon)
│   ├── src-assets/
│   │   └── igris-icon-source.png  # Imagen original de la que salen los iconos
│   └── src/
│       ├── App.vue                # Menú (con botón Salir) + avatar de fondo (solo en la ruta Chat)
│       ├── router.js              # Rutas de las dos superficies + guards de clave y de token
│       ├── api.js                 # Cliente Axios del administrador (X-Igris-Key, localStorage)
│       ├── userApi.js             # Cliente Axios de usuarios (Bearer, sessionStorage)
│       ├── pwa.js                 # Instalación de la PWA y sincronización del manifest por ruta
│       ├── components/
│       │   ├── IgrisAvatar.vue    # Video con efectos según estado y volumen
│       │   ├── IgrisHero.vue      # Avatar a pantalla completa + texto de estado
│       │   └── InstallHint.vue    # Aviso y botón para instalar la app
│       ├── composables/
│       │   └── useIgris.js        # Estado compartido: igris.state y igris.level
│       └── pages/
│           ├── Access.vue         # Acceso del administrador (clave única)
│           ├── Dashboard.vue      # Chat del administrador: voz, manos libres, TTS, historial y texto
│           ├── Configuration.vue  # Proveedor activo y cadena de fallback
│           ├── AdminUsers.vue     # Panel de gestión de usuarios
│           ├── UserLogin.vue      # Acceso de usuarios (usuario y contraseña)
│           └── UserChat.vue       # Chat del usuario
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
### Acceso
| Variable | Descripción | Ejemplo / por defecto |
| --- | --- | --- |
| `IGRIS_ACCESS_KEY` | **Clave del administrador.** Es la que se escribe en `/acceso` y sirve para el panel, la configuración y el panel de usuarios. **Obligatoria:** si falta o está vacía, el backend rechaza todo `/api/*` con 401 (falla cerrado). Usa solo letras y números | `openssl rand -hex 24` |

Los **usuarios** no usan esta variable: tienen su propia cuenta (usuario y contraseña) creada desde el panel, y entran por `/u/login`. Sus cuentas se guardan en la base de datos (`DATABASE_URL`).

**Cookies y CORS:** ni la clave ni el token viajan en cookies, así que el backend va sin `allow_credentials`. Cada header que envíe el frontend tiene que estar en `allow_headers` y cada método en `allow_methods`; si falta uno, el navegador bloquea la petición antes de enviarla.
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
| `OPENAI_API_KEY` | Clave de OpenAI (con pateway, la que emite pateway) | `sk-...` |
| `OPENAI_API_BASE` | URL base del proveedor `openai` (opcional) | `https://api.pateway.ai/v1` |
| `IGRIS_OPENAI_MODEL` | Modelo del proveedor `openai` (opcional) | `gpt-6-luna` |
| `ANTHROPIC_API_KEY` | Clave de Anthropic (con pateway, la que emite pateway) | `sk-...` |
| `ANTHROPIC_API_BASE` | URL base del proveedor `anthropic` (opcional) | `https://api.pateway.ai` |
| `IGRIS_ANTHROPIC_MODEL` | Modelo del proveedor `anthropic` (opcional) | `claude-haiku-4-5-20251001` |
| `IGRIS_LOCAL_URL` | URL de Ollama (debe ser alcanzable desde el contenedor) | `http://localhost:11434` |
| `IGRIS_LOCAL_MODEL` | Modelo local de Ollama (opcional) | **qwen2.5:3b** |
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

Los usuarios pueden vincular **su propio** Telegram desde su página, en «Conexiones»: piden un código de 6 dígitos y lo envían al bot como `/start <código>`. A partir de ahí Igris los atiende como esa persona, con sus permisos y sus datos, y sus recordatorios le llegan a su chat. El código es de un solo uso y caduca a los 15 minutos. `ALLOWED_TELEGRAM_IDS` sigue funcionando igual para el dueño de la instalación, y solo esos chats pueden usar `/config`, `/setprovider` y `/setfallback`.

### Google (correo y calendario)
Para que los usuarios lean su correo y su calendario hace falta un proyecto en Google Cloud. **Cada usuario conecta su propia cuenta**; el token de cada uno se guarda cifrado en la base.

| Variable | Descripción |
| --- | --- |
| `GOOGLE_CLIENT_ID` | ID de cliente OAuth 2.0 (tipo «Aplicación web») |
| `GOOGLE_CLIENT_SECRET` | Secreto del cliente OAuth 2.0 |
| `GOOGLE_REFRESH_TOKEN` | Opcional. Cuenta compartida del administrador, para el panel cuando no hay usuario identificado |
| `GOOGLE_REDIRECT_URI` | Opcional. Por defecto `https://webigris.zottagroup.com/api/user/google/callback` |
| `SECRET_KEY` | **Obligatoria.** Además de firmar los tokens, de ella se deriva la clave que cifra los refresh tokens de Google |

Pasos en Google Cloud Console:
1. Crear un proyecto y **habilitar la Gmail API y la Google Calendar API**. Si no se habilitan, la conexión funciona pero leer el correo o el calendario devuelve error.
2. En «Credenciales», crear un **ID de cliente OAuth** de tipo *Aplicación web*.
3. En «URI de redireccionamiento autorizados», añadir **exactamente** el que devuelve `GET /api/user/connections` (campo `google.redirect_uri`), por defecto `https://webigris.zottagroup.com/api/user/google/callback`. Si no coincide hasta el último carácter, Google rechaza la conexión con `redirect_uri_mismatch`.
4. Configurar la pantalla de consentimiento. Mientras la aplicación no esté verificada por Google, hay que añadir a cada usuario como «usuario de prueba» o no podrá autorizar.
5. Copiar el ID y el secreto a las variables del backend.

> ⚠️ **Cambiar `SECRET_KEY` obliga a todos los usuarios a reconectar su Google.** Los tokens guardados se cifran con una clave derivada de ella; si cambia, dejan de poder descifrarse. Igris se lo dice al usuario con un mensaje distinto («vuelve a conectarla») en lugar del genérico de «no has conectado», para que no busque un problema que no existe. No se pierden datos: solo hay que volver a autorizar.

Los permisos de Google se piden **según lo que el administrador haya habilitado** a ese usuario. A quien no tiene correo ni calendario activados no se le pide ningún permiso, y a quien solo tiene lectura de calendario no se le pide el de escritura.

### Base de datos
| Variable | Descripción |
| --- | --- |
| `DATABASE_URL` | Conexión a PostgreSQL. Acepta `postgresql://`, `postgres://` o `postgresql+psycopg://`; el backend la convierte solo al prefijo del driver psycopg 3. **Es obligatoria en producción:** sin ella se usa SQLite local (`./igris.db`) dentro del contenedor y **las cuentas de usuario, los recordatorios y las notas se pierden en cada despliegue**. Al arrancar, el log dice `Base de datos activa: postgresql` (o `sqlite`) |
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
IGRIS_LOCAL_MODEL=qwen2.5:3b
```
### Ejemplo: `openai` y `anthropic` a través de pateway
Los proveedores `openai` y `anthropic` no tienen por qué apuntar a OpenAI y Anthropic directamente: basta con cambiar la URL base y usar la clave que emite el agregador. Con [pateway](https://pateway.ai) queda así:
```
OPENAI_API_KEY=sk-tu-clave-de-pateway
OPENAI_API_BASE=https://api.pateway.ai/v1
IGRIS_OPENAI_MODEL=gpt-6-luna

ANTHROPIC_API_KEY=sk-tu-clave-de-pateway
ANTHROPIC_API_BASE=https://api.pateway.ai
IGRIS_ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```
> ⚠️ **Las dos URL base no son iguales.** La de `openai` lleva `/v1`; la de `anthropic` **no**, porque el SDK de Anthropic añade `/v1/messages` por su cuenta (con `/v1` la petición iría a `/v1/v1/messages`). Cada proveedor usa su propia variable de clave: no se comparten.
> 🔒 **Nunca subas el archivo `.env` al repositorio.** Las claves viven solo en las variables de Coolify. Si alguna clave se publicó alguna vez, regenérala.
---
## ▶️ Despliegue
Backend y frontend son **dos servicios separados** en Coolify, con sus propias variables y su propio deploy. Un cambio en `web/` no se ve hasta desplegar el frontend (el backend no sirve la interfaz).

1. **Variables de entorno:** configúralas en Coolify → servicio de backend (ver tablas anteriores). No olvides `IGRIS_ACCESS_KEY` (la del administrador) y `DATABASE_URL`.
2. **Backend:** Rebuild and Deploy (si cambiaste el `Dockerfile` o `requirements.txt`, usa Deploy sin caché). Al arrancar, las tablas que falten (`users`, `reminders`, `notes`) se crean solas.
3. **Revisar los logs del backend:** deben aparecer `Base de datos activa: postgresql` y `Planificador de recordatorios iniciado (cada 30 s)`.
4. **Frontend:** Rebuild and Deploy en el servicio del frontend (base `/web`, build `npm install && npm run build`, arranque `npm start`, puerto 3000). Verifica que `web/public/igris.mp4` esté en el repositorio.
5. **Probar la web del administrador:** abre `https://webigris.zottagroup.com/acceso` con Chrome o Edge. Escribe la clave, acepta el permiso del micrófono y toca la pantalla una vez. Deberías ver a Igris de fondo; háblale o usa ✉️ Enviar para escribir "hola".
6. **Probar el área de usuarios:** crea un usuario en `/panel/usuarios` y entra con él en `https://webigris.zottagroup.com/u/login`. Cada usuario debe ver su propio chat.
7. **Probar Telegram:** escribe a tu bot desde un ID autorizado, envía texto y luego una nota de voz.
8. **Probar la configuración:** en ⚙️ Configuración (o con `/config` y `/setprovider` en Telegram) cambia el proveedor y verifica que el siguiente mensaje lo usa. `GET /status` no debe listar `groq`.

Para probar el frontend en local: entra a `web/` y ejecuta `npm install` y `npm run dev`. Para probar el frontend **tal como queda en producción** (con el proxy y los manifests por ruta), usa `npm run build && PORT=3100 node server.js`.

Si cambias `IGRIS_ACCESS_KEY`, haz redeploy del backend: los navegadores que tengan guardada la clave anterior volverán solos a la pantalla de acceso.

**Sobre la app instalada (PWA):** al desplegar una versión nueva, los iconos de una app ya instalada pueden tardar en actualizarse, y la dirección de arranque de una app instalada **no cambia** aunque se despliegue (la fija el navegador al instalarla). Si has cambiado algo de la PWA, hay que **desinstalarla y volver a instalarla**.
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
Para ejecutar las pruebas automáticas: `bash scripts/run_tests.sh` desde la raíz del repositorio (ver la sección **Pruebas** más arriba). Son 226 comprobaciones y se pueden repetir sin limpiar nada a mano.
### Verificar el acceso con `curl`
```bash
API=https://igris.zottagroup.com
curl -i $API/api/auth/check                                  # sin clave: 401
curl -i -H "X-Igris-Key: TU_CLAVE" $API/api/auth_check       # con clave: 200 {"ok":true}
curl -i -X OPTIONS $API/api/chat \
  -H "Origin: https://webigris.zottagroup.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-igris-key"   # preflight: 200 y x-igris-key permitido
```
### Recomendación: caché del modelo de Whisper
La primera nota de voz tras un despliegue descarga el modelo de Whisper (unos 140 MB para `base`). Para no repetirlo en cada redeploy, monta un volumen persistente en `/root/.cache/whisper` (Coolify → backend → Storages).
### PyTorch solo CPU
El servidor no tiene GPU, así que el `Dockerfile` instala `torch==2.3.0` desde el índice de CPU de PyTorch **antes** de `requirements.txt`. Así `openai-whisper` encuentra `torch` ya instalado y no descarga la versión con CUDA (varios GB). La versión del `Dockerfile` debe coincidir con la de `requirements.txt`. Para comprobarlo dentro del contenedor del backend: `pip list | grep -i -E "^(torch|nvidia)"` debe mostrar solo `torch 2.3.0+cpu`.
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
| `Proveedor 'anthropic' falló: 400 - protocol_mismatch` ("No compatible provider available for this request format") | Un modelo Claude se envió por `/v1/chat/completions` en formato OpenAI; Claude solo se sirve por `/v1/messages` | No apuntes `anthropic` a un modelo GPT ni fuerces el SDK de OpenAI. Con un agregador, comprueba que `ANTHROPIC_API_BASE` **no** lleve `/v1`. Si sale `<url>/v1/v1/messages` en el log, sobra un `/v1` |
| `Proveedor 'anthropic'` da 404 y la URL acaba en `/v1/v1/messages` | La URL base lleva `/v1` pero el SDK añade `/v1/messages` | Definir `ANTHROPIC_API_BASE` sin `/v1` (por ejemplo `https://api.pateway.ai`) |
| `Proveedor 'anthropic' falló: ... unexpected keyword argument 'temperature'` | Versión del SDK `anthropic` distinta a la esperada | Fijar la versión en `requirements.txt`; `brain.py` no envía `temperature` en esa ruta, así que solo aparece si se añade a mano |
| Falla un modelo de un agregador y otro no | Protocolos separados: unos modelos van por `/v1/chat/completions` y otros por `/v1/messages` | Comprobar en la documentación del agregador por qué ruta sirve cada modelo, y qué id exacto usa (suele listarse en `GET /v1/models`; algunos devuelven listas distintas según el header de autenticación) |
| `Proveedor 'local' falló: Connection error` | `localhost` dentro del contenedor no es el host de Ollama | Definir `IGRIS_LOCAL_URL` con la IP/servicio correcto o quitar `local` de la cadena |
| Telegram: `No such file or directory: 'ffmpeg'` | Falta ffmpeg en la imagen | Añadir `ffmpeg` al `apt-get install` del `Dockerfile` y reconstruir sin caché |
| Telegram: audio lento la primera vez | Descarga del modelo de Whisper | Montar volumen en `/root/.cache/whisper` |
| `422 Unprocessable Entity` en `/api/chat` | El body del frontend no coincide con el modelo (`{"text": "..."}`) | Revisar el `detail` de la respuesta en la pestaña Network |
| Telegram responde 403 en el webhook | El secreto no coincide | Verificar `TELEGRAM_WEBHOOK_SECRET` y redeploy (se vuelve a registrar al iniciar) |
| El deploy del backend se cuelga o el disco se llena | Caché de build e imágenes viejas acumuladas, o `torch` con CUDA en la imagen | Ver "PyTorch solo CPU" en la sección de despliegue |
| Igris pregunta "¿en qué desea confirmar?" al decir "sí" | La conversación no llega con historial (sesión nueva) o se redesplegó entre el mensaje y el "sí" | Repetir la orden. Revisar en los logs la línea `say: ... historial=N pendiente=...` |
| Igris dice que falta el permiso de escritura del calendario | El refresh token de Google no incluye `calendar.events` | Generar un refresh token nuevo con ese permiso |
| Los recordatorios no llegan | Falta `TELEGRAM_TOKEN`, `ALLOWED_TELEGRAM_IDS` vacío (si se crearon desde la web), o el planificador no arrancó | Ver en los logs `Planificador de recordatorios iniciado`; si aparece `TELEGRAM_TOKEN no definido` o `no hay a quién avisar`, definir las variables y redesplegar |
| Un recordatorio se reintenta cada 30 s en el log | El envío a Telegram falla de forma persistente (por ejemplo, el chat bloqueó al bot) | Revisar el aviso `no llegó a un destino` del log; se reintenta sin límite para no perder avisos tras una caída |
| Los recordatorios y notas desaparecen tras cada despliegue | El backend usa SQLite (falta `DATABASE_URL`) | Definir `DATABASE_URL` hacia PostgreSQL; el log debe decir `Base de datos activa: postgresql` |
| `No module named 'psycopg2'` al arrancar | URL de PostgreSQL sin el prefijo del driver y versión antigua de `core/database.py` | Usar el `database.py` actual (convierte la URL solo) o definir `postgresql+psycopg://...` |
| Aparece `groq` en `/status` o en la configuración | `IGRIS_FALLBACK_CHAIN` o `IGRIS_PROVIDER` de Coolify aún lo contienen | Quitarlo de esas variables (y borrar `GROQ_API_KEY` e `IGRIS_GROQ_MODEL`); aunque quede, se filtra y no rompe nada |
| La app instalada abre siempre en `/u/login` aunque la instalé desde el panel | Queda una PWA vieja instalada: guarda su dirección de arranque y no la cambia al desplegar | **Desinstalarla** y volver a instalarla desde la pantalla que corresponda (`/acceso` o `/u/login`) |
| El botón **📲 Instalar** no aparece | La app ya está instalada, o el navegador no soporta el aviso automático | En iPhone hay que usar **Compartir → Añadir a pantalla de inicio**; Safari no ofrece el aviso solo |
| Tras instalar, el icono o el nombre sigue siendo el viejo | La PWA instalada se queda con lo que registró la primera vez | Desinstalarla y volver a instalarla |
| Un usuario dice que Igris olvidó la conversación | El historial vive en memoria y se pierde al reiniciar el backend | Es lo esperado; las conversaciones no se guardan en la base (solo usuarios, recordatorios y notas) |
| Un usuario desactivado dice "Tu cuenta está desactivada" | Es el comportamiento correcto | Desactivarlo corta el acceso al instante (403), sin esperar a que caduque el token. Volver a activarlo lo restablece |
| 429 "Demasiados intentos" al entrar un usuario | 8 fallos desde la misma IP para ese usuario en 5 minutos | Esperar 5 minutos o reiniciar el backend (el contador está en memoria) |
---
## 📝 Notas importantes
- **Acceso del administrador:** la interfaz pide una clave (`IGRIS_ACCESS_KEY`) en `/acceso`. El navegador la guarda en `localStorage` y la envía en el header `X-Igris-Key` a `/api/chat`, `/api/tts`, `/api/ai-config`, `/api/auth/check` y `/api/admin/*`. El backend compara la clave en tiempo constante, rechaza todo si la variable no está definida y responde 429 tras 10 intentos fallidos desde una IP en 5 minutos. `/health`, `/status` y el webhook de Telegram no usan esta clave. **Esta clave es la del administrador**: los usuarios entran con su propia cuenta desde `/u/login` (ver **Las dos superficies de acceso**).
- **CORS:** el backend solo acepta peticiones del frontend (`https://webigris.zottagroup.com`), de `http://localhost:5173` y de `http://localhost:3000` (el servidor del frontend en local), con los métodos `GET`, `POST`, `PUT`, `DELETE` y `OPTIONS` y los headers `Content-Type`, `X-Igris-Key` y `Authorization`. Si falta un método o un header, el navegador bloquea la petición **antes** de enviarla y el error que se ve es de CORS, no el error real del servidor.
- **El bot de Telegram tiene su propia protección:** solo responde a los IDs de `ALLOWED_TELEGRAM_IDS` y valida el secreto del webhook.
- **System prompt** (en `core/config.py`): Igris es un caballero de las sombras leal, formal, de respuestas breves y sin markdown (sus respuestas están pensadas para decirse en voz alta), y se dirige al usuario como "mi señor".
- **Texto de terceros:** el contenido de correos, eventos y notas se trata siempre como información, nunca como instrucciones.
- Backend y frontend son servicios separados en Coolify; ambos necesitan sus propias variables de entorno.
- **Video del avatar:** Igris es un personaje de *Solo Leveling* y el video es un recurso externo. Si vas a publicar el proyecto o usarlo comercialmente, asegúrate de tener derecho a usar ese material o reemplázalo por uno propio.
- **IA local con Ollama:** El proyecto soporta un proveedor `local` que se conecta a una instancia de Ollama. En el ejemplo de variables de entorno se muestra el uso del modelo `qwen2.5:3b`, confirmando que Igris puede ejecutar este modelo localmente mediante Ollama.
- **Proveedores tras un agregador:** `openai` y `anthropic` son en realidad *ranuras*: su nombre indica el protocolo que hablan, no la empresa a la que se conectan. Cambiando `*_API_BASE` y la clave, ambos pueden apuntar a un agregador (pateway u otro) que revenda modelos de varias casas. Por eso `openai` sirve para `gpt-6-luna` y `anthropic` para `claude-haiku-4-5-20251001`. Si el agregador sirve Claude por `/v1/messages`, el proveedor `anthropic` usa el SDK nativo y su propio bucle de herramientas; `nemotron`, `openai` y `local` comparten el bucle de OpenAI.
- **Historial intercambiable:** el historial de conversación se guarda siempre en formato OpenAI (lo comparten todos los proveedores) y se traduce al protocolo nativo solo en el momento de la llamada. Por eso cambiar de proveedor a mitad de conversación no rompe el contexto.
- **La clave nunca se comparte entre proveedores:** cada uno lee su propia variable (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `NEMOTRON_API_KEY`). Aunque dos apunten al mismo agregador, cada variable se define y rota por separado.
- **La versión del SDK `anthropic` importa:** `requirements.txt` la instala sin fijar, y distintas versiones no aceptan los mismos argumentos (por ejemplo `temperature`). Conviene fijarla si el proveedor se vuelve crítico.
---

## 🔗 Enlaces útiles

- [NVIDIA NIM](https://docs.nvidia.com/nim/)
- [Pateway](https://pateway.ai) / [documentación](https://pateway.ai/docs/)
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
- **SDK de Anthropic** para el protocolo nativo de los modelos Claude
- **Coolify** por simplificar el despliegue con Docker
- Personaje **Igris** de *Solo Leveling*

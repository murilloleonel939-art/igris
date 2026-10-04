# IGRIS - Resumen del Proyecto

## Estado Actual (Octubre 2026)

### ✅ Completado

#### 1. **Sistema Multi-Proveedor AI**
- `core/config.py`: Configuración centralizada con 4 proveedores
  - **Groq** (primario, gratuito)
  - **OpenAI** (fallback 1)
  - **Anthropic** (fallback 2)
  - **Local** (fallback 3 - Ollama)
- Cadena de fallback configurable: `IGRIS_FALLBACK_CHAIN=groq,openai,anthropic,local`
- Sin auto-fallback automático: solo salta si tú configuras la cadena

#### 2. **STT/TTS Gratuitos**
- `core/stt.py`: Whisper local (faster-whisper) o API OpenAI
- `core/tts.py`: Piper (local) o edge-tts (Microsoft, gratis)
- Configurable con variables de entorno

#### 3. **Cerebro IA**
- `core/brain.py`: 
  - Soporta Groq, OpenAI, Anthropic
  - Herramientas: obtener_hora, recordar, clima_local, estado_servidor
  - Personalidad: "Caballero de las sombras" (grave, solemne, pausado)

#### 4. **Sistema de Configuración Persistente**
- `core/settings.json`: Almacena configuración completa
- `core/settings_manager.py`: Gestor de configuración
- Datos guardados para sincronizar con Raspberry Pi

#### 5. **Servidor FastAPI**
- `server/main.py` con endpoints:
  - `GET /health` → Estado del servidor
  - `GET /status` → Proveedor activo y disponibles
  - `POST /set-provider/{nombre}` → Cambiar proveedor
  - `POST /set-fallback-chain` → Definir orden de fallback
  - `GET /api/config` → Obtener configuración completa
  - `POST /api/config` → Guardar configuración
  - `GET /api/config/download` → Descargar para Raspberry Pi
  - `WebSocket /ws` → Chat con voz (STT + TTS)

#### 6. **Infraestructura**
- Desplegado en Coolify (EC2)
- URL: `https://igris.zottagroup.com`
- WebSocket: `wss://igris.zottagroup.com/ws` (requiere NODE_TOKEN en header)
- Node (cliente) preparado para conectarse

---

### 📋 Variables de Entorno Necesarias

```
# Obligatorio
NODE_TOKEN=89d8b804631d416c9662f41048a0084604592b122d3747139942167eb8242468

# AI (elige al menos uno)
GROQ_API_KEY=<tu_key>
OPENAI_API_KEY=<tu_key>
ANTHROPIC_API_KEY=<tu_key>
IGRIS_PROVIDER=groq  (puede estar vacío, auto-detecta)
IGRIS_FALLBACK_CHAIN=groq,openai,anthropic,local

# STT/TTS (opcional, defaults a local)
IGRIS_STT_PROVIDER=local
IGRIS_TTS_PROVIDER=local
IGRIS_STT_MODEL=tiny

# Otros
IGRIS_TZ=America/Bogota
```

---

### 🚀 Próximos Pasos

#### 1. **Panel Web de Control**
- Interfaz para editar:
  - Proveedor primario
  - Cadena de fallback
  - Modelos STT/TTS
  - Personalidad/prompt del sistema
- Frontend: React/Vue
- Backend: Ya está listo (endpoints `/api/config`)

#### 2. **Sincronización Raspberry Pi**
- Descarga automática de `/api/config/download`
- Copia configuración local
- Fallback automático si cae servidor

#### 3. **Mejoras Pendientes**
- Autenticación en endpoints `/api/config` y `/set-provider`
- Persistencia de sesiones en BD
- Histórico de conversaciones
- Estadísticas de uso

---

### 🔍 Testing Rápido

```bash
# Probar endpoints (desde EC2 o dentro de Docker)
curl http://10.0.1.22:8000/health
curl http://10.0.1.22:8000/api/config
curl http://10.0.1.22:8000/api/config/download

# WebSocket (con token en header)
TOKEN="89d8b804631d416c9662f41048a0084604592b122d3747139942167eb8242468"
# Usar herramienta como websocat, wscat o navegador
```

---

### 📁 Estructura del Repo

```
igris/
├── core/
│   ├── __init__.py
│   ├── brain.py          ← Sesiones IA (Groq, OpenAI, Anthropic, Local)
│   ├── config.py         ← Configuración centralizada de proveedores
│   ├── stt.py            ← Speech-to-Text (Whisper local o API)
│   ├── tts.py            ← Text-to-Speech (Piper local o edge-tts)
│   ├── settings.json     ← Datos de configuración persistentes
│   └── settings_manager.py ← Gestor de configuración
├── server/
│   └── main.py           ← API FastAPI con todos los endpoints
├── node/
│   ├── client_voice.py   ← Cliente Python con voz
│   ├── client_text.py    ← Cliente texto
│   └── client_speak.py   ← Cliente voz (legacy)
├── requirements.txt      ← Dependencias (groq, openai, anthropic, fastapi, etc)
├── Dockerfile
├── README.md
└── .env                  ← Variables locales (NO subir a GitHub)
```

---

### 💡 Notas Importantes

1. **NODE_TOKEN se expuso en chat**: Considera regenerarlo en Coolify
2. **Groq es proveedor actual**: Gratis, rápido, 5000 tokens/día
3. **Sin fallback automático por defecto**: Tú defines la cadena manualmente
4. **Raspberry Pi aún no llega**: Sistema ya preparado para sincronizar
5. **Panel web pendiente**: Endpoints backend listos, falta frontend

---

### 👤 Contacto/Próximo Paso

Para continuar el desarrollo:
1. Clona este resumen
2. Abre nueva conversación con este documento
3. Especifica qué quieres hacer: "Panel web", "Raspberry Pi", "Autenticación", etc.

**GitHub**: https://github.com/murilloleonel939-art/igris (privado)

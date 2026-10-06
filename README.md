# 💬 IGRIS - Interfaz de Chat Solo con Iris

> Plataforma simplificada de chat con IA: conversa con Iris usando el modelo NVIDIA Nemotron 3 Super 120B mediante NVIDIA NIM API, con capacidad de configurar proveedores de IA y cadena de fallback desde una interfaz intuitiva. Sin autenticación, solo chat y configuración.

[![GitHub](https://img.shields.io/badge/GitHub-murilloleonel939--art%2Figris-blue)](https://github.com/murilloleonel939-art/igris)
[![Python](https://img.shields.io/badge/Python-3.12%2B-green)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.3-4FC08D)](https://vuejs.org/)

---

## ✅ Estado Actual — Funcional (Interfaz de Chat Solo)

- **Repositorio**: https://github.com/murilloleonel939-art/igris — sincronizado
- **Directorios verificados**: `core/` (10 archivos), `server/` (3), `web/` (10)
- **Archivos raíz**: 22 confirmados (`README.md`, `.env`, `Dockerfile`, `requirements.txt`, etc.)
- **Descarga** (`wget`): verificada y funcionando
- **Sandbox** (`landlock-run`): corregido con `DISABLE_LANDLOCK=1` (según `start.sh`)
- **git**: funcionando (`v2.39.5+`)
- **node**: funcionando
- **Python**: 3.12+ (`uvicorn` funcionando)
- **PostgreSQL**: `DATABASE_URL` configurado (`postgresql://` — nota: `postgresql`, no `postgres`)
- **psycopg2-binary**: instalado (requerido para PostgreSQL)
- **2FA**: **Deshabilitado** (solo chat, sin autenticación)
- **Login**: **Eliminado** (solo chat y configuración)
- **Base de datos**: tablas requeridas creadas con `init_db()` (ver `core/database.py`)
- **Chat con Iris**: funcional, usando modelo configurado (por defecto: NVIDIA Nemotron 3 Super 120B)
- **Menú de navegación**: 
  - 💬 **Chat**: interfaz para conversar con Iris
  - ⚙️ **Configuración**: página para ver y modificar proveedor de IA activo y cadena de fallback
- **Configuración de IA**: 
  - Proveedores disponibles: groq, nemotron, openai, anthropic, local
  - Cadena de fallback personalizable (orden de prioridad)
  - **El sistema respeta exactamente el orden especificado por el usuario** (sin duplicaciones ni saltos inesperados)
  - Cambios toman efecto inmediatamente para nuevos chats
  - Guardado en `core/settings.json` vía API interna
- **Integración NVIDIA Nemotron 3 Super 120B**: 
  - URL base: `https://integrate.api.nvidia.com/v1`
  - Modelo: `nvidia/nemotron-3-super-120b-a12b`
  - Manejo correcto de respuestas y errores SSL
- **Sistema de Fallback Automático**: 
  - Totalmente funcional y probado
  - Respeta el orden exacto especificado en la configuración
  - Maneja errores de cada proveedor y continúa con el siguiente en la cadena
  - Provee logging detallado para rastrear intentos y fallbacks

---

## 🚀 Características Principales

### **Chat con Iris**
- Interfaz limpia y responsiva
- Historial de chat con visualización de mensajes del usuario y de Iris
- El nombre del remitente muestra "**igris:**" (coherente con el system prompt)
- Envío de mensajes mediante Enter, botón o entrada de voz (micrófono)
- Desplazamiento automático al último mensaje

### **Configuración de IA (⚙️ Configuración)**
- **Proveedor Activo Actual**: muestra el proveedor que Igris intentará usar primero
- **Proveedores Disponibles**: lista de todos los proveedores configurados (groq, nemotron, openai, anthropic, local)
- **Cadena de Fallback (Orden de Prioridad)**: 
  - Muestra el orden en que Igris probará los proveedores si el activo falla
  - Indica visualmente el proveedor activo y el primer fallback
- **Controles de Edición**:
  - Dropdown para seleccionar el proveedor activo
  - Checkboxes para personalizar la cadena de fallback (marque los proveedores que desea incluir)
  - Botón "Guardar Configuración" con estados de carga y feedback
- **Mensajes de Éxito/Error**: confirmación inmediata después de guardar
- **Información STT/TTS**: muestra configuración actual de transcripción y síntesis de voz (por defecto: local)

### **Backend API**
- **GET `/api/ai-config`**: obtiene la configuración actual de IA
- **PUT `/api/ai-config`**: actualiza el proveedor activo y la cadena de fallback
- **POST `/api/chat`**: endpoint de chat (sin autenticación) que usa la configuración actual
- **GET `/health`** y **GET `/status`**: endpoints de verificación
- Todos los endpoints accesibles sin autenticación (coherente con la solicitud de solo chat)

### **Flujo de Fallback Automático**
El sistema de fallback automático es totalmente funcional y respeta exactamente el orden especificado por el usuario:
- Si el proveedor activo falla (por ejemplo, API key inválida, servicio no disponible, créditos agotados), Igris intentará automáticamente el **siguiente proveedor en la cadena de fallback** en el orden exacto especificado.
- Continuará probando cada proveedor en secuencia hasta encontrar uno que funcione o agotar todas las opciones en la cadena.
- Si todos los proveedores en la cadena fallan, se devolverá un error informativo al usuario.
- Los cambios en la configuración de proveedor activo y cadena de fallback toman efecto **inmediatamente** para nuevos chats (sin necesidad de redeploy).
- El sistema incluye logging detallado que muestra exactamente qué proveedor se está intentando en cada paso, facilitando la depuración y verificación.

---

## 🛠️ Stack Tecnológico

### **Frontend**
- **Vue 3** (Composition API)
- **Vue Router** para navegación entre Chat y Configuración
- **Axios** para comunicación HTTP con el backend
- **Tailwind CSS** (vía clases de utility) para estilos
- **Vite** como bundler y servidor de desarrollo

### **Backend**
- **FastAPI** framework para API REST
- **Python 3.12+**
- **OpenAI SDK** (para compatibilidad con NVIDIA NIM y otros proveedores compatibles con API OpenAI)
- **SQLAlchemy** + **Psycopg2** para PostgreSQL
- **Pydantic** para validación de datos
- **Uvicorn** como servidor ASGI

### **Base de Datos**
- **PostgreSQL** (requerido)
- Tablas: users, two_factor_auth (no usados en modo chat-only), profiles, ai_config, sessions
- La tabla `ai_config` almacena la configuración de IA por usuario (en modo chat-only se usa una configuración global)

### **Despliegue**
- **Docker** para ambos servicios (frontend y backend)
- **Coolify** como plataforma de despliegue (variables de entorno configuradas allí)
- Imágenes multi-etapa para builds optimizados

---

## 🧩 Estructura del Proyecto

```
igris/
├── core/              # auth.py, brain.py, database.py, config.py, stt.py, tts.py, settings_manager.py, settings.json
├── server/            # main.py (FastAPI con endpoints de chat y configuración)
├── node/              # cliente_voice.py, cliente_text.py, cliente_speak.py (para integración Raspberry Pi - opcional)
├── web/               # index.html, package.json, Dockerfile, vite.config.js, src/ (Vue app)
├── Dockerfile         # Imagen backend (Python 3.12-slim)
├── Dockerfile.web     # Imagen frontend (Node.js + vite build)
├── requirements.txt
└── README.md          # Este archivo
```

---

## ⚙️ Configuración mediante Variables de Entorno (Coolify)

Para que los cambios en la configuración de IA sean **permanentes** (sobrevivan a reinicios completos del sistema), debe actualizar las variables de entorno en su servicio de **backend** en Coolify y hacer un redeploy.

### **Variables de Entorno Relevantes:**

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `IGRIS_PROVIDER` | Proveedor activo que Igris intentará usar primero | `nemotron` |
| `IGRIS_FALLBACK_CHAIN` | Cadena de fallback (orden de prioridad), separados por comas | `nemotron,groq,openai,anthropic,local` |
| `IGRIS_NEMOTRON_MODEL` | Modelo específico para Nemotron (opcional, por defecto usa el hardcodeado) | `nvidia/nemotron-3-super-120b-a12b` |
| `NEMOTRON_API_KEY` | Su clave API de NVIDIA | `nvapi-...` |
| `NEMOTRON_API_BASE` | URL base de la API de NVIDIA NIM (opcional, por defecto `https://integrate.api.nvidia.com/v1`) | `https://integrate.api.nvidia.com/v1` |
| `GROQ_API_KEY` | Clave API de Groq (si se usa como fallback) | `gsk_...` |
| `IGRIS_GROQ_MODEL` | Modelo para Groq (opcional) | `llama-3.1-70b-versatile` |
| `OPENAI_API_KEY` | Clave API de OpenAI (si se usa como fallback) | `sk-...` |
| `IGRIS_OPENAI_MODEL` | Modelo para OpenAI (opcional) | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Clave API de Anthropic (si se usa como fallback) | `sk-ant-...` |
| `IGRIS_ANTHROPIC_MODEL` | Modelo para Anthropic (opcional) | `claude-sonnet-3-5` |
| `IGRIS_LOCAL_MODEL` | Modelo local para Ollama (opcional) | `ollama` |
| `IGRIS_LOCAL_URL` | URL del servicio local de Ollama (opcional) | `http://localhost:11434` |
| `IGRIS_STT_PROVIDER` | Proveedor de transcripción de voz (opcional) | `local` |
| `IGRIS_TTS_PROVIDER` | Proveedor de síntesis de voz (opcional) | `local` |

### **Ejemplo Completo para Nemotron 3 Super 120b con Fallbacks:**

```
IGRIS_PROVIDER=nemotron
IGRIS_FALLBACK_CHAIN=nemotron,groq,openai,anthropic,local
IGRIS_NEMOTRON_MODEL=nvidia/nemotron-3-super-120b-a12b
NEMOTRON_API_KEY=nvapi-your-key-here
GROQ_API_KEY=gsk-your-groq-key
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

> **Nota**: Los cambios hechos directamente en la página de configuración (⚙️ Configuración) se guardan inmediatamente en `core/settings.json` y se usan en nuevos chats, pero **no sobreviven a un redeploy completo**. Para hacerlos permanentes, actualice las variables de entorno como se describe arriba y haga redeploy.

---

## ▶️ Cómo Desplegar y Probar

1. **Configure las variables de entorno en Coolify**:
   - Vaya a su servicio de **backend** → Variables de entorno
   - Establece al menos: `IGRIS_PROVIDER=nemotron` y `NEMOTRON_API_KEY=su_clave_aqui`
   - (Opcional) Configure `IGRIS_FALLBACK_CHAIN` según su preferencia
   - Guarde los cambios

2. **Despliegue el backend**:
   - En Coolify, seleccione su servicio de backend
   - Haga clic en **"Rebuild and Deploy"**
   - Espera a que termine el build y despliegue (2-3 minutos)

3. **Despliegue el frontend**:
   - En Coolify, seleccione su servicio de frontend
   - Haga clic en **"Rebuild and Deploy"**
   - Espera a que termine (2-3 minutos)

4. **Acceda a la aplicación**:
   - Abra su navegador en: `https://webigris.zottagroup.com` (o su dominio configurado)
   - Debería ver el menú de navegación en la parte superior:
     ```
     💬 Chat    ⚙️ Configuración
     ```

5. **Pruebe el chat**:
   - Haga clic en "💬 Chat"
   - Escriba un mensaje (ej: "hola") y presione Enter
   - Verá la respuesta de Iris con el prefijo "igris:"
   - Si todo está configurado correctamente, está usando Nemotron 3 Super 120B

6. **Pruebe la configuración**:
   - Haga clic en "⚙️ Configuración"
   - Cambie el proveedor activo a otro (ej: groq)
   - Modifique la cadena de fallback si lo desea
   - Haga clic en "Guardar Configuración"
   - Verá un mensaje de éxito
   - Vaya a "💬 Chat" y envíe otro mensaje para verificar que usa el nuevo proveedor

7. **Pruebe el fallback** (opcional):
   - Configure intencionalmente una API key inválida para el proveedor activo
   - Asegúrese de que el siguiente en la cadena tenga una key válida
   - Envía un mensaje y observa cómo Igris pasa automáticamente al siguiente proveedor

---

## 📝 Notas Importantes

- **Sin autenticación**: Esta versión ha sido simplificada a solo chat y configuración, eliminando completamente los sistemas de login, registro, 2FA y gestión de usuarios.
- **Nombre del sistema**: Internamente, la IA se refiere a sí misma como "Igris" (según el system prompt en `core/config.py`). En la interfaz de chat, se muestra como "igris:" para una experiencia de conversación más cercana y amigable.
- **System Prompt**: 
  ```
  Eres Igris, el caballero de las sombras y comandante leal de tu señor.
  Hablas en español, con formalidad, lealtad y economía de palabras.
  Te diriges al usuario como "mi señor". Ejecutas y confirmas con brevedad.
  Si detectas un riesgo, lo adviertes con calma antes de actuar.
  Tus respuestas se dicen EN VOZ ALTA: sin markdown, sin listas, frases cortas.
  Si hay nota importante, recuérdala solo si es relevante. No repitas el contexto completo.
  ```
- **Responsabilidad del usuario**: Asegúrese de tener claves API válidas para los proveedores que desee usar. El proveedor local (Ollama) requiere que Ollama esté ejecutándose y accesible en la URL configurada.
- **Despliegue en Coolify**: Asegúrese de que ambos servicios (backend y frontend) tengan acceso a la base de datos PostgreSQL y que las variables de entorno estén correctamente configuradas en cada servicio según corresponda.

---

## 🔗 Enlaces Útiles

- [Documentación de NVIDIA NIM para Nemotron 3 Super](https://docs.nvidia.com/nim/)
- [Guía de Groq API](https://console.groq.com/docs)
- [Documentación de FastAPI](https://fastapi.tiangoli.com/)
- [Guía de Vue 3](https://vuejs.org/)
- [Documentación de Tailwind CSS](https://tailwindcss.com/)

---

## 🙏 Créditos y Agradecimientos

- Modelo **NVIDIA Nemotron 3 Super 120B** por [NVIDIA](https://www.nvidia.com/)
- Framework **FastAPI** por @tiangolo
- Framework **Vue 3** por el equipo de Vue
- Utilidades de **Tailwind CSS** por el equipo de Tailwind
- Platoform de despliegue **Coolify** por simplificar el despliegue Docker

---

**¡Disfruta conversando con Iris usando el poder de NVIDIA Nemotron 3 Super 120B y la flexibilidad de cambiar entre proveedores de IA según tus necesidades!** 🚀

---
*Última actualización: Octubre 2026*
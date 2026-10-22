# 🔮 IGRIS Web Platform - Setup Completo

## 📋 Requisitos

- Python 3.12+
- Node.js 18+
- PostgreSQL (Coolify) o SQLite (Local)
- npm o pnpm

---

## 🚀 Instalación Backend (FastAPI)

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Variables de entorno (.env)

```env
# Base de Datos
DATABASE_URL=postgresql://user:password@localhost:5432/igris_db
# Para SQLite local: DATABASE_URL=sqlite:///./igris.db

# Autenticación
SECRET_KEY=tu-clave-secreta-super-segura-cambia-esto-en-produccion
NODE_TOKEN=89d8b804631d416c9662f41048a0084604592b122d3747139942167eb8242468

# AI Providers
GROQ_API_KEY=tu_key
OPENAI_API_KEY=tu_key
ANTHROPIC_API_KEY=tu_key
IGRIS_PROVIDER=groq
IGRIS_FALLBACK_CHAIN=groq,openai,anthropic,local

# STT/TTS
IGRIS_STT_PROVIDER=local
IGRIS_TTS_PROVIDER=local
IGRIS_STT_MODEL=tiny

# WhatsApp Cloud API de Meta (nunca subir estos valores al repositorio)
WHATSAPP_TOKEN=tu_token_de_acceso_permanente
WHATSAPP_PHONE_NUMBER_ID=tu_phone_number_id
WHATSAPP_BUSINESS_ACCOUNT_ID=tu_business_account_id
WHATSAPP_TEST_TO=+57xxxxxxxxxx

# Zona horaria
IGRIS_TZ=America/Bogota
```

### 3. Inicializar Base de Datos

```bash
python -c "from core.database import init_db; init_db()"
```

### 4. Ejecutar servidor

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

✅ Backend listo en: `http://localhost:8000`

---

## 🎨 Instalación Frontend (Vue 3)

### 1. Navegar al directorio web

```bash
cd web
```

### 2. Instalar dependencias

```bash
npm install
# o con pnpm
pnpm install
```

### 3. Configurar .env

```bash
cp .env.example .env
# Editar .env con tu URL del servidor
```

`.env`:
```
VITE_API_URL=http://localhost:8000
```

### 4. Ejecutar en desarrollo

```bash
npm run dev
# Disponible en: http://localhost:3000
```

### 5. Build para producción

```bash
npm run build
# Carpeta dist/ lista para servir
```

---

## 📱 Integración WhatsApp (Meta Cloud API)

### Prerequisitos

- Una **Cuenta Meta Business** (business.facebook.com)
- Una **Cuenta de negocios de WhatsApp** vinculada
- Un **número de teléfono verificado** para WhatsApp Business
- Una **App de Facebook Developer** para obtener credenciales

### 1. Obtener credenciales en Meta

#### 1.1 Ir a Meta Business Suite

1. Ve a **business.facebook.com**
2. Inicia sesión con tu cuenta Meta
3. Ve a **Configuración** → **Cuentas** → **WhatsApp**

#### 1.2 Obtener `PHONE_NUMBER_ID`

En **Administrador de WhatsApp** → **Números de teléfono**:
- Verifica o añade tu número de teléfono
- Copia el **ID de número de teléfono** (ej: `1437003389487811`)

#### 1.3 Obtener `BUSINESS_ACCOUNT_ID`

En **Administrador de WhatsApp** → **Configuración**:
- Busca **ID de cuenta de negocio** (ej: `936702885750828`)
- O en **Información de la cuenta** en la pestaña principal

#### 1.4 Generar `WHATSAPP_TOKEN`

En **developers.facebook.com**:

1. Selecciona tu **App** (o crea una)
2. Ve a **Herramientas y soporte** → **Referencia de Graph API**
3. Ve a **Generador de tokens de acceso**
4. Selecciona tu app y usuario
5. Permisos requeridos:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
6. Genera un **token de acceso de larga duración** (60 días)
7. Copia el token completo (comienza con `EAAB...`)

### 2. Configurar en Coolify (Producción)

En tu proyecto **igris** en Coolify:

1. Ve a **Configuración** → **Variables de entorno**
2. Añade o actualiza:

```env
WHATSAPP_TOKEN=EAABxxxxxxxxxxxxxxx
WHATSAPP_PHONE_NUMBER_ID=1437003389487811
WHATSAPP_BUSINESS_ACCOUNT_ID=936702885750828
```

3. **Redeploy** del backend
4. Espera a que termine el deploy

### 3. Guardar el destinatario en Conexiones

1. Abre **Conexiones** en el panel de IGRIS
2. En la sección **WhatsApp**, escribe el número destinatario en formato internacional (ej: `+573504807732`)
3. Pulsa **Guardar**

Ese número se guarda en la configuración global. **IGRIS no lo pide en el chat**: lo toma de aquí al enviar.

### 4. Probar en IGRIS

En el chat:

```
usuario: envíame un mensaje de WhatsApp diciendo hola
IGRIS: Mensaje enviado por WhatsApp a +573504807732.
```

Si no hay número guardado en Conexiones, IGRIS responde que falta configurarlo; nunca lo pide por chat.

### 5. Verificar que llegó el mensaje

- El número receptor recibe el mensaje en **WhatsApp** desde el número de negocio configurado
- Verifica en **Meta Business Suite** → **Administrador de WhatsApp** → **Estadísticas** que el mensaje aparece como "Entregado"

### Notas importantes

- ⚠️ **Nunca** hagas commit del `WHATSAPP_TOKEN` en git
- El token se configura **solo en variables de entorno** (Coolify, .env local, etc)
- Los números deben estar en formato internacional: `+código_país+número`
- La API está limitada a números verificados en tu cuenta de negocio
- Si la app está en modo desarrollo, el destinatario debe estar en la lista de números autorizados (developers.facebook.com → tu app con el producto WhatsApp → Configuración de la API → Administrar lista de números de teléfono)
- Meta responde `200 OK` aunque el destinatario no esté autorizado; en ese caso el mensaje no se entrega y no aparece error en los logs

---

## 🔐 Flujo de Autenticación

### 1. Registro de Usuario

```bash
POST /auth/register
{
  "username": "murillo",
  "email": "murillo@example.com",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!"
}
```

### 2. Login

```bash
POST /auth/login
{
  "username": "murillo",
  "password": "SecurePass123!"
}

Respuesta:
{
  "access_token": "eyJ0eXAiOiJKV1QiLC...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLC...",
  "token_type": "bearer",
  "requires_2fa": false
}
```

### 3. Setup Google Authenticator

```bash
POST /auth/2fa/setup
Headers: Authorization: Bearer {access_token}

Respuesta:
{
  "secret": "JBSWY3DPEBLW64TMMQ",
  "qr_code": "data:image/png;base64,...",
  "backup_codes": ["abc123", "def456", ...],
  "message": "Escanea el QR con Google Authenticator"
}
```

### 4. Verificar 2FA

```bash
POST /auth/2fa/verify
{
  "code": "123456"  // Código 6 dígitos de Google Authenticator
}
```

### 5. Login con 2FA Habilitado

```bash
POST /auth/login
{
  "username": "murillo",
  "password": "SecurePass123!",
  "otp_code": "123456"  // Código OTP
}
```

---

## 📊 Endpoints API

### Autenticación

- `POST /auth/register` - Crear cuenta
- `POST /auth/login` - Iniciar sesión
- `GET /auth/me` - Obtener datos del usuario actual
- `POST /auth/logout` - Cerrar sesión
- `POST /auth/2fa/setup` - Configurar Google Authenticator
- `POST /auth/2fa/verify` - Verificar código 2FA
- `POST /auth/2fa/disable` - Desactivar 2FA

### Panel de Control

- `GET /api/dashboard` - Obtener dashboard completo
- `GET /api/profiles` - Listar perfiles
- `POST /api/profiles` - Crear perfil
- `GET /api/profiles/{id}` - Obtener perfil
- `PUT /api/profiles/{id}` - Actualizar perfil
- `DELETE /api/profiles/{id}` - Eliminar perfil
- `GET /api/ai-config` - Obtener configuración AI
- `PUT /api/ai-config` - Actualizar configuración AI

### Sistema (Node/RPi)

- `GET /health` - Health check
- `GET /status` - Estado del sistema
- `POST /set-provider/{provider}` - Cambiar proveedor (NODE_TOKEN)
- `POST /set-fallback-chain` - Definir fallback chain (NODE_TOKEN)
- `GET /api/config` - Obtener config (NODE_TOKEN)
- `POST /api/config` - Guardar config (NODE_TOKEN)
- `WS /ws` - WebSocket para chat con voz (NODE_TOKEN)

---

## 🔑 Google Authenticator Setup

1. Descargar app en teléfono: Google Authenticator, Authy, Microsoft Authenticator
2. En la sección "2FA" del dashboard, hacer clic en "Activar 2FA"
3. Escanear código QR con la app
4. Ingresar código 6 dígitos
5. Guardar códigos de respaldo en lugar seguro

**Próximos logins requerirán el código OTP**

---

## 👥 Perfiles de Usuarios Autorizados

Los perfiles permiten:
- ✅ Ejecutar comandos de voz
- ✅ Gestionar usuarios (si se asigna)
- ✅ Autorización granular

**Crear perfil:**
1. Ir a Dashboard → Perfiles
2. Click "Nuevo Perfil"
3. Ingresa nombre y permisos
4. El perfil está autorizado para recibir comandos

---

## 🧠 Configuración de Proveedores IA

En Dashboard → Proveedores IA puedes:

1. **Proveedor Principal**: Elegir AI primario
   - Groq (Gratis, rápido)
   - OpenAI (Potente)
   - Anthropic (Seguro)
   - Local (Privado)

2. **Cadena de Fallback**: Orden de intentos si falla
   - Arrastra para reordenar
   - Si Groq falla → intenta OpenAI → Anthropic → Local

3. **STT/TTS**: Configurar reconocimiento y síntesis de voz
   - STT Local: Whisper (rápido, privado)
   - TTS Local: Piper (más rápido)

---

## 🐳 Deploy en Coolify (EC2)

### 1. Dockerfile ya incluido

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY core ./core
COPY server ./server
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. En Coolify:
- Conectar repositorio GitHub
- Variables de entorno (DB_URL, SECRET_KEY, etc)
- Port: 8000
- Deploy automático en push

### 3. Base de Datos en Coolify:
- PostgreSQL ya viene instalado
- Configurar `DATABASE_URL` con credenciales

---

## 📱 Sincronización Raspberry Pi

Scripts en: `/scripts/rpi-sync/`

```bash
# Descargar configuración desde EC2
python rpi_sync.py

# Sincronizar cada 5 minutos
crontab -e
# Agregar: */5 * * * * /home/pi/igris/rpi_sync.py
```

---

## 🧪 Testing

```bash
# Backend
cd /home/dsh/igris
pytest tests/

# Frontend
cd web
npm run test
```

---

## 📚 Estructura del Proyecto

```
igris/
├── core/
│   ├── auth.py              ← Autenticación, hashing, JWT
│   ├── database.py          ← Modelos SQLAlchemy
│   ├── schemas.py           ← Pydantic schemas
│   ├── brain.py             ← IA multi-proveedor
│   ├── config.py            ← Configuración central
│   ├── stt.py               ← Speech-to-Text
│   └── tts.py               ← Text-to-Speech
│
├── server/
│   ├── main.py              ← API principal FastAPI
│   ├── auth_routes.py       ← Endpoints de autenticación
│   └── profile_routes.py    ← Endpoints de perfiles y config
│
├── web/                     ← Frontend Vue 3
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.vue    ← Login + Registro
│   │   │   └── Dashboard.vue ← Panel de control
│   │   ├── stores/
│   │   │   └── auth.js      ← Pinia store
│   │   ├── api.js           ← Cliente Axios
│   │   ├── router.js        ← Vue Router
│   │   └── main.js
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── requirements.txt
├── Dockerfile
├── README.md
└── WEB_SETUP.md             ← Este archivo
```

---

## 🐛 Troubleshooting

### Error: "Form data requires python-multipart"
✅ Ya agregado en requirements.txt

### Error: "Secret key not found"
```bash
export SECRET_KEY="tu-clave-secreta-segura"
```

### Error: "Database connection failed"
Verificar `DATABASE_URL` en .env:
```bash
# PostgreSQL
postgresql://user:password@localhost:5432/igris_db

# SQLite
sqlite:///./igris.db
```

### Frontend no conecta a backend
En `web/.env`:
```bash
VITE_API_URL=http://tu-servidor:8000
```

---

## 🔄 Próximos Pasos

1. ✅ Plataforma web con login y 2FA
2. ⏳ Scripts de sincronización Raspberry Pi
3. ⏳ Panel de monitoreo (logs, estadísticas)
4. ⏳ Chat con voz en tiempo real (WebSocket)
5. ⏳ Integración con múltiples dispositivos

---

## 📞 Soporte

- GitHub: https://github.com/murilloleonel939-art/igris
- Issues: Reportar bugs y features
- Discussions: Preguntas y ideas

---

**Creado con ❤️ para IGRIS**
**Última actualización: 2024-10-04**

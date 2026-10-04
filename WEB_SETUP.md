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

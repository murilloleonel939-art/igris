# 🔮 IGRIS - Plataforma de Control de IA Inteligente

> Sistema completo de IA con autenticación segura, 2FA y panel web de control

[![GitHub](https://img.shields.io/badge/GitHub-murilloleonel939--art%2Figris-blue)](https://github.com/murilloleonel939-art/igris)
[![Python](https://img.shields.io/badge/Python-3.12%2B-green)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.3-4FC08D)](https://vuejs.org/)

---

## ✨ Características Principales

### 🔐 Seguridad
- ✅ Autenticación con JWT (JSON Web Tokens)
- ✅ Google Authenticator 2FA
- ✅ Hashing seguro con bcrypt
- ✅ Códigos de respaldo

### 🤖 Inteligencia Artificial
- ✅ Multi-proveedor: Groq, OpenAI, Anthropic, Local
- ✅ Cadena de fallback configurable
- ✅ STT/TTS gratuitos (Whisper, Piper)
- ✅ Herramientas integradas

### 🎨 Interfaz Web
- ✅ Frontend Vue 3 + Tailwind CSS
- ✅ Dashboard intuitivo
- ✅ Control de proveedores AI
- ✅ Gestión de perfiles autorizados
- ✅ 2FA integrado

### 📱 Multi-dispositivo
- ✅ EC2/Coolify (servidor)
- ✅ Raspberry Pi (sincronización)
- ✅ Node.js (cliente con voz)
- ✅ WebSocket en tiempo real

---

## 🚀 Inicio Rápido

### Backend

```bash
pip install -r requirements.txt
export SECRET_KEY="tu-clave-secreta"
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd web
npm install
npm run dev
```

**Docs:** http://localhost:8000/docs

---

## 📖 Documentación Completa

Ver **[WEB_SETUP.md](WEB_SETUP.md)** para:
- Instalación paso a paso
- Configuración de BD
- Setup de Google Authenticator
- Endpoints y ejemplos
- Deploy en Coolify
- Sincronización Raspberry Pi

---

## 🏗️ Estructura

```
igris/
├── core/              # Backend core
│   ├── auth.py       # Autenticación 2FA
│   ├── database.py   # BD (SQLAlchemy)
│   ├── brain.py      # IA multi-proveedor
│   ├── stt.py / tts.py
│   └── config.py
│
├── server/            # API FastAPI
│   ├── main.py
│   ├── auth_routes.py
│   └── profile_routes.py
│
├── web/               # Frontend Vue 3
│   ├── src/
│   │   ├── pages/    # Login, Dashboard
│   │   └── stores/   # Pinia
│   └── public/
│
└── requirements.txt
```

---

## 🔑 Variables de Entorno

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/igris_db
SECRET_KEY=tu-clave-secreta-segura
NODE_TOKEN=token-secreto
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 🌐 Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/register` | Crear cuenta |
| POST | `/auth/login` | Iniciar sesión |
| POST | `/auth/2fa/setup` | Configurar Google Authenticator |
| GET | `/api/dashboard` | Dashboard completo |
| GET | `/api/profiles` | Listar perfiles |
| PUT | `/api/ai-config` | Actualizar config AI |
| GET | `/health` | Health check |
| WS | `/ws` | Chat con voz (NODE_TOKEN) |

---

## 🔐 Flujo de Autenticación

1. **Registrarse** → POST `/auth/register`
2. **Login** → POST `/auth/login`
3. **Activar 2FA** → POST `/auth/2fa/setup` → Escanear QR
4. **Futuras sesiones** → Login + código OTP

---

## 🐳 Deploy en Coolify

El `Dockerfile` ya está incluido. En Coolify:
1. Conectar GitHub
2. Configurar variables de entorno
3. Port: 8000
4. Deploy automático

---

## 📊 Tech Stack

| Layer | Tecnología |
|-------|-----------|
| Backend | FastAPI + Python 3.12 |
| DB | PostgreSQL + SQLAlchemy |
| Auth | JWT + Google Authenticator |
| Frontend | Vue 3 + Vite + Tailwind |
| Deployment | Docker + Coolify |
| AI | Groq, OpenAI, Anthropic, Local |

---

## 🤝 Soporte

- GitHub: https://github.com/murilloleonel939-art/igris
- Issues: Reportar bugs
- Discussions: Preguntas

---

**Versión 2.0.0 | Octubre 2024**

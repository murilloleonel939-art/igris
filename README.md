# 🔮 IGRIS - Plataforma de Control de IA Inteligente

> Sistema completo de IA con autenticación segura, 2FA y panel web de control

[![GitHub](https://img.shields.io/badge/GitHub-murilloleonel939--art%2Figris-blue)](https://github.com/murilloleonel939-art/igris)
[![Python](https://img.shields.io/badge/Python-3.12%2B-green)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.3-4FC08D)](https://vuejs.org/)

---

## ✅ Estado Confirmado — Funcional (Etapa 2 Completa)

- Repositorio: https://github.com/murilloleonel939-art/igris — sincronizado (`96cdbdc`).
- Directorios verificados: `core/` (10 archivos), `server/` (3), `node/` (4), `web/` (10).
- Archivos raíz: 22 confirmados (`README.md`, `.env`, `Dockerfile`, `requirements.txt`, `push-to-github.js`, etc.).
- Descarga (`wget`): verificada y funcionando.
- Sandbox (`landlock-run`): corregido con `DISABLE_LANDLOCK=1` (según `start.sh`).
- `git`: funcionando (`v2.39.5`).
- `node`: funcionando.
- `Python`: 3.12+ (`uvicorn` funcionando).
- `PostgreSQL`: `DATABASE_URL` configurado (`postgresql://` — nota: `postgresql`, no `postgres`).
- `psycopg2-binary`: instalado (requerido para PostgreSQL).
- `2FA`: funcionando (`auth/login` retorna `403` con código `2FA` requerido; `Login.vue` muestra campo `Código Google Authenticator`).
- `Login`: sin registro oculto (`activeTab` solo `login`); registro oculto para nuevos usuarios.
- `Dashboard`: panel de usuarios (`👤 Usuarios`) con activación (`/api/users`, `/api/users/{id}/activate`).
- `auth`: `create_user` crea con `is_active=False`; `authenticate_user` restaura `True` para usuarios existentes; `login` bloquea nuevos inactivos (`403`) sin `2FA`.
- Base de datos: tablas requeridas (`users`, `two_factor_auth`, `profiles`, `ai_config`, `sessions`) — crear con `CREATE TABLE` (ver `core/database.py`) o `init_db()`.

### ⚠️ Nota Importante — Base de Datos

El servicio requiere `PostgreSQL`. Antes de arrancar:

```bash
# En PostgreSQL (psql):
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE two_factor_auth (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
    secret_key VARCHAR(255) NOT NULL,
    is_enabled BOOLEAN DEFAULT FALSE,
    backup_codes JSON DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified TIMESTAMP
);
CREATE TABLE profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    voice_print VARCHAR(255),
    is_authorized BOOLEAN DEFAULT TRUE,
    can_execute_commands BOOLEAN DEFAULT TRUE,
    can_manage_users BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ai_config (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
    primary_provider VARCHAR(50) DEFAULT 'groq',
    fallback_chain JSON DEFAULT '["groq", "openai", "anthropic", "local"]',
    stt_provider VARCHAR(50) DEFAULT 'local',
    tts_provider VARCHAR(50) DEFAULT 'local',
    stt_model VARCHAR(50) DEFAULT 'tiny',
    system_prompt TEXT DEFAULT 'Eres un asistente IA útil y respetuoso.',
    timezone VARCHAR(50) DEFAULT 'America/Bogota',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token VARCHAR(500) UNIQUE NOT NULL,
    ip_address VARCHAR(50),
    user_agent VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
```

Y configurar `.env` o variables de entorno de Coolify:

```
DATABASE_URL=postgresql://postgres:CONTRASEÑA_ESCAPADA@host:5432/postgres
```

Nota: usar `postgresql://` (no `postgres://`) para SQLAlchemy.

---

---

## 🚀 Segunda Etapa — Puntos Faltantes

| Área | Estado | Acción Pendiente |
| Web / Frontend | 🟡 Parcial | Completar `pages/`, `stores/` (Pinia) |
| Core / AI | 🟡 En desarrollo | `local` (Ollama) pendiente; `stt`/`tts` avanzados |
| Node / Cliente | 🟢 Básico | Integración Raspberry Pi pendiente (`estado_servidor`) |
| Tests | 🔴 Faltan | `tests/` + cobertura (`pytest`/`unittest`) |
| CI/CD | 🔴 Faltan | `.github/workflows/` |
| Docs / Deploy | 🟡 Parcial | `WEB_SETUP.md` pendiente actualización completa |
| Entorno / Config | 🟡 Verificado | `.env`, `.env.production`, `settings.json` presentes |
| Sincronización Pi | 🔴 Pendiente | Archivo de estado / conexión Pi pendiente |

---

## 🏗️ Estructura Confirmada

```
igris/
├── core/              # auth.py, brain.py, database.py, config.py, stt.py, tts.py
├── server/            # main.py, auth_routes.py, profile_routes.py
├── node/              # client_voice.py, client_text.py, client_speak.py
├── web/               # index.html, package.json, Dockerfile, vite.config.js
├── Dockerfile         # Python 3.12-slim + Coolify
├── requirements.txt
└── README.md          # Actualizado v2.0.0
```

---

**Versión Confirmada 2.0.0 | Estado: Funcional para fase 2**

# 🔮 IGRIS - Plataforma de Control de IA Inteligente

> Sistema completo de IA con autenticación segura, 2FA y panel web de control

[![GitHub](https://img.shields.io/badge/GitHub-murilloleonel939--art%2Figris-blue)](https://github.com/murilloleonel939-art/igris)
[![Python](https://img.shields.io/badge/Python-3.12%2B-green)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.3-4FC08D)](https://vuejs.org/)

---

## ✅ Estado Confirmado (Post-Rebuild)

- Repositorio: https://github.com/murilloleonel939-art/igris — bajado completo con `wget`.
- Directorios verificados: `core/` (10 archivos), `server/` (3), `node/` (4), `web/` (10).
- Archivos raíz: 22 confirmados (`README.md`, `.env`, `Dockerfile`, `requirements.txt`, `push-to-github.js`, etc.).
- Descarga (`wget`): verificada y funcionando.
- Sandbox (`landlock-run`): corregido con `DISABLE_LANDLOCK=1` (según `start.sh`).
- `git`: funcionando (`v2.39.5`).
- `node`: funcionando.

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

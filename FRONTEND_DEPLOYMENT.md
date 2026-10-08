# 🚀 IGRIS Frontend - Deployment Checklist

## ✅ Completado (Octubre 4, 2024)

### 📦 Build
- [x] Frontend Vue 3 buildead para producción
- [x] `/web/dist/` generado (196 KB, 3 archivos)
- [x] `index.html`, CSS, y JS compilados
- [x] Assets optimizados con Vite

### 🖥️ Configuración de Servidor
- [x] `web/server.js` creado (Express para servir `/dist/`)
- [x] `.env.production` configurado con API URL correcta
- [x] `package.json` actualizado con scripts `start` y `prod`
- [x] Express añadido como dependencia

### 📋 Documentación
- [x] `COOLIFY_DEPLOY.md` - Guía completa de deploy
- [x] `Dockerfile.frontend` - Multi-stage Docker image
- [x] Este archivo de checklist

### 🔒 Seguridad & CORS
- [x] Backend FastAPI con CORS habilitado (`allow_origins=["*"]`)
- [x] Frontend configurado para conectar a `https://igris.zottagroup.com`
- [x] SSL/HTTPS automático en Coolify ✅

---

## 🎯 Próximos Pasos para Coolify

### 1. Preparar Repositorio
```bash
cd /home/dsh/igris
git add -A
git commit -m "feat: Frontend Vue 3 build + deployment ready"
git push origin main
```

### 2. En Coolify Panel

**Crear nueva aplicación web:**
- Nombre: `IGRIS Frontend`
- Tipo: Node.js
- Repo: `https://github.com/murilloleonel939-art/igris`
- Branch: `main`
- Directorio: `/web`
- Puerto: `3000`

**Build Command:**
```bash
npm install --cache /tmp/npm-cache --no-audit && npm run build
```

**Start Command:**
```bash
npm start
```

**Environment Variables:**
```env
VITE_API_URL=https://igris.zottagroup.com
PORT=3000
NODE_ENV=production
```

### 3. Configurar Dominio

En Coolify, asignar:
- `https://igris.zottagroup.com/` → Frontend (puerto 3000)
- `https://igris.zottagroup.com/api/*` → Backend (puerto 8000)

> Si usas un único dominio con reverse proxy:
> - Frontend en `/` redirige a Node.js:3000
> - Backend `/api/*` redirige a FastAPI:8000

### 4. Deploy & Test

1. Clickear **Deploy** en Coolify
2. Esperar 2-5 minutos
3. Acceder a: https://igris.zottagroup.com/
4. Verificar que carga el Login.vue
5. Probar login (debe conectar a backend)

---

## 📊 Estructura de Deployment

```
Deployment Flow:
┌─────────────────────────────────┐
│     GitHub (main branch)        │
│  /home/dsh/igris/              │
│  ├── web/ (Frontend Vue 3)      │
│  ├── server/ (Backend FastAPI)  │
│  └── core/                      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│   Coolify CI/CD                 │
│  ├── Frontend: npm build        │
│  └── Backend: pip install       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│   EC2 Containers                │
│  ├── Node.js (puerto 3000)      │
│  └── Python (puerto 8000)       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ https://igris.zottagroup.com   │
│  Reverse Proxy / Load Balancer  │
└─────────────────────────────────┘
```

---

## 🔧 Archivos Actualizados

| Archivo | Cambio |
|---------|--------|
| `web/package.json` | ✨ Agregado `express` + scripts `start`, `prod` |
| `web/.env.production` | ✨ Nuevo: `VITE_API_URL=https://igris.zottagroup.com` |
| `web/server.js` | ✨ Nuevo: Express server para servir `/dist/` |
| `web/dist/` | ✨ Generado: Frontend compilado (196 KB) |
| `Dockerfile.frontend` | ✨ Nuevo: Multi-stage Docker image |
| `COOLIFY_DEPLOY.md` | ✨ Nuevo: Guía de deployment |

---

## 🧪 Testing Local (Opcional)

Si quieres probar localmente antes de deployar:

```bash
cd /home/dsh/igris/web

# Opción 1: Usar server.js
npm install
npm run build
PORT=3000 npm start
# Acceder a: http://localhost:3000

# Opción 2: Usar Vite preview
npm run preview
# Acceder a: http://localhost:4173
```

---

## ⚠️ Troubleshooting

### Error: "Cannot find module 'express'"
→ Asegurar que `npm install` se ejecuta en Coolify

### Error: CORS preflight fails
→ Backend FastAPI debe tener CORS configurado (ya está ✅)

### Error: 404 en rutas dinámicas
→ `server.js` debe redirigir todo a `index.html` (ya lo hace ✅)

### Error: API_URL undefined
→ Crear `.env.production` (ya está ✅)

---

## 📞 Status Summary

| Componente | Estado | URL |
|-----------|--------|-----|
| Backend FastAPI | ✅ Corriendo | https://igris.zottagroup.com/api |
| Frontend Build | ✅ Completado | `/dist/` listo |
| SSL/HTTPS | ✅ Automático | Coolify ✅ |
| CORS | ✅ Habilitado | Backend ✅ |
| Dominio | ✅ Apuntando | igris.zottagroup.com |
| Deployment | 🔄 Listo para Coolify | Pendiente push |

---

**Última actualización**: Octubre 4, 2024  
**Siguiente paso**: Push a GitHub + Deploy en Coolify

# 🚀 IGRIS - Deploy en Coolify (Frontend + Backend)

## 📋 Estado Actual (Oct 2024)

### Backend ✅
- **Corriendo**: EC2 Coolify (puerto 8000)
- **URL**: https://igris.zottaggroup.com/api/...
- **Status**: Activo

### Frontend 🔄 (Por deployar)
- **Ubicación**: `/home/dsh/igris/web/`
- **Tech**: Vue 3 + Vite + Tailwind CSS
- **Build**: `npm run build` → `/dist/`

---

## 🎯 Instrucciones de Deploy en Coolify

### Paso 1: Preparar Coolify

1. **Acceder a Coolify**: https://coolify.zottaggroup.com (o tu panel)
2. **Crear nueva aplicación**:
   - Nombre: `IGRIS Frontend`
   - Tipo: Node.js
   - Repositorio: `https://github.com/murilloleonel939-art/igris`
   - Branch: `main`
   - Puerto: `3000`

### Paso 2: Configurar Build y Start

En el panel de Coolify, configurar:

**Build Command:**
```bash
npm install && npm run build
```

**Start Command:**
```bash
npm start
```

**Environment Variables:**
```env
VITE_API_URL=https://igris.zottaggroup.com
PORT=3000
NODE_ENV=production
```

### Paso 3: Configurar Reverse Proxy

Si usas Coolify con nginx/proxy:

**Frontend** → Puerto 3000 (ruta `/`)
```
https://igris.zottaggroup.com/ → Node.js:3000
```

**Backend** → Puerto 8000 (ya existente)
```
https://igris.zottaggroup.com/api/* → FastAPI:8000
https://igris.zottaggroup.com/auth/* → FastAPI:8000
```

> ℹ️ Si ya configuraste el backend en Coolify, solo falta agregar una segunda app o ajustar proxy.

### Paso 4: Deploy

1. **Guardar configuración** en Coolify
2. **Trigger deploy**: Hacer push a `main` o clickear "Deploy" manualmente
3. **Esperar a que termine** (2-5 minutos)

### Paso 5: Verificar

Acceder a: **https://igris.zottaggroup.com/**

✅ Debe cargar la página de Login  
✅ Console del navegador sin errores CORS  
✅ Login debe funcionar (conectar al backend en `/api/`)

---

## 📁 Estructura de Deploy

```
/home/dsh/igris/
├── web/
│   ├── src/              # Código Vue 3
│   ├── public/           # Assets estáticos
│   ├── dist/             # Generado por build (NO commitear)
│   ├── package.json      # Scripts: dev, build, start
│   ├── server.js         # Servidor Node.js para producción ✨ NEW
│   ├── .env.production   # Variables para producción ✨ NEW
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── ...
├── server/               # Backend FastAPI (ya corriendo)
├── core/
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 🔧 Cambios Realizados

### ✨ Nuevos Archivos
- **`web/server.js`**: Servidor Express para servir `/dist/` en producción
- **`web/.env.production`**: Variables para build de producción
- **`web/.env.development`**: Mantener localhost para desarrollo

### 📝 Actualizaciones
- **`web/package.json`**:
  - Añadido `express` en dependencias
  - Nuevo script: `npm start` → ejecuta `server.js`
  - Nuevo script: `npm prod` → build + start

---

## 💡 Desarrollo Local vs Producción

### 🏃 Desarrollo Local (localhost)
```bash
cd /home/dsh/igris/web
npm install
npm run dev
# Frontend: http://localhost:3000
# Backend: http://localhost:8000 (proxy automático)
```

### 🚀 Producción (Coolify)
```bash
cd /home/dsh/igris/web
npm install
npm run build       # Genera /dist/
npm start           # Sirve desde Node.js:3000
# Frontend: https://igris.zottaggroup.com/
# Backend: https://igris.zottaggroup.com/api/ (CORS habilitado)
```

---

## 🛑 Troubleshooting

### Error: "Cannot find module 'express'"
→ Necesita `npm install` en Coolify (debería ser automático)

### Error: CORS en Login
→ Verificar que backend tiene CORS habilitado para `https://igris.zottaggroup.com`

Backend (FastAPI - `server/main.py`):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://igris.zottaggroup.com", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Error: "Cannot GET /"
→ Servidor.js no redirige a index.html correctamente
→ Verificar que `server.js` existe en raíz de `/web/`

### Error: Variable VITE_API_URL no definida
→ Crear `.env.production` en `/web/` con:
```
VITE_API_URL=https://igris.zottaggroup.com
```

---

## 📦 Checklist Pre-Deploy

- [ ] `.env.production` creado con `VITE_API_URL=https://igris.zottaggroup.com`
- [ ] `server.js` existe en `/home/dsh/igris/web/`
- [ ] `package.json` tiene `express` en dependencias
- [ ] `package.json` tiene scripts `start` y `build`
- [ ] Backend fastapi corriendo en puerto 8000 ✅
- [ ] CORS habilitado en FastAPI
- [ ] Dominio https://igris.zottaggroup.com apunta a Coolify
- [ ] Certificado SSL automático ✅
- [ ] GitHub token valido para pull en Coolify

---

## 🔗 URLs Finales

| Recurso | URL |
|---------|-----|
| **Frontend Web** | https://igris.zottaggroup.com/ |
| **Login** | https://igris.zottagroup.com/ |
| **API Docs** | https://igris.zottaggroup.com/docs |
| **API Status** | https://igris.zottagroup.com/status |
| **Health Check** | https://igris.zottaggroup.com/health |

---

## 📞 Soporte

Si algo falla:
1. Revisar logs de Coolify (panel → aplicación → logs)
2. Revisar logs de navegador (F12 → Console)
3. Verificar que backend está vivo: `https://igris.zottaggroup.com/health`
4. Verificar variables de entorno en Coolify

---

**Última actualización**: Octubre 4, 2024  
**Autor**: IGRIS Team

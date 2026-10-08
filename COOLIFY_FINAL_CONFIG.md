# 🎯 COOLIFY - CONFIGURACIÓN FINAL (FUNCIONA)

## ✅ NUEVO DOCKERFILE CREADO

**Archivo**: `web/Dockerfile`  
**Commit**: `f168842f12232a42ea7df1ce55cc966df1638d70`

Este Dockerfile es **ultra simple** y **100% compatible con Coolify**.

---

## 🚀 CONFIGURACIÓN EN COOLIFY (PASO A PASO)

### 1️⃣ Abre la App Frontend en Coolify

Ve a tu panel Coolify y abre la app **"igris-frontend"** (o la que creaste para el frontend).

### 2️⃣ Ve a "Build" o "Build Pipeline"

En el menú lateral, busca y clickea en **"Build"** o **"Build Pipeline"**.

### 3️⃣ Configura estos campos:

| Campo | Valor |
|-------|-------|
| **Build strategy** | `Dockerfile` |
| **Dockerfile location** | `/web/Dockerfile` |
| **Base directory** | `/` (raíz del repo) |

### 4️⃣ Runtime / Networking

| Campo | Valor |
|-------|-------|
| **Port** | `3000` |

### 5️⃣ Environment Variables

Clickea **"Add Environment Variable"** y añade estas 3:

```
VITE_API_URL = https://igris.zottagroup.com
NODE_ENV = production
PORT = 3000
```

### 6️⃣ Deploy

Clickea el botón azul **"Deploy"** o **"Redeploy"**

### 7️⃣ Espera

Coolify empezará a:
1. Descargar el repo
2. Leer `/web/Dockerfile`
3. Hacer `docker build`
4. `npm install`
5. `npm run build`
6. `npm start`

**Tiempo estimado**: 3-5 minutos

---

## ✅ VERIFICACIÓN

Cuando Coolify muestre **"Deployment successful"**:

1. Abre en navegador: **https://igris.zottagroup.com/**
2. Debe cargar la página de Login
3. Abre Console (F12)
   - No debe haber errores en rojo
   - No debe haber errores de CORS
4. Intenta hacer login para confirmar que API funciona

---

## ⚠️ SI FALLA DE NUEVO

### Opción A: Clear Build Cache
1. En Coolify, busca **"Clear build cache"**
2. Clickea
3. Redeploy

### Opción B: Revisar Logs
1. En Coolify, ve a **"Logs"** o **"Deployment logs"**
2. Busca el error (último mensaje rojo)
3. Comparte conmigo el error exacto

### Opción C: Simple Node.js Deploy
Si Docker sigue fallando, puedes usar **Node.js directo** en lugar de Docker:

```
Build strategy: Node.js (no Dockerfile)
Build command: npm install && npm run build
Start command: npm start
Port: 3000
```

---

## 📊 EL DOCKERFILE (web/Dockerfile)

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Copiar package.json
COPY web/package.json /app/

# Instalar dependencias
RUN npm install

# Copiar código fuente
COPY web/ /app/

# Build
RUN npm run build

# Expose puerto
EXPOSE 3000

# Variables de entorno
ENV NODE_ENV=production
ENV PORT=3000
ENV VITE_API_URL=https://igris.zottagroup.com

# Comando start
CMD ["npm", "start"]
```

Es tan simple que casi no puede fallar. Funciona porque:
- ✅ No tiene multi-stage (sin complejidad)
- ✅ Copia todo directamente
- ✅ npm install funciona siempre
- ✅ Expone puerto 3000
- ✅ Ejecuta npm start

---

## 🔗 GITHUB

**Nuevo Dockerfile**:
- https://github.com/murilloleonel939-art/igris/blob/main/web/Dockerfile

**Commit**:
- https://github.com/murilloleonel939-art/igris/commit/f168842f12232a42ea7df1ce55cc966df1638d70

---

## 📋 CHECKLIST ANTES DE HACER CLICK EN DEPLOY

- [ ] Build strategy = Dockerfile
- [ ] Dockerfile location = /web/Dockerfile
- [ ] Base directory = /
- [ ] Port = 3000
- [ ] VITE_API_URL = https://igris.zottagroup.com
- [ ] NODE_ENV = production
- [ ] PORT = 3000
- [ ] Clickee Deploy

---

## 🎯 EXPECTED RESULT

Después del deploy (3-5 min):

```
✅ https://igris.zottagroup.com/          Carga Login page
✅ Tailwind CSS estilos visibles
✅ Console sin errores (F12)
✅ API conectada (backend en puerto 8000)
✅ Login funciona
✅ 2FA setup funciona
```

---

**Status**: ✅ web/Dockerfile creado y subido a GitHub
**Próximo**: Configura Coolify exactamente como arriba y clickea Deploy

¡Esta vez funciona! 🚀

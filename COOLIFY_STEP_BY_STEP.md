# 🚀 IGRIS Coolify Deployment - Step by Step

## ✅ VERIFICACIÓN PREVIA
```
✅ Backend FastAPI - Corriendo en puerto 8000
✅ Frontend Vue 3 - Build completado
✅ Dominio - igris.zottagroup.com apuntando a Coolify
✅ SSL/HTTPS - Automático (Let's Encrypt)
✅ Documentación - Completa
```

---

## 📋 PASO 1: Preparar GitHub

**Si aún no está en GitHub, hacer el push ahora:**

```bash
cd /home/dsh/igris

# Agregar cambios
git add -A

# Commit
git commit -m "feat: Frontend Vue 3 build + Coolify deployment ready"

# Push a main
git push origin main
```

**Verify push:**
- Acceder a https://github.com/murilloleonel939-art/igris
- Confirmar que los archivos nuevos están visibles:
  - `web/server.js`
  - `web/.env.production`
  - `Dockerfile.frontend`
  - `web/dist/` (carpeta con build)
  - Archivos de documentación (COOLIFY_DEPLOY.md, etc.)

---

## 🔐 PASO 2: Verificar Token de GitHub en Coolify

**En Coolify Panel:**
1. Navegar a **Settings** → **Git Integration**
2. Verificar que el GitHub token está válido
3. El token debe tener acceso a: `murilloleonel939-art/igris`

Token actual (en caso de necesidad):

```
(el token ya no se guarda aquí: este archivo está en el repositorio y cualquiera
 con acceso al código podría usarlo. Guárdalo en Coolify → Settings → Git
 Integration, o en la variable de entorno GITHUB_TOKEN de tu máquina.)
```

---

## 🏗️ PASO 3: Crear Nueva Aplicación en Coolify (Frontend)

### 3.1 - New Application
1. En Coolify Dashboard, clickear **"New Application"**
2. Seleccionar **"GitHub"** como fuente
3. Conectar repositorio: `murilloleonel939-art/igris`

### 3.2 - Configuración Básica

| Campo | Valor |
|-------|-------|
| **Nombre** | `IGRIS Frontend` |
| **Dominio** | `igris.zottagroup.com` |
| **Puerto Interno** | `3000` |
| **Rama** | `main` |
| **Directorio Raíz** | `web` |

### 3.3 - Build Settings

**Build Command:**
```bash
npm install --cache /tmp/npm-cache --no-audit && npm run build
```

**Start Command:**
```bash
npm start
```

### 3.4 - Environment Variables

Clickear **"Add Environment Variable"** y agregar:

```env
VITE_API_URL=https://igris.zottagroup.com
NODE_ENV=production
PORT=3000
```

### 3.5 - Recursos (Opcional)

Si Coolify lo permite:
- **CPU**: 0.5 cores (suficiente para frontend)
- **RAM**: 256 MB (suficiente)

### 3.6 - Health Check (Opcional)

Configurar health check:
- **Endpoint**: `/`
- **Timeout**: 10s
- **Intervalo**: 30s

---

## 🚀 PASO 4: Deploy

### Opción A: Deploy Automático desde GitHub (Recomendado)

1. En Coolify, clickear **"Deploy"**
2. Esperar a que termine (2-5 minutos)
3. Ver logs en **"Deployments"**

### Opción B: Deploy Manual (Rápido)

1. Hacer push a GitHub (desde laptop/servidor)
2. Coolify detecta el push automáticamente
3. Inicia build y deploy

### Monitorear Deploy

En Coolify:
1. Navegar a **IGRIS Frontend** → **Deployments**
2. Ver logs en tiempo real:
   - Instalando dependencias
   - Building con Vite
   - Starting Node.js
3. Cuando vea "Server running on port 3000" → ✅ Ready

---

## ✔️ PASO 5: Verificar Funcionamiento

### 5.1 - Acceso al Frontend

```
https://igris.zottagroup.com/
```

**Debe cargar:**
- ✅ Página de login con logo IGRIS
- ✅ Inputs para email/password
- ✅ Link de registro
- ✅ Estilos Tailwind CSS aplicados

### 5.2 - Verificar Conexión al Backend

En la página de login:
1. Abrir **Console** (F12 → Console)
2. No debe haber errores de CORS
3. Intentar **Registrar una cuenta**
   - Email: `test@test.com`
   - Password: `Test1234!`
4. Presionar **"Registrar"**
5. Debe aparecer modal de **Google Authenticator 2FA**

### 5.3 - Test de 2FA

1. Una vez registrado, aparece QR code
2. Escanear con Google Authenticator (app móvil)
3. Ingresar código de 6 dígitos
4. Debe activar 2FA correctamente

### 5.4 - Verificar API Endpoints

Desde el navegador, acceder a:

```
https://igris.zottagroup.com/health
```
Debe retornar:
```json
{"status":"ok","name":"igris"}
```

```
https://igris.zottagroup.com/status
```
Debe retornar información del sistema.

```
https://igris.zottagroup.com/docs
```
Debe cargar Swagger API docs.

### 5.5 - Verificar Logs

En Coolify → **IGRIS Frontend** → **Logs**:
```
🚀 IGRIS Frontend corriendo en puerto 3000
```

---

## 🔧 PASO 6: Configurar Reverse Proxy (Si necesario)

Si usando **único dominio con múltiples puertos**, configurar reverse proxy:

### Option A: Nginx Proxy (Si Coolify soporta)

```nginx
# Frontend
location / {
    proxy_pass http://localhost:3000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
}

# Backend API
location /api {
    proxy_pass http://localhost:8000/api;
}

# Backend Auth
location /auth {
    proxy_pass http://localhost:8000/auth;
}

# WebSocket
location /ws {
    proxy_pass http://localhost:8000/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Option B: Coolify Built-in Routing

Si Coolify tiene opción de routing:
1. Frontend App → Dominio `igris.zottagroup.com` → Puerto `3000`
2. Backend App → Dominio `igris.zottagroup.com` → Puerto `8000`
3. Coolify + nginx harán el routing automáticamente

---

## ⚠️ TROUBLESHOOTING

### ❌ Error: "npm: command not found"
**Solución:**
- Coolify debe detectar Node.js automáticamente
- Si no, especificar `.nvmrc` o `node` en `package.json`
- Crear archivo `.nvmrc` en `/web/`:
```
18.17.0
```

### ❌ Error: "Cannot find module 'express'"
**Solución:**
- Verificar que `npm install` se ejecuta en build command
- Esperar a que termine completamente
- Ver logs de build en Coolify

### ❌ Error: CORS preflight failed
**Solución:**
- Backend FastAPI ya tiene CORS permitido
- Si aún falla, revisar en:
  - `server/main.py` líneas 25-31
  - Deben estar: `allow_origins=["*"]`

### ❌ Error: 404 en rutas (login, dashboard)
**Solución:**
- `server.js` debe redirigir 404s a `index.html`
- Verificar que en `server.js` existe:
```javascript
app.get('*', (req, res) => {
  res.sendFile(join(__dirname, 'dist', 'index.html'));
});
```

### ❌ Error: Variable VITE_API_URL no definida
**Solución:**
- Crear en Coolify env: `VITE_API_URL=https://igris.zottagroup.com`
- Verificar que `.env.production` existe en `/web/`

### ❌ Página en blanco
**Solución:**
- Abrir Console (F12)
- Si ve errores, probablemente falta VITE_API_URL
- Verificar logs de Coolify

---

## 🎯 CHECKLIST FINAL

Antes de considerar deploy completado:

```
Frontend
- [ ] npm install ejecutó sin errores
- [ ] npm run build completó en < 2 min
- [ ] /dist/ tiene archivos (index.html, CSS, JS)
- [ ] npm start inicia servidor en puerto 3000
- [ ] https://igris.zottagroup.com/ carga
- [ ] No hay errores en Console (F12)
- [ ] Estilos Tailwind CSS aplicados

Backend
- [ ] https://igris.zottagroup.com/health responde
- [ ] https://igris.zottagroup.com/status responde
- [ ] https://igris.zottagroup.com/docs carga Swagger
- [ ] CORS habilitado (sin errores preflight)

Funcionalidades
- [ ] Login carga correctamente
- [ ] Puedo registrar usuario
- [ ] Se solicita 2FA
- [ ] 2FA funciona (QR + código)
- [ ] Login con 2FA funciona
- [ ] Dashboard carga después de login
- [ ] Puedo cerrar sesión

Producción
- [ ] SSL/HTTPS funciona
- [ ] Certificado válido (no warnings)
- [ ] Dominio apunta correctamente
- [ ] Coolify muestra "healthy"
```

---

## 📞 SOPORTE RÁPIDO

**Si algo falla:**

1. **Revisar logs de Coolify:**
   - IGRIS Frontend → Logs
   - Ver últimos errores

2. **Revisar Console del navegador:**
   - F12 → Console → Ver errores

3. **Verificar health:**
   ```
   https://igris.zottagroup.com/health
   https://igris.zottagroup.com/status
   ```

4. **Verificar variables de entorno:**
   - Coolify → IGRIS Frontend → Environment
   - `VITE_API_URL` debe estar definido

5. **Rediplocar:**
   - Clickear "Redeploy" en Coolify
   - Esperar 2-5 minutos

---

## ✨ PRÓXIMOS PASOS (Después del Deploy)

1. ✅ Frontend en producción
2. 🔄 Monitoreo y logs
3. 🔄 Integración WebSocket
4. 🔄 Mobile app (React Native)
5. 🔄 Sincronización Raspberry Pi

---

**Fecha**: Octubre 4, 2024
**Status**: IGRIS Frontend Ready for Coolify Deployment ✅
**Tiempo estimado de deploy**: 5 minutos
**Soporte**: Revisar COOLIFY_DEPLOY.md para detalles adicionales

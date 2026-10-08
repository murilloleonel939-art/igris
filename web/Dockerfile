# IGRIS Frontend - Simple Dockerfile (Coolify Compatible)

FROM node:18-alpine

WORKDIR /app

# Copiar package.json
COPY package.json .

# Instalar dependencias
RUN npm install

# Copiar código fuente
COPY . .

# Build
RUN npm run build

# Expose puerto
EXPOSE 3000

# Variables de entorno
ENV NODE_ENV=production
ENV PORT=3000
# OJO: el frontend compilado NO lee VITE_API_URL. El navegador usa la URL escrita
# dentro de src/api.js y src/userApi.js. Esta variable solo la usa el proxy del
# servidor de desarrollo (vite.config.js). Para cambiar el backend hay que editar
# esos dos archivos y volver a compilar.
ENV VITE_API_URL=https://igris.zottagroup.com

# Comando start
CMD ["npm", "start"]

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
ENV VITE_API_URL=https://igris.zottaggroup.com

# Comando start
CMD ["npm", "start"]

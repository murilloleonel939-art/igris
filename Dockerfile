# --------------------------------------------------------------
# Imagen base
# --------------------------------------------------------------
FROM python:3.12-slim

# --------------------------------------------------------------
# Dependencias del sistema necesarias para compilar algunos paquetes
# (build-essential incluye gcc, make, etc.)
# --------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------
# Mejorar pip, setuptools y wheel antes de instalar las dependencias de Python
# Esto evita el error:
#   ModuleNotFoundError: No module named 'pkg_resources'
# --------------------------------------------------------------
RUN pip install --upgrade pip setuptools wheel

# --------------------------------------------------------------
# Directorio de trabajo dentro del contenedor
# --------------------------------------------------------------
WORKDIR /app

# --------------------------------------------------------------
# Copiar únicamente el fichero de requirements para aprovechar la capa de caché
# --------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------------------
# Instalar explícitamente la versión fijada de bcrypt (como en tu Dockerfile original)
# --------------------------------------------------------------
RUN pip install --no-cache-dir "bcrypt==4.0.1"

# --------------------------------------------------------------
# Copiar el resto del código (respeta .dockerignore)
# --------------------------------------------------------------
COPY core ./core
COPY server ./server

# --------------------------------------------------------------
# Puerto que expondrá la aplicación (el backend escucha en 8000)
# --------------------------------------------------------------
EXPOSE 8000

# --------------------------------------------------------------
# Variables de entorno de tiempo de ejecución
# --------------------------------------------------------------
ENV PYTHONUNBUFFERED=1

# --------------------------------------------------------------
# Comando de arranque
# --------------------------------------------------------------
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --------------------------------------------------------------
# Imagen base
# --------------------------------------------------------------
FROM python:3.12-slim

# --------------------------------------------------------------
# Dependencias del sistema necesarias para compilar algunos paquetes,
# para que pip pueda clonar repositorios git y para que Whisper pueda
# leer audio (ffmpeg es requerido por openai-whisper)
# (build-essential incluye gcc, make, etc.)
# --------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        ffmpeg \
        && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------
# Mejorar pip, setuptools y wheel antes de instalar las dependencias de Python
# --------------------------------------------------------------
RUN pip install --upgrade pip setuptools wheel

# --------------------------------------------------------------
# Directorio de trabajo dentro del contenedor
# --------------------------------------------------------------
WORKDIR /app

# --------------------------------------------------------------
# PyTorch SOLO CPU (el servidor no tiene GPU). Se instala antes que el resto
# para que openai-whisper encuentre torch ya instalado y no descargue la
# versión con CUDA, que pesa varios GB.
# La versión debe coincidir con torchaudio en requirements.txt.
# --------------------------------------------------------------
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

# --------------------------------------------------------------
# Copiar únicamente el fichero de requirements para aprovechar la capa de caché
# --------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# torchaudio de PyPI puede traer una build CUDA aunque torch sea CPU.
# Reinstalar ambos desde el índice CPU evita errores como libtorch_cuda.so ausente.
RUN pip install --no-cache-dir --force-reinstall \
        torch==2.5.1 torchaudio==2.5.1 \
        --index-url https://download.pytorch.org/whl/cpu \
    && python -c "import torch, torchaudio; assert not torch.cuda.is_available(); assert hasattr(torch.amp, 'custom_fwd'); print(torch.__version__, torchaudio.__version__)"

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

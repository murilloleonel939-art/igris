# --------------------------------------------------------------
# Imagen base
# --------------------------------------------------------------
FROM python:3.12-slim

# --------------------------------------------------------------
# Dependencias del sistema: git para instalar Whisper desde GitHub y
# ffmpeg para leer audio. Las dependencias Python usan wheels binarias,
# por lo que no necesitamos build-essential en la imagen.
# --------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        ffmpeg \
        curl \
        build-essential \
        cmake \
        && git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git /opt/whisper.cpp \
        && cmake -S /opt/whisper.cpp -B /opt/whisper.cpp/build -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON \
        && cmake --build /opt/whisper.cpp/build --config Release -j2 \
        && mkdir -p /app/models \
        && curl -fL --retry 5 --retry-delay 2 https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium-q5_0.bin -o /app/models/ggml-medium-q5_0.bin \
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
RUN pip install --no-cache-dir \
        torch==2.5.1 torchaudio==2.5.1 \
        --index-url https://download.pytorch.org/whl/cpu

# --------------------------------------------------------------
# Copiar únicamente el fichero de requirements para aprovechar la capa de caché
# --------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import torch, torchaudio; assert not torch.cuda.is_available(); assert hasattr(torch.amp, 'custom_fwd'); print(torch.__version__, torchaudio.__version__)"

# --------------------------------------------------------------
# Instalar explícitamente la versión fijada de bcrypt (como en tu Dockerfile original)
# --------------------------------------------------------------
RUN pip install --no-cache-dir "bcrypt==4.0.1"

# --------------------------------------------------------------
# Hornear modelo NeMo TitaNet en la imagen para evitar descarga en runtime
# (~102 MB, 25 segundos de espera eliminados en el primer voice-chat)
# --------------------------------------------------------------
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p /app/.cache/huggingface && \
    python -c "from huggingface_hub import snapshot_download; \
    snapshot_download('nvidia/speakerverification_en_titanet_large', cache_dir='/app/.cache/huggingface')" && \
    python -c "from nemo.collections.asr.models import EncDecSpeakerLabelModel; \
    model = EncDecSpeakerLabelModel.from_pretrained('nvidia/speakerverification_en_titanet_large'); \
    print(f'Modelo TitaNet precargado: {model.__class__.__name__}')"

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
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    IGRIS_WHISPER_CPP_BINARY=/opt/whisper.cpp/build/bin/whisper-cli \
    IGRIS_WHISPER_CPP_MODEL=/app/models/ggml-medium-q5_0.bin

# --------------------------------------------------------------
# Healthcheck: Coolify solo reinicia el contenedor si sabe que está caído.
# Sin esto el servicio queda en "Running (no healthcheck)" y un cuelgue pasa
# inadvertido hasta que un usuario se queja.
# start-period=180s cubre las migraciones y el primer arranque, que es cuando
# más tarda en responder.
# --------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# --------------------------------------------------------------
# Comando de arranque
# --------------------------------------------------------------
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

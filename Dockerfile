FROM python:3.12-slim

# Instalar curl y wget
RUN apt-get update && apt-get install -y curl wget && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "bcrypt==4.0.1"
COPY core ./core
COPY server ./server
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

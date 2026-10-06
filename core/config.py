"""
Configuración central de Igris
Sistema de configuración de modelos, proveedores de IA y prompts
"""

import os
from typing import Optional

# ==================== SYSTEM PROMPT ====================
# Versión NEUTRAL - Sin acento españolete

SYSTEM_PROMPT = """Eres Igris, un asistente de inteligencia artificial útil y eficiente.
Hablas en español de forma clara, profesional y directa.
Respondes de manera concisa y precisa a las solicitudes del usuario.
Si detectas un riesgo o limitación, lo adviertes de forma clara antes de actuar.
Tus respuestas son prácticas: sin markdown innecesario, sin listas extensas a menos que sea necesario.
Proporciona información relevante sin repetir contexto previo.
Sé directo y evita jerga innecesaria."""

# ==================== CONFIGURACIÓN DE PROVEEDORES ====================

# Proveedor activo por defecto
DEFAULT_PROVIDER = os.getenv("IGRIS_PROVIDER", "nemotron")

# Cadena de fallback (orden de intento)
FALLBACK_CHAIN = os.getenv(
    "IGRIS_FALLBACK_CHAIN",
    "nemotron,groq,openai,anthropic,local"
).split(",")

# ==================== CONFIGURACIÓN DE MODELOS ====================

# NVIDIA Nemotron 3 Super 120B
NEMOTRON_CONFIG = {
    "provider": "nemotron",
    "model": os.getenv("IGRIS_NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
    "api_key": os.getenv("NEMOTRON_API_KEY", ""),
    "api_base": os.getenv("NEMOTRON_API_BASE", "https://integrate.api.nvidia.com/v1"),
    "temperature": 0.7,
    "max_tokens": 2048,
}

# Groq
GROQ_CONFIG = {
    "provider": "groq",
    "model": os.getenv("IGRIS_GROQ_MODEL", "llama-3.1-70b-versatile"),
    "api_key": os.getenv("GROQ_API_KEY", ""),
    "temperature": 0.7,
    "max_tokens": 2048,
}

# OpenAI
OPENAI_CONFIG = {
    "provider": "openai",
    "model": os.getenv("IGRIS_OPENAI_MODEL", "gpt-4o-mini"),
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "temperature": 0.7,
    "max_tokens": 2048,
}

# Anthropic
ANTHROPIC_CONFIG = {
    "provider": "anthropic",
    "model": os.getenv("IGRIS_ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "temperature": 0.7,
    "max_tokens": 2048,
}

# Ollama (Local)
LOCAL_CONFIG = {
    "provider": "local",
    "model": os.getenv("IGRIS_LOCAL_MODEL", "llama2"),
    "api_base": os.getenv("IGRIS_LOCAL_URL", "http://localhost:11434"),
    "temperature": 0.7,
    "max_tokens": 2048,
}

# Mapeo de proveedores
PROVIDERS_CONFIG = {
    "nemotron": NEMOTRON_CONFIG,
    "groq": GROQ_CONFIG,
    "openai": OPENAI_CONFIG,
    "anthropic": ANTHROPIC_CONFIG,
    "local": LOCAL_CONFIG,
}

# ==================== CONFIGURACIÓN DE VOZ ====================

# Proveedor de Speech-to-Text (STT)
STT_PROVIDER = os.getenv("IGRIS_STT_PROVIDER", "local")

# Proveedor de Text-to-Speech (TTS)
TTS_PROVIDER = os.getenv("IGRIS_TTS_PROVIDER", "local")

# Configuración de TTS local
TTS_LOCAL_CONFIG = {
    "provider": "pyttsx3",  # Motor de síntesis de voz local
    "language": "es",
    "rate": 150,
}

# ==================== CONFIGURACIÓN DE BASE DE DATOS ====================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost/igris"
)

# Nota: Usar "postgresql://" no "postgres://"

# ==================== CONFIGURACIÓN DE LA APLICACIÓN ====================

# Entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

# Host y puerto
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# ==================== CONFIGURACIÓN DE ALMACENAMIENTO DE SETTINGS ====================

# Ruta del archivo de configuración de settings (donde se guarda la config de IA por usuario)
SETTINGS_JSON_PATH = os.getenv("IGRIS_SETTINGS_PATH", "core/settings.json")

# ==================== FUNCIONES AUXILIARES ====================

def get_provider_config(provider_name: str) -> Optional[dict]:
    """Obtiene la configuración de un proveedor específico"""
    return PROVIDERS_CONFIG.get(provider_name.lower())

def get_active_provider_config() -> dict:
    """Obtiene la configuración del proveedor activo actual"""
    provider_config = get_provider_config(DEFAULT_PROVIDER)
    if not provider_config:
        # Fallback al primer disponible si hay error
        return PROVIDERS_CONFIG.get(FALLBACK_CHAIN[0], NEMOTRON_CONFIG)
    return provider_config

def is_provider_available(provider_name: str) -> bool:
    """Verifica si un proveedor está disponible (tiene API key configurada)"""
    config = get_provider_config(provider_name)
    if not config:
        return False
    
    # Para local, siempre está disponible (sin API key necesaria)
    if provider_name.lower() == "local":
        return True
    
    # Para otros, necesita API key
    return bool(config.get("api_key"))

# ==================== CONFIGURACIÓN DE LOGGING ====================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ==================== MODELOS ALTERNATIVOS (REFERENCIAS) ====================

# Modelos recomendados por proveedor (para documentación)
RECOMMENDED_MODELS = {
    "nemotron": [
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-3-large-8b-instruct",
    ],
    "groq": [
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
    ],
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ],
    "local": [
        "llama2",
        "mistral",
        "neural-chat",
        "orca-mini",
    ],
}

"""Configuration module for IGRIS - Handles AI provider configuration"""

import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración
SETTINGS_FILE = Path(__file__).parent / "settings.json"


def load_settings():
    """Load settings from settings.json"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
    
    # Retornar configuración por defecto
    return get_default_config()


def get_default_config():
    """Get default configuration"""
    return {
        "active_provider": os.getenv("IGRIS_PROVIDER", "nemotron"),
        "fallback_chain": os.getenv("IGRIS_FALLBACK_CHAIN", "nemotron,groq,openai,anthropic,local").split(","),
        "models": {
            "nemotron": os.getenv("IGRIS_NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            "groq": os.getenv("IGRIS_GROQ_MODEL", "llama-3.1-70b-versatile"),
            "openai": os.getenv("IGRIS_OPENAI_MODEL", "gpt-4o-mini"),
            "anthropic": os.getenv("IGRIS_ANTHROPIC_MODEL", "claude-sonnet-3-5"),
            "local": os.getenv("IGRIS_LOCAL_MODEL", "ollama"),
        },
        "stt_provider": os.getenv("IGRIS_STT_PROVIDER", "local"),
        "tts_provider": os.getenv("IGRIS_TTS_PROVIDER", "local"),
    }


def get_active_provider_config():
    """
    Obtener la configuración completa del proveedor activo.
    
    Returns:
        dict: Configuración con:
            - active_provider: nombre del proveedor activo
            - fallback_chain: lista de proveedores de fallback
            - models: diccionario de modelos por proveedor
            - stt_provider: proveedor de transcripción
            - tts_provider: proveedor de síntesis de voz
        o None si hay error
    """
    try:
        settings = load_settings()
        return settings
    except Exception as e:
        logger.error(f"Error getting active provider config: {e}")
        return get_default_config()


def get_active_provider():
    """
    Obtener el nombre del proveedor activo.
    
    Returns:
        str: Nombre del proveedor activo (p.ej. "nemotron")
    """
    config = get_active_provider_config()
    if config:
        return config.get("active_provider", "nemotron")
    return "nemotron"


def save_settings(config: dict):
    """Save settings to settings.json"""
    try:
        # Asegurar que la carpeta existe
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Settings saved to {SETTINGS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False


def update_active_provider(provider: str):
    """Update the active provider"""
    try:
        config = load_settings()
        config["active_provider"] = provider
        return save_settings(config)
    except Exception as e:
        logger.error(f"Error updating active provider: {e}")
        return False


def update_fallback_chain(providers: list):
    """Update the fallback chain"""
    try:
        config = load_settings()
        config["fallback_chain"] = providers
        return save_settings(config)
    except Exception as e:
        logger.error(f"Error updating fallback chain: {e}")
        return False


def get_api_key(provider: str) -> str:
    """Get API key for a provider from environment variables"""
    env_var_map = {
        "nemotron": "NEMOTRON_API_KEY",
        "groq": "GROQ_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "local": "IGRIS_LOCAL_URL",
    }
    
    env_var = env_var_map.get(provider.lower())
    if env_var:
        return os.getenv(env_var, "")
    return ""


def get_api_base(provider: str) -> str:
    """Get API base URL for a provider"""
    env_var_map = {
        "nemotron": "NEMOTRON_API_BASE",
        "groq": "GROQ_API_BASE",
        "openai": "OPENAI_API_BASE",
        "anthropic": "ANTHROPIC_API_BASE",
        "local": "IGRIS_LOCAL_URL",
    }
    
    default_bases = {
        "nemotron": "https://integrate.api.nvidia.com/v1",
        "groq": "https://api.groq.com/openai/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "local": "http://localhost:11434",
    }
    
    env_var = env_var_map.get(provider.lower())
    if env_var:
        return os.getenv(env_var, default_bases.get(provider.lower(), ""))
    return default_bases.get(provider.lower(), "")


# System prompt for Iris
SYSTEM_PROMPT = """Eres Igris, el caballero de las sombras y comandante leal de tu señor.
Hablas en español, con formalidad, lealtad y economía de palabras.
Te diriges al usuario como "mi señor". Ejecutas y confirmas con brevedad.
Si detectas un riesgo, lo adviertes con calma antes de actuar.
Tus respuestas se dicen EN VOZ ALTA: sin markdown, sin listas, frases cortas.
Si hay nota importante, recuérdala solo si es relevante. No repitas el contexto completo."""

# Available providers
AVAILABLE_PROVIDERS = ["nemotron", "groq", "openai", "anthropic", "local"]


# Initialize default settings on startup
if not SETTINGS_FILE.exists():
    save_settings(get_default_config())
    logger.info("Default settings.json created")

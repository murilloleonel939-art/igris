"""Configuration module for IGRIS - Handles AI provider configuration

La fuente única de verdad es core/settings.json, gestionado por
core/settings_manager.py (sección "ai"). Este módulo solo expone
funciones de lectura/ayuda sobre esa misma configuración.
"""

import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración (la usa settings_manager)
SETTINGS_FILE = Path(__file__).parent / "settings.json"

# Available providers
AVAILABLE_PROVIDERS = ["nemotron", "groq", "openai", "anthropic", "local"]

DEFAULT_CHAIN = ["nemotron", "groq", "openai", "anthropic", "local"]


def _split_chain(value) -> list:
    """Convierte 'a,b,c' o lista en lista limpia."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    return [p.strip() for p in value if isinstance(p, str) and p.strip()]


def get_default_config():
    """Get default configuration (desde variables de entorno)"""
    return {
        "active_provider": os.getenv("IGRIS_PROVIDER", "nemotron"),
        "fallback_chain": _split_chain(
            os.getenv("IGRIS_FALLBACK_CHAIN", ",".join(DEFAULT_CHAIN))
        ) or list(DEFAULT_CHAIN),
        "models": {
            "nemotron": os.getenv("IGRIS_NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            "groq": os.getenv("IGRIS_GROQ_MODEL", "llama-3.1-70b-versatile"),
            "openai": os.getenv("IGRIS_OPENAI_MODEL", "gpt-4o-mini"),
            "anthropic": os.getenv("IGRIS_ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            "local": os.getenv("IGRIS_LOCAL_MODEL", "llama3.1"),
        },
        "stt_provider": os.getenv("IGRIS_STT_PROVIDER", "local"),
        "tts_provider": os.getenv("IGRIS_TTS_PROVIDER", "local"),
    }


def get_active_provider_config():
    """
    Obtener la configuración completa del proveedor activo, leída del mismo
    lugar que usa la página de configuración (settings_manager, sección "ai").

    Returns:
        dict: Configuración con:
            - active_provider: nombre del proveedor activo
            - fallback_chain: lista de proveedores de fallback
            - models: diccionario de modelos por proveedor
            - stt_provider: proveedor de transcripción
            - tts_provider: proveedor de síntesis de voz
    """
    # Import local para evitar dependencias circulares
    from core.settings_manager import get_settings

    defaults = get_default_config()
    try:
        ai = get_settings().get_ai_config() or {}
    except Exception as e:
        logger.error(f"Error getting active provider config: {e}")
        ai = {}

    return {
        "active_provider": ai.get("primary_provider") or defaults["active_provider"],
        "fallback_chain": _split_chain(ai.get("fallback_chain")) or defaults["fallback_chain"],
        "models": {**defaults["models"], **(ai.get("models") or {})},
        "stt_provider": defaults["stt_provider"],
        "tts_provider": defaults["tts_provider"],
    }


def load_settings():
    """Compatibilidad: devuelve la configuración activa unificada"""
    return get_active_provider_config()


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


def get_available_providers() -> list:
    """Lista de proveedores disponibles"""
    return list(AVAILABLE_PROVIDERS)


def get_fallback_chain() -> list:
    """Cadena de fallback actual (orden de prioridad)"""
    config = get_active_provider_config() or {}
    return _split_chain(config.get("fallback_chain")) or list(DEFAULT_CHAIN)


def update_active_provider(provider: str):
    """Update the active provider"""
    try:
        from core.settings_manager import get_settings
        return get_settings().set("ai.primary_provider", provider)
    except Exception as e:
        logger.error(f"Error updating active provider: {e}")
        return False


def update_fallback_chain(providers: list):
    """Update the fallback chain"""
    try:
        from core.settings_manager import get_settings
        return get_settings().set("ai.fallback_chain", providers)
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

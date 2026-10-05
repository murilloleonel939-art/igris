"""Configuración centralizada de Igris: proveedores, modelos, fallbacks.
Diseñado para ser controlable desde un panel de administración futuro."""
import os
import json

# Configuración de proveedores disponibles
PROVIDERS_CONFIG = {
    "groq": {
        "enabled": os.environ.get("GROQ_API_KEY") is not None,
        "api_key": os.environ.get("GROQ_API_KEY", ""),
        "model": os.environ.get("IGRIS_GROQ_MODEL", "openai/gpt-oss-120b"),
        "priority": 1,  # Prioridad más alta = se intenta primero
    },
    "openai": {
        "enabled": os.environ.get("OPENAI_API_KEY") is not None,
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
        "model": os.environ.get("IGRIS_OPENAI_MODEL", "gpt-4o-mini"),
        "priority": 2,
    },
    "anthropic": {
        "enabled": os.environ.get("ANTHROPIC_API_KEY") is not None,
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "model": os.environ.get("IGRIS_ANTHROPIC_MODEL", "claude-sonnet-3-5"),
        "priority": 3,
    },
    "local": {
        "enabled": True,  # Siempre disponible como último recurso
        "model": os.environ.get("IGRIS_LOCAL_MODEL", "ollama"),
        "url": os.environ.get("IGRIS_LOCAL_URL", "http://localhost:11434"),
        "priority": 999,  # Último recurso
    },
}

# Ordenar proveedores por prioridad
ORDERED_PROVIDERS = sorted(
    [(name, config) for name, config in PROVIDERS_CONFIG.items() if config.get("enabled")],
    key=lambda x: x[1].get("priority", 999)
)

# Proveedor activo y cadena de fallback: definido por el usuario o auto-detectado
ACTIVE_PROVIDER = os.environ.get("IGRIS_PROVIDER", "").lower().strip()
FALLBACK_CHAIN_STR = os.environ.get("IGRIS_FALLBACK_CHAIN", "groq,openai,anthropic,local").lower().split(",")

# Si IGRIS_PROVIDER está vacío, usar el primero disponible
if not ACTIVE_PROVIDER:
    available = [name for name, cfg in PROVIDERS_CONFIG.items() if cfg.get("enabled")]
    if available:
        ACTIVE_PROVIDER = available[0]
        print(f"ℹ️ IGRIS_PROVIDER vacío. Auto-detectado: {ACTIVE_PROVIDER}")
    else:
        # Fallback a groq (puede fallar luego si no tiene API key, pero al menos inicia)
        ACTIVE_PROVIDER = "groq"
        print(f"⚠️ IGRIS_PROVIDER vacío y no hay proveedores disponibles. Usando: {ACTIVE_PROVIDER}")

# Validar que el proveedor está disponible
if ACTIVE_PROVIDER not in PROVIDERS_CONFIG:
    raise ValueError(f"❌ IGRIS_PROVIDER='{ACTIVE_PROVIDER}' no es válido. Opciones: {list(PROVIDERS_CONFIG.keys())}")

# Validar cadena de fallback
FALLBACK_CHAIN = [p.strip() for p in FALLBACK_CHAIN_STR if p.strip() in PROVIDERS_CONFIG]
if ACTIVE_PROVIDER not in FALLBACK_CHAIN:
    FALLBACK_CHAIN.insert(0, ACTIVE_PROVIDER)

print(f"ℹ️ IGRIS: Proveedor primario={ACTIVE_PROVIDER}, Fallback chain={FALLBACK_CHAIN}")

TIMEZONE = os.environ.get("IGRIS_TZ", "America/Bogota")

# Configuración global
SYSTEM_PROMPT = """Eres Igris, el caballero de las sombras y comandante leal de tu señor.
Hablas en español, con formalidad, lealtad y economía de palabras.
Te diriges al usuario como "mi señor". Ejecutas y confirmas con brevedad.
Si detectas un riesgo, lo adviertes con calma antes de actuar.
Tus respuestas se dicen EN VOZ ALTA: sin markdown, sin listas, frases cortas.
Si hay nota importante, recuérdala solo si es relevante. No repitas el contexto completo."""

def get_active_provider():
    """Obtiene el proveedor activo actual."""
    return ACTIVE_PROVIDER

def set_active_provider(provider_name):
    """Cambia el proveedor activo (para panel de control futuro)."""
    global ACTIVE_PROVIDER
    if provider_name in dict(ORDERED_PROVIDERS):
        ACTIVE_PROVIDER = provider_name
        return True
    return False

def get_available_providers():
    """Devuelve lista de proveedores disponibles."""
    return [name for name, _ in ORDERED_PROVIDERS]

def get_provider_config(provider_name=None):
    """Obtiene configuración de un proveedor."""
    if provider_name is None:
        provider_name = ACTIVE_PROVIDER
    return PROVIDERS_CONFIG.get(provider_name)

def get_fallback_chain():
    """Devuelve la cadena de fallback ordenada por prioridad."""
    return [name for name, _ in ORDERED_PROVIDERS]

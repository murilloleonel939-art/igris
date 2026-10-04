"""Gestor de configuración persistente para Igris.
Carga/guarda settings desde settings.json para sincronizar con Raspberry Pi."""
import json
import os
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent / "settings.json"

class SettingsManager:
    def __init__(self):
        self.settings = self.load()

    def load(self) -> dict:
        """Carga la configuración desde settings.json."""
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ {SETTINGS_FILE} no encontrado. Usando defaults.")
            return self.get_defaults()

    def save(self) -> bool:
        """Guarda la configuración en settings.json."""
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=2)
            print(f"✓ Configuración guardada en {SETTINGS_FILE}")
            return True
        except Exception as e:
            print(f"✗ Error al guardar configuración: {e}")
            return False

    def get(self, key: str, default=None):
        """Obtiene un valor de la configuración."""
        keys = key.split(".")
        value = self.settings
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value) -> bool:
        """Establece un valor en la configuración."""
        keys = key.split(".")
        config = self.settings
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        return self.save()

    def get_ai_config(self) -> dict:
        """Obtiene configuración de IA."""
        return self.settings.get("ai", {})

    def set_ai_config(self, config: dict) -> bool:
        """Establece configuración de IA."""
        self.settings["ai"] = config
        return self.save()

    def get_stt_config(self) -> dict:
        """Obtiene configuración de STT."""
        return self.settings.get("stt", {})

    def get_tts_config(self) -> dict:
        """Obtiene configuración de TTS."""
        return self.settings.get("tts", {})

    def update_provider(self, provider: str, fallback_chain: list) -> bool:
        """Actualiza el proveedor primario y la cadena de fallback."""
        self.settings["ai"]["primary_provider"] = provider
        self.settings["ai"]["fallback_chain"] = fallback_chain
        return self.save()

    def get_defaults(self) -> dict:
        """Devuelve la configuración por defecto."""
        return {
            "version": "1.0",
            "ai": {
                "primary_provider": "groq",
                "fallback_chain": ["groq", "openai", "anthropic", "local"],
                "models": {
                    "groq": "llama-3.1-70b-versatile",
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-sonnet-3-5",
                    "local": "ollama"
                }
            },
            "stt": {
                "provider": "local",
                "model": "tiny",
                "language": "es"
            },
            "tts": {
                "provider": "local",
                "voice": "es_ES-carlos-medium",
                "instructions": "Habla como un caballero de las sombras."
            },
            "system": {
                "personality": "caballero_sombras",
                "timezone": "America/Bogota",
                "language": "es"
            },
            "raspberry_pi": {
                "enabled": False,
                "url": "",
                "auto_sync": True
            }
        }

# Instancia global
_settings = None

def get_settings() -> SettingsManager:
    """Obtiene la instancia global del gestor de configuración."""
    global _settings
    if _settings is None:
        _settings = SettingsManager()
    return _settings

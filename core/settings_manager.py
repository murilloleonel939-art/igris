"""Gestor de configuración persistente para Igris.
Carga/guarda settings desde settings.json para sincronizar con Raspberry Pi."""
import json
import os
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent / "settings.json"

# Proveedores válidos (deben coincidir con core/config.py y PROVIDERS de core/brain.py)
VALID_PROVIDERS = ("nemotron", "openai", "anthropic", "local")


def _sanitize_ai(ai: dict) -> dict:
    """Quita de la sección "ai" los proveedores que ya no existen (ej. groq de un
    settings.json antiguo). Solo corrige en memoria; el disco se actualiza en el
    próximo guardado."""
    primary = ai.get("primary_provider")
    if primary not in VALID_PROVIDERS:
        ai.pop("primary_provider", None)  # se usará el valor por defecto

    chain = ai.get("fallback_chain")
    if isinstance(chain, list):
        clean = [p for p in chain if isinstance(p, str) and p in VALID_PROVIDERS]
        ai["fallback_chain"] = list(dict.fromkeys(clean))
        if not ai["fallback_chain"]:
            ai.pop("fallback_chain")

    models = ai.get("models")
    if isinstance(models, dict):
        ai["models"] = {k: v for k, v in models.items() if k in VALID_PROVIDERS}
    return ai


class SettingsManager:
    def __init__(self):
        self.settings = self.load()

    def load(self) -> dict:
        """Carga la configuración desde settings.json."""
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"⚠️ {SETTINGS_FILE} no encontrado. Usando defaults.")
            return self.get_defaults()
        except Exception as e:
            print(f"⚠️ Error leyendo {SETTINGS_FILE}: {e}. Usando defaults.")
            return self.get_defaults()

        if not isinstance(data, dict):
            return self.get_defaults()

        # Si el archivo tiene el formato plano antiguo (sin sección "ai"),
        # completar con los defaults para no perder la configuración.
        if not isinstance(data.get("ai"), dict):
            data["ai"] = self.get_defaults()["ai"]
        else:
            data["ai"] = _sanitize_ai(data["ai"])
        return data

    def save(self) -> bool:
        """Guarda la configuración en settings.json."""
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
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
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        return self.save()

    def get_ai_config(self) -> dict:
        """Obtiene configuración de IA."""
        return self.settings.get("ai", {})

    def set_ai_config(self, config: dict) -> bool:
        """Establece configuración de IA."""
        self.settings["ai"] = _sanitize_ai(dict(config))
        return self.save()

    def get_stt_config(self) -> dict:
        """Obtiene configuración de STT."""
        return self.settings.get("stt", {})

    def get_tts_config(self) -> dict:
        """Obtiene configuración de TTS."""
        return self.settings.get("tts", {})

    def update_provider(self, provider: str, fallback_chain: list) -> bool:
        """Actualiza el proveedor primario y la cadena de fallback."""
        ai = self.settings.setdefault("ai", {})
        ai["primary_provider"] = provider
        ai["fallback_chain"] = fallback_chain
        self.settings["ai"] = _sanitize_ai(ai)
        return self.save()

    def get_defaults(self) -> dict:
        """Devuelve la configuración por defecto."""
        chain = [
            p.strip()
            for p in os.getenv(
                "IGRIS_FALLBACK_CHAIN", ",".join(VALID_PROVIDERS)
            ).split(",")
            if p.strip() in VALID_PROVIDERS
        ] or list(VALID_PROVIDERS)
        primary = os.getenv("IGRIS_PROVIDER", "nemotron")
        if primary not in VALID_PROVIDERS:
            primary = "nemotron"
        return {
            "version": "1.0",
            "ai": {
                "primary_provider": primary,
                "fallback_chain": chain,
                "models": {
                    "nemotron": os.getenv("IGRIS_NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-sonnet-5-5",
                    "local": "llama3.1"
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

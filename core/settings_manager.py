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
        """Resuelve overrides del panel sobre los valores base de entorno."""
        saved = self.settings.get("stt", {})
        saved = saved if isinstance(saved, dict) else {}
        defaults = self.get_defaults()["stt"]
        result = {**defaults, **saved}
        # Solo un cambio explícito del panel debe prevalecer sobre Coolify.
        # La clave legacy "model" se ignora: podía dejar tiny fijo aunque el
        # administrador hubiera configurado otro modelo en el entorno.
        if not saved.get("provider_override"):
            result["provider"] = defaults["provider"]
        return result

    def set_stt_config(self, config: dict) -> bool:
        """Guarda solo overrides STT (nunca claves secretas ni defaults redundantes)."""
        defaults = self.get_defaults()["stt"]
        current = self.settings.get("stt", {})
        current = dict(current) if isinstance(current, dict) else {}
        for key in ("provider", "cloud_model", "local_engine", "local_model", "local_compute_type", "whisper_cpp_model", "language"):
            if key not in config or config[key] is None:
                continue
            value = str(config[key]).strip()
            if key == "provider":
                value = value.lower()
                if value not in {"local", "deepgram", "openai"}:
                    raise ValueError("Proveedor STT no válido. Usa local, deepgram u openai.")
                current[key] = value
                current["provider_override"] = True
            elif key == "language":
                value = value.lower()
                current[key] = value
            elif value:
                if key == "local_engine" and value not in {"whisper", "faster-whisper", "whisper.cpp"}:
                    raise ValueError("Motor local no válido. Usa whisper, faster-whisper o whisper.cpp.")
                if key == "local_model" and value not in {"tiny", "base", "small", "medium"}:
                    raise ValueError("Modelo local no válido. Usa tiny, base, small o medium.")
                if key == "local_compute_type" and value not in {"int8", "float16", "float32"}:
                    raise ValueError("Tipo de cómputo no válido. Usa int8, float16 o float32.")
                current[key] = value
        self.settings["stt"] = current
        return self.save()

    def get_whatsapp_config(self) -> dict:
        """Obtiene la configuración no secreta de WhatsApp."""
        saved = self.settings.get("whatsapp", {})
        return dict(saved) if isinstance(saved, dict) else {}

    def set_whatsapp_config(self, config: dict) -> bool:
        """Guarda la configuración no secreta de WhatsApp."""
        self.settings["whatsapp"] = dict(config)
        return self.save()

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
                "provider": os.getenv("IGRIS_STT_PROVIDER", "local"),
                "cloud_model": os.getenv("IGRIS_STT_MODEL", "whisper-1"),
                "local_engine": os.getenv("IGRIS_STT_LOCAL_ENGINE", "whisper"),
                "local_compute_type": os.getenv("IGRIS_STT_COMPUTE_TYPE", "int8"),
                "whisper_cpp_model": os.getenv("IGRIS_WHISPER_CPP_MODEL", ""),
                "local_model": os.getenv("IGRIS_WHISPER_MODEL", "tiny"),
                "language": os.getenv("IGRIS_STT_LANGUAGE", "es")
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

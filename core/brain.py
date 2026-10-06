"""Brain module for IGRIS - orquestación de IA con cadena de fallback"""

import logging
import os
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from core.config import SYSTEM_PROMPT
from core.settings_manager import get_settings

logger = logging.getLogger(__name__)

DEFAULT_CHAIN = ["nemotron", "openai", "anthropic", "local"]

# Tokens máximos por respuesta. Nemotron es un modelo con razonamiento:
# con límites bajos (ej. 512) gasta todo pensando y devuelve content vacío.
MAX_TOKENS = int(os.environ.get("IGRIS_MAX_TOKENS", "2048"))

# Todos los proveedores se consumen con el SDK de OpenAI (APIs compatibles).
PROVIDERS = {
    "nemotron": {
        "key_env": "NEMOTRON_API_KEY",
        "base_env": "NEMOTRON_API_BASE",
        "base_default": "https://integrate.api.nvidia.com/v1",
        "model_env": "IGRIS_NEMOTRON_MODEL",
        "model_default": "nvidia/nemotron-3-super-120b-a12b",
        "timeout": 60,
    },
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "base_default": "https://api.openai.com/v1",
        "model_env": "IGRIS_OPENAI_MODEL",
        "model_default": "gpt-4o-mini",
        "timeout": 30,
    },
    "anthropic": {
        "key_env": "ANTHROPIC_API_KEY",
        "base_default": "https://api.anthropic.com/v1/",
        "model_env": "IGRIS_ANTHROPIC_MODEL",
        "model_default": "claude-sonnet-5-5",
        "timeout": 30,
    },
    "local": {
        "key_env": None,
        "model_env": "IGRIS_LOCAL_MODEL",
        "model_default": "llama3.1",
        "timeout": 60,
    },
}


def _build_client(name: str):
    """Devuelve (cliente, modelo) para el proveedor, o None si no está configurado."""
    spec = PROVIDERS.get(name)
    if not spec:
        logger.warning(f"Proveedor desconocido en la cadena: {name}")
        return None

    model = os.environ.get(spec["model_env"]) or spec["model_default"]

    if name == "local":
        base = os.environ.get("IGRIS_LOCAL_URL", "http://localhost:11434").rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        return AsyncOpenAI(api_key="ollama", base_url=base, timeout=spec["timeout"]), model

    api_key = os.environ.get(spec["key_env"], "")
    if not api_key:
        logger.warning(f"Proveedor '{name}' omitido: falta {spec['key_env']}")
        return None

    base = os.environ.get(spec.get("base_env", ""), "") or spec["base_default"]
    return AsyncOpenAI(api_key=api_key, base_url=base, timeout=spec["timeout"]), model


class BrainSession:
    """Una conversación con historial."""

    def __init__(self, brain: "Brain"):
        self.brain = brain
        self.history: List[Dict[str, str]] = []

    async def say(self, text: str, context: Optional[dict] = None) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self.history[-20:]
        messages.append({"role": "user", "content": text})

        errors = []
        for name in self.brain.fallback_chain:
            built = _build_client(name)
            if not built:
                errors.append(f"{name}: no configurado")
                continue
            client, model = built
            logger.info(f"Intentando proveedor: {name} ({model})")
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=MAX_TOKENS,
                )
                choice = resp.choices[0]
                reply = (choice.message.content or "").strip()
                if not reply:
                    raise ValueError(
                        f"respuesta vacía (finish_reason={choice.finish_reason})"
                    )
                self.history.append({"role": "user", "content": text})
                self.history.append({"role": "assistant", "content": reply})
                return reply
            except Exception as e:
                logger.error(f"Proveedor '{name}' falló: {e}")
                errors.append(f"{name}: {e}")
            finally:
                await client.close()

        raise RuntimeError("Todos los proveedores fallaron -> " + " | ".join(errors))


class Brain:
    """Orquesta los proveedores de IA según la configuración activa."""

    def __init__(self):
        self.provider = "nemotron"
        self.fallback_chain: List[str] = list(DEFAULT_CHAIN)
        self.reload_settings()

    def reload_settings(self):
        """Relee proveedor activo y cadena de fallback."""
        primary, chain = None, None
        try:
            ai = get_settings().get_ai_config() or {}
            primary = ai.get("primary_provider")
            chain = ai.get("fallback_chain")
        except Exception as e:
            logger.error(f"No se pudo leer settings: {e}")

        primary = primary or os.environ.get("IGRIS_PROVIDER") or "nemotron"
        if not isinstance(chain, list) or not chain:
            env_chain = os.environ.get("IGRIS_FALLBACK_CHAIN", "")
            chain = [p.strip() for p in env_chain.split(",") if p.strip()] or list(DEFAULT_CHAIN)

        # Descarta proveedores que ya no existen (ej. groq guardado en settings viejos)
        chain = [p for p in chain if p in PROVIDERS]
        if primary not in PROVIDERS:
            primary = DEFAULT_CHAIN[0]

        self.provider = primary
        self.fallback_chain = [primary] + [p for p in chain if p != primary]
        logger.info(f"Config recargada. Orden de proveedores: {self.fallback_chain}")

    def new_session(self) -> BrainSession:
        return BrainSession(self)


def init_brain():
    """Initialize the Brain"""
    return Brain()

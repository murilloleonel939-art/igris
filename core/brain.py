"""Brain module for IGRIS - Core AI orchestration"""

import logging
from core import config

logger = logging.getLogger(__name__)

# Obtener el proveedor activo usando el método correcto
PROVIDER_CONFIG = config.get_active_provider_config()
if PROVIDER_CONFIG:
    PROVIDER = PROVIDER_CONFIG.get("active_provider", "nemotron")
else:
    PROVIDER = "nemotron"


class Brain:
    """Brain class for managing AI responses"""

    def __init__(self):
        self.provider = PROVIDER
        self.config = PROVIDER_CONFIG
        self.logger = logger

    def process(self, message: str, context: dict = None) -> str:
        """Process a message and generate a response"""
        try:
            # Obtener el proveedor activo en cada request (por si cambió)
            provider_config = config.get_active_provider_config()
            if provider_config:
                self.provider = provider_config.get("active_provider", "nemotron")
                self.config = provider_config

            # Aquí va la lógica de procesamiento
            response = self._generate_response(message, context)
            return response

        except Exception as e:
            self.logger.error(f"Error in Brain.process: {e}")
            raise

    def _generate_response(self, message: str, context: dict = None) -> str:
        """Generate response using configured provider"""
        # Implementation goes here
        return f"Response from {self.provider}"


def init_brain():
    """Initialize the Brain"""
    return Brain()

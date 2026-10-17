"""Cliente mínimo para la WhatsApp Cloud API de Meta.

Las credenciales se leen exclusivamente desde variables de entorno. No se
persisten ni se incluyen en los logs ni en los mensajes de error.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

GRAPH_VERSION = "v23.0"
GRAPH_BASE = "https://graph.facebook.com"


class WhatsAppConfigurationError(RuntimeError):
    """Falta configuración necesaria para usar la Cloud API."""


class WhatsAppAPIError(RuntimeError):
    """Meta rechazó una solicitud o no respondió correctamente."""


class WhatsAppClient:
    """Cliente asíncrono para enviar mensajes vía Graph API."""

    def __init__(
        self,
        token: str | None = None,
        phone_number_id: str | None = None,
        base_url: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.token = token or os.getenv("WHATSAPP_TOKEN", "").strip()
        self.phone_number_id = (
            phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        )
        self.base_url = (base_url or os.getenv("WHATSAPP_API_BASE", GRAPH_BASE)).rstrip("/")
        self.timeout = timeout

    def _validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("WHATSAPP_TOKEN", self.token),
                ("WHATSAPP_PHONE_NUMBER_ID", self.phone_number_id),
            )
            if not value
        ]
        if missing:
            raise WhatsAppConfigurationError(
                "Faltan variables de WhatsApp: " + ", ".join(missing)
            )

    def _url(self) -> str:
        return f"{self.base_url}/{GRAPH_VERSION}/{self.phone_number_id}/messages"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def send_text(
        self,
        to: str,
        text: str,
        preview_url: bool = False,
    ) -> dict[str, Any]:
        """Envía un mensaje de texto libre. Requiere ventana de 24 h abierta."""
        self._validate()
        recipient = (to or "").strip().lstrip("+")
        body = (text or "").strip()
        if not recipient.isdigit():
            raise ValueError(
                "El destinatario debe estar en formato E.164 sin '+', por ejemplo 573504807732"
            )
        if not body:
            raise ValueError("El mensaje no puede estar vacío")
        if len(body) > 4096:
            raise ValueError("El texto supera el límite de 4096 caracteres")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": preview_url, "body": body},
        }
        return await self._post(payload)

    async def send_template(
        self,
        to: str,
        name: str,
        language: str = "es",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Envía una plantilla aprobada; funciona con la ventana cerrada."""
        self._validate()
        recipient = (to or "").strip().lstrip("+")
        if not recipient.isdigit():
            raise ValueError("El destinatario debe estar en formato E.164 sin '+'")
        if not (name or "").strip():
            raise ValueError("La plantilla necesita un nombre")

        template: dict[str, Any] = {
            "name": name.strip(),
            "language": {"code": language},
        }
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "template",
            "template": template,
        }
        return await self._post(payload)

    async def list_templates(self, waba_id: str | None = None) -> dict[str, Any]:
        """Lista las plantillas de la cuenta de WhatsApp Business."""
        waba = (waba_id or os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")).strip()
        if not self.token:
            raise WhatsAppConfigurationError("Falta WHATSAPP_TOKEN")
        if not waba:
            raise WhatsAppConfigurationError("Falta WHATSAPP_BUSINESS_ACCOUNT_ID")
        url = f"{self.base_url}/{GRAPH_VERSION}/{waba}/message_templates"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self._headers)
        return self._result(response)

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self._url(), headers=self._headers, json=payload)
        return self._result(response)

    @staticmethod
    def _result(response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise WhatsAppAPIError(
                f"Meta respondió HTTP {response.status_code}: {response.text[:500]}"
            )
        return response.json() if response.content else {"status_code": response.status_code}


async def send_test_message(text: str = "Prueba de conexión de Igris por WhatsApp") -> dict[str, Any]:
    """Envía la prueba al destinatario configurado en WHATSAPP_TEST_TO."""
    destination = os.getenv("WHATSAPP_TEST_TO", "+573504807732").strip()
    return await WhatsAppClient().send_text(destination, text)

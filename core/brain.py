"""Cerebro de Igris: personalidad, herramientas y conversación.
Lo usan tanto el servidor (EC2) como, más adelante, la Raspberry Pi (modo respaldo)."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from anthropic import AsyncAnthropic

MODEL = os.environ.get("IGRIS_MODEL", "claude-sonnet-5-5")
TIMEZONE = os.environ.get("IGRIS_TZ", "America/Bogota")

SYSTEM = """Eres Igris, el caballero de las sombras y comandante leal de tu señor.
Hablas en español, con formalidad, lealtad y economía de palabras.
Te diriges al usuario como "mi señor". Ejecutas y confirmas con brevedad.
Si detectas un riesgo, lo adviertes con calma antes de actuar.
Tus respuestas se dicen en voz alta: sin markdown, sin listas, frases cortas."""

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

TOOLS = [{
    "name": "obtener_hora",
    "description": "Devuelve la fecha y hora actual.",
    "input_schema": {"type": "object", "properties": {}},
}]


def run_tool(name: str, args: dict) -> str:
    if name == "obtener_hora":
        n = datetime.now(ZoneInfo(TIMEZONE))
        return f"{DIAS[n.weekday()]} {n.day} de {MESES[n.month-1]} de {n.year}, {n:%H:%M}"
    return "Herramienta desconocida."


def trim_history(history: list, keep: int = 20) -> list:
    """Recorta sin separar un tool_use de su tool_result:
    el historial siempre empieza en un mensaje de texto del usuario."""
    if len(history) <= keep:
        return history
    trimmed = history[-keep:]
    while trimmed and not (trimmed[0]["role"] == "user" and isinstance(trimmed[0]["content"], str)):
        trimmed = trimmed[1:]
    return trimmed


class Brain:
    def __init__(self):
        self.client = AsyncAnthropic()  # lee ANTHROPIC_API_KEY del entorno

    async def think(self, history: list) -> str:
        while True:
            resp = await self.client.messages.create(
                model=MODEL, max_tokens=500, system=SYSTEM,
                tools=TOOLS, messages=history,
            )
            history.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text")
            results = [
                {"type": "tool_result", "tool_use_id": b.id,
                 "content": run_tool(b.name, b.input)}
                for b in resp.content if b.type == "tool_use"
            ]
            history.append({"role": "user", "content": results})

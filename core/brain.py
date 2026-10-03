"""Cerebro de Igris: personalidad, herramientas y conversación.
Soporta Groq (gratuito local), OpenAI, Anthropic según IGRIS_PROVIDER.
Lo usan tanto el servidor (EC2) como, más adelante, la Raspberry Pi (modo respaldo)."""
import os, json
from datetime import datetime
from zoneinfo import ZoneInfo

PROVIDER = os.environ.get("IGRIS_PROVIDER", "groq").lower()   # "groq", "openai" o "anthropic"
GROQ_MODEL = os.environ.get("IGRIS_GROQ_MODEL", "llama-3.1-70b-versatile")
OPENAI_MODEL = os.environ.get("IGRIS_OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.environ.get("IGRIS_ANTHROPIC_MODEL", "claude-sonnet-5-5")
TIMEZONE = os.environ.get("IGRIS_TZ", "America/Bogota")

SYSTEM = """Eres Igris, el caballero de las sombras y comandante leal de tu señor.
Hablas en español, con formalidad, lealtad y economía de palabras.
Te diriges al usuario como "mi señor". Ejecutas y confirmas con brevedad.
Si detectas un riesgo, lo adviertes con calma antes de actuar.
Tus respuestas se dicen EN VOZ ALTA: sin markdown, sin listas, frases cortas.
Si hay nota importante, recuérdala solo si es relevante. No repitas el contexto completo."""

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Herramientas en formato neutro; cada proveedor las convierte a su formato.
TOOLS = [{
    "name": "obtener_hora",
    "description": "Devuelve la fecha y hora actual.",
    "parameters": {"type": "object", "properties": {}},
}, {
    "name": "recordar",
    "description": "Guarda un dato o nota para recordar luego (ej: 'recordar que apagar luz').",
    "parameters": {
        "type": "object",
        "properties": {
            "texto": {"type": "string", "description": "Lo que debe recordar Igris."},
        },
        "required": ["texto"],
    },
}, {
    "name": "clima_local",
    "description": "Devuelve el clima aproximado para la ciudad configurada (Bogotá por defecto).",
    "parameters": {
        "type": "object",
        "properties": {
            "ciudad": {"type": "string", "description": "Nombre de ciudad."},
        },
        "required": ["ciudad"],
    },
}, {
    "name": "estado_servidor",
    "description": "Indica si el servidor EC2 / Coolify está activo y si hay conexión con la Raspberry Pi.",
    "parameters": {"type": "object", "properties": {}},
}]


def run_tool(name: str, args: dict) -> str:
    if name == "obtener_hora":
        n = datetime.now(ZoneInfo(TIMEZONE))
        return f"{DIAS[n.weekday()]} {n.day} de {MESES[n.month-1]} de {n.year}, {n:%H:%M}"

    if name == "recordar":
        texto = args.get("texto", "").strip()
        # En un entorno real escribimos a archivo o memoria persistente compartida con Raspberry
        # Aquí simulamos confirmación; luego se sincroniza con el nodo cliente
        return f"Nota guardada: \"{texto}\". Confirmado, mi señor."

    if name == "clima_local":
        ciudad = args.get("ciudad", "Bogotá")
        # Respuesta aproximada para evitar llamadas externas de pago
        return f"Clima aproximado en {ciudad}: parcial, 18°C, sin lluvias. (Datos simulados para respaldo local)."

    if name == "estado_servidor":
        # Aquí en producción se consulta un archivo de estado o ping a Raspberry
        return "Servidor EC2 activo. Modo respaldo con Raspberry Pi pendiente (no conectado aún)."

    return "Herramienta desconocida."


def trim_history(history: list, keep: int = 20) -> list:
    """Recorta sin separar una llamada a herramienta de su resultado:
    el historial siempre empieza en un mensaje de texto del usuario."""
    if len(history) <= keep:
        return history
    trimmed = history[-keep:]
    while trimmed and not (trimmed[0]["role"] == "user" and isinstance(trimmed[0]["content"], str)):
        trimmed = trimmed[1:]
    return trimmed


class OpenAISession:
    def __init__(self, client):
        self.client = client
        self.history = []
        self.tools = [{"type": "function", "function": t} for t in TOOLS]

    async def say(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        while True:
            resp = await self.client.chat.completions.create(
                model=OPENAI_MODEL, max_completion_tokens=500,
                messages=[{"role": "system", "content": SYSTEM}] + self.history,
                tools=self.tools,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                self.history.append({"role": "assistant", "content": msg.content or ""})
                break
            self.history.append({
                "role": "assistant", "content": msg.content,
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name,
                                             "arguments": c.function.arguments}}
                               for c in msg.tool_calls],
            })
            for c in msg.tool_calls:
                args = json.loads(c.function.arguments or "{}")
                self.history.append({"role": "tool", "tool_call_id": c.id,
                                     "content": run_tool(c.function.name, args)})
        self.history = trim_history(self.history)
        return msg.content or ""


class AnthropicSession:
    def __init__(self, client):
        self.client = client
        self.history = []
        self.tools = [{"name": t["name"], "description": t["description"],
                       "input_schema": t["parameters"]} for t in TOOLS]

    async def say(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        while True:
            resp = await self.client.messages.create(
                model=ANTHROPIC_MODEL, max_tokens=500, system=SYSTEM,
                tools=self.tools, messages=self.history,
            )
            self.history.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                break
            results = [{"type": "tool_result", "tool_use_id": b.id,
                        "content": run_tool(b.name, b.input)}
                       for b in resp.content if b.type == "tool_use"]
            self.history.append({"role": "user", "content": results})
        self.history = trim_history(self.history)
        return "".join(b.text for b in resp.content if b.type == "text")


class GroqSession:
    def __init__(self, client):
        self.client = client
        self.history = []
        self.tools = [{"type": "function", "function": t} for t in TOOLS]

    async def say(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        while True:
            resp = await self.client.chat.completions.create(
                model=GROQ_MODEL, max_tokens=500,
                messages=[{"role": "system", "content": SYSTEM}] + self.history,
                tools=self.tools,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                self.history.append({"role": "assistant", "content": msg.content or ""})
                break
            self.history.append({
                "role": "assistant", "content": msg.content,
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name,
                                             "arguments": c.function.arguments}}
                               for c in msg.tool_calls],
            })
            for c in msg.tool_calls:
                args = json.loads(c.function.arguments or "{}")
                self.history.append({"role": "tool", "tool_call_id": c.id,
                                     "content": run_tool(c.function.name, args)})
        self.history = trim_history(self.history)
        return msg.content or ""


class Brain:
    def __init__(self):
        if PROVIDER == "groq":
            from groq import AsyncGroq
            self.client, self.session_cls = AsyncGroq(), GroqSession
        elif PROVIDER == "anthropic":
            from anthropic import AsyncAnthropic
            self.client, self.session_cls = AsyncAnthropic(), AnthropicSession
        elif PROVIDER == "openai":
            from openai import AsyncOpenAI
            self.client, self.session_cls = AsyncOpenAI(), OpenAISession
        else:
            raise ValueError("IGRIS_PROVIDER debe ser 'groq', 'openai' o 'anthropic'")

    def new_session(self):
        """Una conversación independiente (una por cada conexión)."""
        return self.session_cls(self.client)

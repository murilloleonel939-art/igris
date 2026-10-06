"""Cerebro de Igris: personalidad, herramientas y conversación.
Soporta múltiples proveedores con fallback automático: Groq, OpenAI, Anthropic, Local.
Lo usan tanto el servidor (EC2) como, más adelante, la Raspberry Pi (modo respaldo)."""
import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
from core import config
from core.settings_manager import get_settings

PROVIDER = config.get_active_provider()
TIMEZONE = config.TIMEZONE

SYSTEM = config.SYSTEM_PROMPT

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
    def __init__(self, client, model, provider_name="unknown", brain_ref=None, current_idx=0):
        self.client = client
        self.model = model
        self.provider_name = provider_name
        self.brain_ref = brain_ref
        self.history = []
        self.tools = [{"name": t["name"], "description": t["description"],
                       "input_schema": t["parameters"]} for t in TOOLS]
        self.current_provider_idx = current_idx  # Índice en cadena completa de proveedores

    async def say(self, text: str) -> str:
        print(f"🧠 [Brain] Iniciando say() para proveedor {self.provider_name} con texto: '{text[:100]}'")
        self.history.append({"role": "user", "content": text})
        while True:
            try:
                print(f"🔄 [Brain] Llamando a {self.provider_name}...")
                resp = await self.client.messages.create(
                    model=self.model, max_tokens=500, system=SYSTEM,
                    tools=self.tools, messages=self.history,
                )
                print(f"📨 [Brain] Respuesta recibida de {self.provider_name}: {type(resp)}")
                
                self.history.append({"role": "assistant", "content": resp.content})
                if resp.stop_reason != "tool_use":
                    break
                results = [{"type": "tool_result", "tool_use_id": b.id,
                            "content": run_tool(b.name, b.input)}
                           for b in resp.content if b.type == "tool_use"]
                self.history.append({"role": "user", "content": results})
            except Exception as e:
                print(f"❌ [Brain] Error en {self.provider_name}: {e}")
                import traceback
                print(f"📋 [Brain] Traceback: {traceback.format_exc()}")
                
                # Intenta el siguiente en la cadena de fallback
                if self.brain_ref:
                    result = self.brain_ref._get_next_fallback_provider(self.current_provider_idx)
                    if result[0] is not None:
                        provider_name, session_idx = result
                        print(f"↻ [Brain] Saltando a fallback: {provider_name}")
                        self.brain_ref._switch_provider(provider_name, session_idx, self)
                        continue
                raise
        self.history = trim_history(self.history)
        return "".join(b.text for b in resp.content if b.type == "text")


class LocalSession:
    """Sesión para modelos locales (Ollama, etc)."""
    def __init__(self, provider_name="unknown", brain_ref=None, current_idx=0):
        self.provider_name = provider_name
        self.brain_ref = brain_ref
        self.current_provider_idx = current_idx
        self.history = []
        self.tools = [{"type": "function", "function": t} for t in TOOLS]

    async def say(self, text: str) -> str:
        # Implementación futura para Ollama/modelos locales
        return f"Modo local no implementado aún. Proveedor actual: {PROVIDER}"


class OpenAICompatibleSession:
    """Sesión compatible con Groq, OpenAI, y otros que usan OpenAI SDK, con fallback automático."""
    def __init__(self, client, model, provider_name="unknown", brain_ref=None, current_idx=0):
        self.client = client
        self.model = model
        self.provider_name = provider_name
        self.brain_ref = brain_ref
        self.history = []
        self.tools = [{"type": "function", "function": t} for t in TOOLS]
        self.current_provider_idx = current_idx  # Índice en cadena completa de proveedores

    async def say(self, text: str) -> str:
        print(f"🧠 [Brain] Iniciando say() para proveedor {self.provider_name} con texto: '{text[:100]}'")
        self.history.append({"role": "user", "content": text})
        while True:
            try:
                print(f"🔄 [Brain] Llamando a {self.provider_name}...")
                resp = await self.client.chat.completions.create(
                    model=self.model, max_tokens=500,
                    messages=[{"role": "system", "content": SYSTEM}] + self.history,
                    tools=self.tools,
                )
                print(f"📨 [Brain] Respuesta recibida de {self.provider_name}: {type(resp)}")
                
                if resp is None:
                    print(f"⚠️ [Brain] Respuesta None de {self.provider_name}")
                    raise RuntimeError("Received None response from client")
                    
                if not hasattr(resp, 'choices'):
                    print(f"⚠️ [Brain] Respuesta sin atributo 'choices' de {self.provider_name}: {resp}")
                    raise RuntimeError("Response missing 'choices' attribute")
                    
                if resp.choices is None:
                    print(f"⚠️ [Brain] Respuesta con choices None de {self.provider_name}")
                    raise RuntimeError("Response choices is None")
                    
                if len(resp.choices) == 0:
                    print(f"⚠️ [Brain] Respuesta con choices vacío de {self.provider_name}")
                    raise RuntimeError("Response choices is empty")
                    
                msg = resp.choices[0].message
                print(f"📝 [Brain] Mensaje de {self.provider_name}: {type(msg)}")
                
                if msg is None:
                    print(f"⚠️ [Brain] Mensaje None de {self.provider_name}")
                    raise RuntimeError("Message is None")
                    
                if not hasattr(msg, 'tool_calls'):
                    print(f"⚠️ [Brain] Mensaje sin atributo 'tool_calls' de {self.provider_name}: {msg}")
                    # Treat as no tool calls
                    self.history.append({"role": "assistant", "content": msg.content or ""})
                    break
                    
                tool_calls = msg.tool_calls
                if tool_calls is None:
                    print(f"ℹ️ [Brain] Tool calls es None de {self.provider_name}, tratándolo como vacío")
                    tool_calls = []
                    
                if not tool_calls:  # Empty list or None (now handled as empty list)
                    self.history.append({"role": "assistant", "content": msg.content or ""})
                    break
                    
                self.history.append({
                    "role": "assistant", "content": msg.content,
                    "tool_calls": [{"id": c.id, "type": "function",
                                    "function": {"name": c.function.name,
                                                 "arguments": c.function.arguments}}
                                   for c in tool_calls],
                })
                
                for c in tool_calls:
                    if c is None:
                        print(f"⚠️ [Brain] Tool call None en {self.provider_name}")
                        continue
                        
                    if not hasattr(c, 'function') or c.function is None:
                        print(f"⚠️ [Brain] Tool call sin función en {self.provider_name}: {c}")
                        continue
                        
                    function_name = getattr(c.function, 'name', None)
                    if function_name is None:
                        print(f"⚠️ [Brain] Tool call sin nombre de función en {self.provider_name}: {c.function}")
                        continue
                        
                    arguments = getattr(c.function, 'arguments', None)
                    if arguments is None:
                        arguments = "{}"
                        
                    try:
                        args = json.loads(arguments)
                    except json.JSONDecodeError:
                        print(f"⚠️ [Brain] Error decodificando argumentos JSON: {arguments}")
                        args = {}
                        
                    print(f"🔧 [Brain] Ejecutando herramienta: {function_name} con args: {args}")
                    tool_result = run_tool(function_name, args)
                    print(f"✅ [Brain] Resultado de herramienta {function_name}: {tool_result}")
                    
                    self.history.append({"role": "tool", "tool_call_id": getattr(c, 'id', None),
                                         "content": tool_result})
                                     
            except Exception as e:
                print(f"❌ [Brain] Error en {self.provider_name}: {e}")
                import traceback
                print(f"📋 [Brain] Traceback: {traceback.format_exc()}")
                
                # Intenta el siguiente en la cadena de fallback
                if self.brain_ref:
                    result = self.brain_ref._get_next_fallback_provider(self.current_provider_idx)
                    if result[0] is not None:
                        provider_name, session_idx = result
                        print(f"↻ [Brain] Saltando a fallback: {provider_name}")
                        self.brain_ref._switch_provider(provider_name, session_idx, self)
                        continue
                raise
        self.history = trim_history(self.history)
        return msg.content or ""


class Brain:
    def __init__(self):
        self.reload_settings()
        self.clients = {}  # Cache de clientes por proveedor
        self._init_provider(self.primary_provider)
    def reload_settings(self):
        """Recarga la configuración de IA desde settings.json."""
        settings = get_settings()
        ai_config = settings.get_ai_config()
        self.primary_provider = ai_config.get("primary_provider", config.get_active_provider())
        self.fallback_chain = ai_config.get("fallback_chain", config.FALLBACK_CHAIN)
        # Ensure fallback_chain is a list
        if not isinstance(self.fallback_chain, list):
            self.fallback_chain = config.FALLBACK_CHAIN

    def _init_provider(self, provider_name):
        """Inicializa un cliente para un proveedor específico."""
        if provider_name in self.clients:
            return self.clients[provider_name]
        
        provider_config = config.get_provider_config(provider_name)
        if not provider_config["enabled"]:
            return None
        
        # Manejo especial para proveedores que necesitan base_url personalizada (como NVIDIA)
        if provider_name == "nemotron":
            from openai import AsyncOpenAI
            api_key = provider_config["api_key"]
            api_base = provider_config.get("api_base")
            # Si se proporciona una base_url personalizada, la usamos
            if api_base:
                self.clients[provider_name] = AsyncOpenAI(api_key=api_key, base_url=api_base)
            else:
                self.clients[provider_name] = AsyncOpenAI(api_key=api_key)
            return self.clients.get(provider_name)
        
        # Los proveedores existentes (Groq, OpenAI, Anthropic) permanecen igual
        elif provider_name == "groq":
            from groq import AsyncGroq
            self.clients[provider_name] = AsyncGroq(api_key=provider_config["api_key"])
        elif provider_name == "openai":
            from openai import AsyncOpenAI
            self.clients[provider_name] = AsyncOpenAI(api_key=provider_config["api_key"])
        elif provider_name == "anthropic":
            from anthropic import AsyncAnthropic
            self.clients[provider_name] = AsyncAnthropic(api_key=provider_config["api_key"])
        elif provider_name == "local":
            self.clients[provider_name] = None  # Local no necesita cliente de API
        
        return self.clients.get(provider_name)

    def _get_next_fallback_provider(self, current_idx):
        """Obtiene el siguiente proveedor en la cadena de fallback.
        Retorna (nombre_del_proveedor, indice_para_la_nueva_sesion) o (None, None)."""
        # current_idx es el índice en la cadena completa de proveedores intentados
        # cadena completa = [primary_provider] + fallback_chain
        # Si current_idx apunta a primary_provider (índice 0), el siguiente es fallback_chain[0]
        # Si current_idx apunta a fallback_chain[i], el siguiente es fallback_chain[i+1]
        # En general, el siguiente proveedor está en fallback_chain[current_idx] si existe
        if current_idx < len(self.fallback_chain):
            provider = self.fallback_chain[current_idx]
            if config.PROVIDERS_CONFIG[provider]["enabled"]:
                # El índice para la nueva sesión será current_idx + 1 en la cadena completa
                return provider, current_idx + 1
        return None, None

    def _switch_provider(self, provider_name, session_idx, session):
        """Cambia el proveedor en una sesión activa."""
        session.provider_name = provider_name
        session.client = self._init_provider(provider_name)
        session.model = config.get_provider_config(provider_name)["model"]
        session.current_provider_idx = session_idx

    def new_session(self):
        """Una conversación independiente con fallback automático según cadena."""
        if self.primary_provider == "local":
            current_idx = self.fallback_chain.index(self.primary_provider)
            return LocalSession(provider_name=self.primary_provider,
                              brain_ref=self,
                              current_idx=current_idx)
        elif self.primary_provider == "anthropic":
            client = self._init_provider(self.primary_provider)
            if client is None:
                raise RuntimeError(f"No se pudo inicializar el proveedor {self.primary_provider}")
            provider_config = config.get_provider_config(self.primary_provider)
            current_idx = self.fallback_chain.index(self.primary_provider)
            return AnthropicSession(client, provider_config["model"],
                                  provider_name=self.primary_provider,
                                  brain_ref=self,
                                  current_idx=current_idx)
        else:
            # Groq, OpenAI (compatible con OpenAI SDK)
            client = self._init_provider(self.primary_provider)
            if client is None:
                raise RuntimeError(f"No se pudo inicializar el proveedor {self.primary_provider}")
            provider_config = config.get_provider_config(self.primary_provider)
            current_idx = self.fallback_chain.index(self.primary_provider)
            return OpenAICompatibleSession(
                client, 
                provider_config["model"],
                provider_name=self.primary_provider,
                brain_ref=self,
                current_idx=current_idx
            )

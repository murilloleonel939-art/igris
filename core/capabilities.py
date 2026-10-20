"""Funciones de Igris y permisos por usuario.

Cada herramienta pertenece a UNA función ("feature"). Un usuario solo puede
ejecutar las herramientas de las funciones que tiene habilitadas.

El control se hace en DOS sitios, y los dos importan:

  1. brain.py no le ofrece al modelo las herramientas no permitidas (así ni
     siquiera intenta usarlas ni se las menciona al usuario).
  2. run_tool() las rechaza aunque lleguen igualmente (por ejemplo, si el
     modelo alucina una llamada o si un mensaje de correo intenta provocarla).

El segundo punto es el que da la garantía real: el prompt es una sugerencia para
el modelo, pero el permiso se comprueba en el servidor.

Sin usuario (panel del administrador, que entra con la clave única) capabilities
es None y todo está permitido: el administrador conserva el comportamiento
anterior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Optional

# ============= FUNCIONES =============

# Orden en el que se muestran en el panel.
FEATURE_ORDER = (
    "time",
    "weather",
    "documents",
    "email",
    "email_write",
    "calendar",
    "calendar_write",
    "youtube",
    "spotify",
    "notes",
    "reminders",
    "tuya",
    "device",
)

# Funciones que están activas de fábrica. Son inofensivas: no tocan datos de
# nadie. Todo lo que lee datos personales (correo, calendario) o escribe algo
# (notas, recordatorios) lo tiene que abrir el administrador a mano.
DEFAULT_FEATURES: FrozenSet[str] = frozenset({"time", "weather", "documents"})


@dataclass(frozen=True)
class Feature:
    key: str            # identificador interno (columna de la BD)
    column: str         # columna de la tabla users
    label: str          # nombre para el panel
    description: str    # explicación para el panel
    requires_google: bool = False   # exige que el usuario conecte su cuenta Google


FEATURES: dict[str, Feature] = {
    "time": Feature(
        key="time",
        column="can_use_time",
        label="Hora y fecha",
        description="Saber la hora, el día y la fecha.",
    ),
    "weather": Feature(
        key="weather",
        column="can_use_weather",
        label="Clima",
        description="Consultar el clima y el pronóstico de una ciudad.",
    ),
    "documents": Feature(
        key="documents",
        column="can_use_documents",
        label="Documentos en el PC",
        description=(
            "Crear archivos Word, Excel, PowerPoint, texto y CSV directamente en la "
            "carpeta Documentos del computador del usuario mediante el agente Windows. "
            "El servidor no guarda copias."
        ),
    ),
    "email": Feature(
        key="email",
        column="can_use_email",
        label="Leer correo (Gmail)",
        description="Ver la bandeja de entrada y leer correos. Solo lectura.",
        requires_google=True,
    ),
    "email_write": Feature(
        key="email_write",
        column="can_use_email_write",
        label="Enviar y eliminar correos (Gmail)",
        description=(
            "Redactar y enviar correos, y mover correos a la papelera. "
            "Igris siempre pide confirmación antes de enviar."
        ),
        requires_google=True,
    ),
    "calendar": Feature(
        key="calendar",
        column="can_use_calendar",
        label="Ver calendario (Google)",
        description="Consultar la agenda: qué tiene hoy, mañana o esta semana.",
        requires_google=True,
    ),
    "calendar_write": Feature(
        key="calendar_write",
        column="can_use_calendar_write",
        label="Agendar, mover y eliminar eventos",
        description=(
            "Crear eventos en su calendario, reagendarlos y eliminarlos. "
            "Igris siempre pide confirmación antes de crear o mover, y no invita a nadie."
        ),
        requires_google=True,
    ),
    "youtube": Feature(
        key="youtube",
        column="can_use_youtube",
        label="Administrar listas de YouTube",
        description="Consultar, crear y modificar listas de reproducción y añadir videos.",
        requires_google=True,
    ),
    "spotify": Feature(
        key="spotify",
        column="can_use_spotify",
        label="Spotify (API)",
        description="Buscar música, administrar playlists y controlar la reproducción con tu cuenta de Spotify.",
    ),
    "notes": Feature(
        key="notes",
        column="can_use_notes",
        label="Notas",
        description="Anotar, consultar y borrar sus propias notas.",
    ),
    "reminders": Feature(
        key="reminders",
        column="can_use_reminders",
        label="Recordatorios",
        description="Programar avisos; le llegan por Telegram si lo tiene vinculado.",
    ),
    "device": Feature(
        key="device",
        column="can_use_device",
        label="Control del computador local",
        description="Controlar Chrome, Edge, Spotify, Steam, Explorador, Word, Excel, archivos, multimedia, volumen y programas autorizados.",
    ),
    "tuya": Feature(
        key="tuya",
        column="can_use_tuya",
        label="Casa inteligente (Smart Life)",
        description="Consultar y controlar los dispositivos vinculados a Tuya Cloud.",
    ),
}

# ============= HERRAMIENTA -> FUNCIÓN =============

TOOL_FEATURES: dict[str, str] = {
    "get_time": "time",
    "get_weather": "weather",
    "create_document": "documents",
    "list_emails": "email",
    "read_email": "email",
    "propose_email": "email_write",
    "confirm_email": "email_write",
    "delete_email": "email_write",
    "list_events": "calendar",
    "propose_event": "calendar_write",
    "confirm_event": "calendar_write",
    "delete_event": "calendar_write",
    "propose_reschedule": "calendar_write",
    "confirm_reschedule": "calendar_write",
    "list_youtube_playlists": "youtube",
    "create_youtube_playlist": "youtube",
    "add_video_to_youtube_playlist": "youtube",
    "remove_video_from_youtube_playlist": "youtube",
    "search_spotify_api": "spotify",
    "list_spotify_playlists": "spotify",
    "create_spotify_playlist": "spotify",
    "add_tracks_to_spotify_playlist": "spotify",
    "remove_tracks_from_spotify_playlist": "spotify",
    "start_spotify_playback": "spotify",
    "add_note": "notes",
    "list_notes": "notes",
    "search_notes": "notes",
    "delete_note": "notes",
    "create_reminder": "reminders",
    "list_reminders": "reminders",
    "delete_reminder": "reminders",
    "list_tuya_devices": "tuya",
    "get_tuya_device_status": "tuya",
    "control_tuya_device": "tuya",
    "open_chrome": "device",
    "search_youtube": "device",
    "capture_screen": "device",
    "list_windows": "device",
    "focus_window": "device",
    "click_screen": "device",
    "press_key": "device",
    "media_control": "device",
    "volume_control": "device",
    "launch_program": "device",
    "search_files": "device",
    "open_file": "device",
    "type_in_office": "device",
    "search_spotify": "device",
    "search_steam": "device",
    "navigate_edge": "device",
    "system_power": "device",
}


# ============= CAPACIDADES DE UNA SESIÓN =============

@dataclass
class Capabilities:
    """Qué puede hacer la conversación actual.

    `user_id` es None en el panel del administrador. `features` es el conjunto de
    funciones habilitadas; `all_features=False` junto con un conjunto vacío
    significa "ninguna", que es distinto de None ("todas").
    """

    user_id: Optional[int] = None
    features: FrozenSet[str] = field(default_factory=frozenset)

    def has(self, feature: str) -> bool:
        return feature in self.features

    def allows_tool(self, tool_name: str) -> bool:
        feature = TOOL_FEATURES.get(tool_name)
        # Una herramienta sin función declarada se permite: así, añadir una
        # herramienta nueva sin tocar este archivo no la bloquea por accidente.
        if feature is None:
            return True
        return self.has(feature)


def capabilities_from_user(user) -> Capabilities:
    """Construye las capacidades a partir de un usuario de la base de datos."""
    enabled = {
        key for key, feat in FEATURES.items()
        if bool(getattr(user, feat.column, False))
    }
    return Capabilities(user_id=getattr(user, "id", None), features=frozenset(enabled))


def admin_capabilities(user_id: Optional[int] = None) -> Capabilities:
    """Todas las funciones, conservando el usuario si el admin está autenticado."""
    return Capabilities(user_id=user_id, features=frozenset(FEATURES))


def tools_for(caps: Optional[Capabilities]) -> list:
    """Esquemas de herramientas visibles para estas capacidades.

    SIN capacidades (None) se devuelven todas: es el caso del administrador y de
    cualquier llamada interna que no pase por un usuario.
    """
    from core.tools import TOOLS

    if caps is None:
        return list(TOOLS)
    return [t for t in TOOLS if caps.allows_tool(t["function"]["name"])]


def denial_message(tool_name: str, caps: Optional[Capabilities]) -> str:
    """Texto que recibe el modelo cuando intenta usar algo no permitido.

    Se le dice qué función falta para que pueda explicárselo al usuario con
    naturalidad, sin inventar que hubo un error técnico.
    """
    feature = TOOL_FEATURES.get(tool_name)
    if feature is None:
        return "Esa herramienta no está disponible."
    label = FEATURES[feature].label
    if caps is None or caps.user_id is None:
        return f"No tienes habilitada la función «{label}»."
    return (
        f"Este usuario no tiene habilitada la función «{label}». "
        f"Dile que se la pida al administrador y no intentes usar otra herramienta para conseguirlo."
    )

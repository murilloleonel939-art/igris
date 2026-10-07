"""Herramienta de hora y fecha para IGRIS (por defecto, hora de Colombia)."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "America/Bogota"  # UTC-5, Colombia no tiene horario de verano

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _format(now: datetime) -> dict:
    hora12 = now.hour % 12 or 12
    sufijo = "a. m." if now.hour < 12 else "p. m."
    return {
        "fecha": f"{DIAS[now.weekday()]} {now.day} de {MESES[now.month - 1]} de {now.year}",
        "hora": f"{hora12}:{now.minute:02d} {sufijo}",
    }


def now_context() -> str:
    """Línea para inyectar en el system prompt en cada petición."""
    now = datetime.now(ZoneInfo(DEFAULT_TZ))
    f = _format(now)
    return f"Fecha y hora actual en Colombia: {f['fecha']}, {f['hora']}"


async def get_time(timezone: str = DEFAULT_TZ) -> dict:
    """Hora y fecha actuales. Por defecto Colombia; acepta otra zona IANA."""
    try:
        tz = ZoneInfo(timezone or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return {"error": f"Zona horaria desconocida: {timezone}"}
    now = datetime.now(tz)
    return {"zona_horaria": str(tz), **_format(now)}

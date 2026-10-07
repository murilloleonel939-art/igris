"""Herramienta de clima para IGRIS usando Open-Meteo (gratis, sin API key)."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Ciudad por defecto cuando el usuario no menciona ninguna
DEFAULT_PLACE = {"nombre": "Cali", "pais": "Colombia", "lat": 3.4516, "lon": -76.5320}

# Códigos WMO de Open-Meteo -> descripción en español
WMO = {
    0: "despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "niebla",
    48: "niebla con escarcha",
    51: "llovizna ligera",
    53: "llovizna moderada",
    55: "llovizna intensa",
    56: "llovizna helada ligera",
    57: "llovizna helada intensa",
    61: "lluvia ligera",
    63: "lluvia moderada",
    65: "lluvia fuerte",
    66: "lluvia helada ligera",
    67: "lluvia helada fuerte",
    71: "nevada ligera",
    73: "nevada moderada",
    75: "nevada fuerte",
    77: "granizo fino",
    80: "chubascos ligeros",
    81: "chubascos moderados",
    82: "chubascos violentos",
    85: "chubascos de nieve ligeros",
    86: "chubascos de nieve fuertes",
    95: "tormenta eléctrica",
    96: "tormenta con granizo ligero",
    99: "tormenta con granizo fuerte",
}


async def _geocode(client: httpx.AsyncClient, city: str) -> Optional[dict]:
    r = await client.get(GEO_URL, params={"name": city, "count": 1, "language": "es"})
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    p = results[0]
    return {
        "nombre": p.get("name", city),
        "pais": p.get("country", ""),
        "lat": p["latitude"],
        "lon": p["longitude"],
    }


async def get_weather(city: Optional[str] = None) -> dict:
    """Clima actual y pronóstico de hoy. Sin ciudad, usa la ciudad por defecto."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            place = DEFAULT_PLACE
            if city and city.strip():
                place = await _geocode(client, city.strip())
                if place is None:
                    return {"error": f"No encontré la ciudad: {city}"}

            r = await client.get(
                FORECAST_URL,
                params={
                    "latitude": place["lat"],
                    "longitude": place["lon"],
                    "current": (
                        "temperature_2m,apparent_temperature,relative_humidity_2m,"
                        "precipitation,weather_code,wind_speed_10m"
                    ),
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 1,
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.error(f"Error consultando el clima: {e}")
        return {"error": "No pude consultar el servicio del clima en este momento."}

    cur = data.get("current", {})
    day = data.get("daily", {})

    def first(key):
        values = day.get(key) or [None]
        return values[0]

    return {
        "ciudad": place["nombre"],
        "pais": place["pais"],
        "condicion": WMO.get(cur.get("weather_code"), "sin datos"),
        "temperatura_c": cur.get("temperature_2m"),
        "sensacion_termica_c": cur.get("apparent_temperature"),
        "humedad_pct": cur.get("relative_humidity_2m"),
        "viento_kmh": cur.get("wind_speed_10m"),
        "precipitacion_mm": cur.get("precipitation"),
        "hoy_maxima_c": first("temperature_2m_max"),
        "hoy_minima_c": first("temperature_2m_min"),
        "hoy_prob_lluvia_pct": first("precipitation_probability_max"),
    }

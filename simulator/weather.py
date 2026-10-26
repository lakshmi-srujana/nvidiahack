"""
SkyWarden Python Open-Meteo Live Weather Service
Fetches real-time ambient wind speed, direction, temperature, and conditions.
Includes zero-dependency HTTP client with safe offline fallback.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any


def decode_wmo_code(code: int) -> str:
    if code == 0:
        return "CLEAR_SKY"
    if code in (1, 2):
        return "PARTLY_CLOUDY"
    if code == 3:
        return "OVERCAST"
    if code in (45, 48):
        return "FOG"
    if 51 <= code <= 55:
        return "LIGHT_DRIZZLE"
    if 61 <= code <= 65:
        return "RAIN"
    if 71 <= code <= 77:
        return "SNOW"
    if 80 <= code <= 82:
        return "RAIN_SHOWERS"
    if 95 <= code <= 99:
        return "THUNDERSTORM"
    return "MODERATE_CLOUDS"


def fetch_open_meteo_weather(
    latitude: float = 37.4220,
    longitude: float = -122.0845,
    timeout_s: float = 3.0,
) -> Dict[str, Any]:
    """
    Fetches real-time ambient weather from Open-Meteo API.
    Falls back safely to local meteorological baseline if offline or timeout.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude:.4f}&longitude={longitude:.4f}"
        "&current=temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code"
        "&wind_speed_unit=ms"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SkyWarden-UAS/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                current = data.get("current", {})
                wind_speed = current.get("wind_speed_10m", 4.5)
                return {
                    "wind_speed_mps": float(wind_speed),
                    "wind_direction_deg": float(current.get("wind_direction_10m", 240.0)),
                    "wind_gusts_mps": float(current.get("wind_gusts_10m", wind_speed + 2.0)),
                    "temperature_c": float(current.get("temperature_2m", 18.0)),
                    "weather_condition": decode_wmo_code(int(current.get("weather_code", 1))),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "source": "OPEN_METEO_API",
                }
    except Exception:
        # Resilient offline fallback
        pass

    return {
        "wind_speed_mps": 4.8,
        "wind_direction_deg": 240.0,
        "wind_gusts_mps": 7.2,
        "temperature_c": 19.0,
        "weather_condition": "PARTLY_CLOUDY",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source": "OFFLINE_FALLBACK",
    }

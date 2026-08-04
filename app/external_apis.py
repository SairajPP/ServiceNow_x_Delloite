"""
Weather (OpenWeatherMap) + AQI (WAQI) lookups.
integration-contract.md Section 2.5 and 2.6.

Both are best-effort: if either fails we degrade gracefully per the
"Weather / AQI API Down" failure mode in Section 6 — the pipeline keeps
going on whatever signals it has, and env_snapshot.data_source records
what actually came back.
"""
from typing import Optional

import httpx

from app.config import settings
from app.logging_utils import get_logger
from app.models import EnvironmentalData

logger = get_logger(__name__)

_WIND_DEG_TO_CARDINAL = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def _deg_to_cardinal(deg: Optional[float]) -> Optional[str]:
    if deg is None:
        return None
    idx = round(deg / 22.5) % 16
    return _WIND_DEG_TO_CARDINAL[idx]


def _aqi_category(aqi: int) -> str:
    if aqi <= 50:
        return "good"
    if aqi <= 100:
        return "moderate"
    if aqi <= 150:
        return "unhealthy_sensitive"
    if aqi <= 200:
        return "unhealthy"
    if aqi <= 300:
        return "very_unhealthy"
    return "hazardous"


async def fetch_weather(lat: float, lng: float) -> Optional[dict]:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lng, "appid": settings.weather_api_key}
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.error("Weather API failed: %s", exc)
        return None


async def fetch_aqi(lat: float, lng: float) -> Optional[dict]:
    url = f"https://api.waqi.info/feed/geo:{lat};{lng}/"
    params = {"token": settings.aqi_api_key}
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()
            if body.get("status") != "ok":
                logger.error("AQI API returned non-ok status: %s", body)
                return None
            return body
    except httpx.HTTPError as exc:
        logger.error("AQI API failed: %s", exc)
        return None


async def fetch_environmental_data(lat: float, lng: float) -> EnvironmentalData:
    """Fetch weather + AQI in parallel-ish (called concurrently by the caller)
    and fold into one EnvironmentalData record, tracking data_source honestly."""
    weather = await fetch_weather(lat, lng)
    aqi_resp = await fetch_aqi(lat, lng)

    if weather is None and aqi_resp is None:
        return EnvironmentalData(data_source="error")

    data = EnvironmentalData(
        data_source="success" if (weather and aqi_resp) else "partial",
    )

    if weather:
        data.temperature = round(weather["main"]["temp"] - 273.15, 1)  # Kelvin -> Celsius
        data.humidity = weather["main"].get("humidity")
        data.weather_condition = weather.get("weather", [{}])[0].get("description")
        wind = weather.get("wind", {})
        # OpenWeatherMap wind speed is m/s -> convert to km/h
        data.wind_speed = round(wind.get("speed", 0) * 3.6, 1)
        data.wind_direction = _deg_to_cardinal(wind.get("deg"))

    if aqi_resp:
        aqi_value = aqi_resp["data"]["aqi"]
        data.aqi_value = aqi_value
        data.aqi_category = _aqi_category(aqi_value)
        data.primary_pollutant = aqi_resp["data"].get("dominentpol")

    return data

"""Weather ingestion using Open-Meteo."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Optional

import httpx

from app.config import settings
from app.models.weather import TimeWindow, WeatherSnapshot

logger = logging.getLogger("sentinelai.ingestors.weather")


def _parse_timestamp(ts: str | None) -> datetime:
    if ts is None:
        return datetime.utcnow()
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def _find_hourly_value(times: list[str] | None, target: str | None, values: list | None):
    if not times or not values:
        return None
    try:
        if target:
            idx = times.index(target)
            return values[idx]
    except ValueError:
        logger.debug("Target time %s not found in hourly data", target)
    return values[0] if values else None


class WeatherIngestor:
    """Fetch mission-relevant weather data from Open-Meteo."""

    def __init__(self, *, base_url: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.weather_base_url
        self.timeout = timeout or settings.weather_timeout

    async def get_weather(
        self, lat: float, lon: float, time_window: Optional[TimeWindow] = None
    ) -> WeatherSnapshot:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "hourly": "visibility,precipitation_probability,precipitation,cloudcover",
            "timezone": "UTC",
        }
        if time_window and time_window.start:
            params["start_date"] = time_window.start.date().isoformat()
        if time_window and time_window.end:
            params["end_date"] = time_window.end.date().isoformat()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("Weather request timed out: %s", exc)
            raise RuntimeError("Weather service timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Weather service returned error: status=%s body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            raise RuntimeError("Weather service error") from exc
        except httpx.RequestError as exc:
            logger.error("Weather request failed: %s", exc)
            raise RuntimeError("Weather request failed") from exc

        payload = response.json()
        current = payload.get("current_weather", {})
        hourly = payload.get("hourly", {})
        target_time = current.get("time")

        times = hourly.get("time")
        precipitation_probability = _find_hourly_value(
            times, target_time, hourly.get("precipitation_probability")
        )
        precipitation = _find_hourly_value(times, target_time, hourly.get("precipitation"))
        visibility_m = _find_hourly_value(times, target_time, hourly.get("visibility"))
        cloud_cover = _find_hourly_value(times, target_time, hourly.get("cloudcover"))

        snapshot = WeatherSnapshot(
            latitude=lat,
            longitude=lon,
            as_of=_parse_timestamp(target_time),
            temperature_c=current.get("temperature"),
            wind_speed_mps=current.get("windspeed"),
            wind_direction_deg=current.get("winddirection"),
            precipitation_probability_pct=precipitation_probability,
            precipitation_mm=precipitation,
            visibility_km=(visibility_m / 1000) if visibility_m is not None else None,
            cloud_cover_pct=cloud_cover,
            condition=str(current.get("weathercode")) if current.get("weathercode") is not None else None,
        )
        logger.debug("Weather snapshot ingested: %s", snapshot)
        return snapshot


__all__ = ["WeatherIngestor"]

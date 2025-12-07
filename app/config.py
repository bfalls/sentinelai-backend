"""Configuration settings for SentinelAI backend."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application configuration loaded from environment variables."""

    sentinellai_env: str = os.getenv("SENTINELAI_ENV", "local")
    log_level: str = os.getenv("SENTINELAI_LOG_LEVEL", "INFO")

    # OpenAI / LLM settings
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_timeout: float = float(os.getenv("OPENAI_TIMEOUT", "30.0"))
    debug_ai_endpoints: bool = os.getenv("DEBUG_AI_ENDPOINTS", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    # Weather ingestion
    enable_weather_ingestor: bool = os.getenv("ENABLE_WEATHER_INGESTOR", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    weather_provider: str = os.getenv("WEATHER_PROVIDER", "open-meteo")
    weather_base_url: str = os.getenv(
        "WEATHER_BASE_URL", "https://api.open-meteo.com/v1/forecast"
    )
    weather_timeout: float = float(os.getenv("WEATHER_TIMEOUT", "10.0"))

    # ADS-B ingestion
    enable_adsb_ingestor: bool = os.getenv("ENABLE_ADSB_INGESTOR", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    adsb_base_url: str = os.getenv(
        "ADSB_BASE_URL",
        "https://opensky-network.org/api/states/all",
    )
    adsb_timeout: float = float(os.getenv("ADSB_TIMEOUT", "10.0"))
    adsb_default_radius_nm: float = float(os.getenv("ADSB_DEFAULT_RADIUS_NM", "25.0"))

    # APRS ingestion
    aprs_enabled: bool = os.getenv("APRS_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    aprs_host: str = os.getenv("APRS_HOST", "noam.aprs2.net")
    aprs_port: int = int(os.getenv("APRS_PORT", "14580"))
    aprs_callsign: str | None = os.getenv("APRS_CALLSIGN")
    aprs_passcode: str | None = os.getenv("APRS_PASSCODE")
    aprs_filter_center_lat: float | None = (
        float(os.getenv("APRS_FILTER_CENTER_LAT"))
        if os.getenv("APRS_FILTER_CENTER_LAT")
        else None
    )
    aprs_filter_center_lon: float | None = (
        float(os.getenv("APRS_FILTER_CENTER_LON"))
        if os.getenv("APRS_FILTER_CENTER_LON")
        else None
    )
    aprs_filter_radius_km: float | None = (
        float(os.getenv("APRS_FILTER_RADIUS_KM"))
        if os.getenv("APRS_FILTER_RADIUS_KM")
        else None
    )
    aprs_filter: str | None = os.getenv("APRS_FILTER")

    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")


settings = Settings()

__all__ = ["settings", "Settings"]

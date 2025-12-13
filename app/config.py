"""Configuration settings for SentinelAI backend."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger("sentinelai.config")

# Shared SSM client for configuration reads. Default to a region so imports do
# not fail in environments without AWS configuration (e.g. CI test runners).
_ssm_client = boto3.client(
    "ssm",
    region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
)


def _get_bool(env_var: str, default: bool = False) -> bool:
    """Parse an environment variable into a boolean with a default."""

    value = os.getenv(env_var)
    if value is None:
        return default

    return value.lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_openai_api_key() -> str:
    """Fetch the OpenAI API key from AWS SSM Parameter Store.

    The value is cached in-memory to avoid repeated SSM calls. Any failure to
    retrieve the key results in a runtime error so the application fails fast.
    """

    try:
        response = _ssm_client.get_parameter(
            Name="/sentinel/openai/api_key", WithDecryption=True
        )
        value = response.get("Parameter", {}).get("Value")
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - AWS error passthrough
        logger.error("Failed to load OpenAI API key from SSM: %s", exc)
        raise RuntimeError("Unable to load OpenAI API key from SSM") from exc

    if not value:
        logger.error("Received empty OpenAI API key from SSM")
        raise RuntimeError("OpenAI API key not configured in SSM")

    return value


@lru_cache(maxsize=1)
def get_api_key_pepper() -> str:
    """Fetch the API key pepper from AWS SSM Parameter Store."""

    try:
        response = _ssm_client.get_parameter(
            Name="/sentinel/api_key_pepper", WithDecryption=True
        )
        value = response.get("Parameter", {}).get("Value")
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - AWS error passthrough
        logger.error("Failed to load API key pepper from SSM: %s", exc)
        raise RuntimeError("Unable to load API key pepper from SSM") from exc

    if not value:
        logger.error("Received empty API key pepper from SSM")
        raise RuntimeError("API key pepper not configured in SSM")

    return value


@dataclass
class Settings:
    """Application configuration loaded from environment variables."""

    sentinellai_env: str = os.getenv("SENTINELAI_ENV", "local")
    log_level: str = os.getenv("SENTINELAI_LOG_LEVEL", "INFO")
    retention_days: int = int(os.getenv("SENTINELAI_RETENTION_DAYS", "7"))

    # OpenAI / LLM settings
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_timeout: float = float(os.getenv("OPENAI_TIMEOUT", "30.0"))
    openai_api_key: str = ""
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
    _aprs_lat = os.getenv("APRS_FILTER_CENTER_LAT")
    aprs_filter_center_lat: float | None = float(_aprs_lat) if _aprs_lat else None # this pattern avoids Pylance (reportArgumentType) errors
    # aprs_filter_center_lat: float | None = (
    #     float(os.getenv("APRS_FILTER_CENTER_LAT"))
    #     if os.getenv("APRS_FILTER_CENTER_LAT")
    #     else None
    # )
    _aprs_lon = os.getenv("APRS_FILTER_CENTER_LON")
    aprs_filter_center_lon: float | None = float(_aprs_lon) if _aprs_lon else None
    # aprs_filter_center_lon: float | None = (
    #     float(os.getenv("APRS_FILTER_CENTER_LON"))
    #     if os.getenv("APRS_FILTER_CENTER_LON")
    #     else None
    # )
    _aprs_radius = os.getenv("APRS_FILTER_RADIUS_KM")
    aprs_filter_radius_km: float | None = float(_aprs_radius) if _aprs_radius else None
    # aprs_filter_radius_km: float | None = (
    #     float(os.getenv("APRS_FILTER_RADIUS_KM"))
    #     if os.getenv("APRS_FILTER_RADIUS_KM")
    #     else None
    # )
    aprs_filter: str | None = os.getenv("APRS_FILTER")

    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")

    # API key authentication
    api_key_pepper: str = ""
    require_api_key: bool = _get_bool(
        "REQUIRE_API_KEY",
        default=os.getenv("SENTINELAI_ENV", "local").lower()
        in {"prod", "production"},
    )


settings = Settings()

# Populate the API key lazily so tests can override behavior via env
try:
    settings.openai_api_key = get_openai_api_key()
except RuntimeError:
    logger.warning("OpenAI API key not available at import time")

try:
    settings.api_key_pepper = get_api_key_pepper()
except RuntimeError:
    logger.warning("API key pepper not available at import time")

__all__ = ["settings", "Settings", "get_openai_api_key", "get_api_key_pepper"]

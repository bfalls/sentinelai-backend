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


settings = Settings()

__all__ = ["settings", "Settings"]

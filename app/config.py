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


settings = Settings()

__all__ = ["settings", "Settings"]

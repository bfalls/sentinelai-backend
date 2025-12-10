"""Thin OpenAI client wrapper for mission analysis calls."""

from __future__ import annotations

import json
import logging
from typing import Any

try:  # pragma: no cover - import guard for environments without OpenAI installed
    from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
except ImportError:  # pragma: no cover - handled at runtime
    APIError = APITimeoutError = AsyncOpenAI = RateLimitError = None  # type: ignore

from app.config import settings

logger = logging.getLogger("sentinelai.openai")

OPENAI_AVAILABLE = AsyncOpenAI is not None

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Return a singleton AsyncOpenAI client configured from settings."""

    global _client
    if AsyncOpenAI is None:  # type: ignore[truthy-bool]
        raise RuntimeError("OpenAI client library is not installed")

    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError("OpenAI API key not configured")
        _client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout)
        logger.info("Initialized OpenAI client for model %s", settings.openai_model)
    return _client


async def analyze_mission_context(prompt: str, *, system_message: str | None = None) -> str:
    """Send a mission analysis prompt to OpenAI and return the text response."""

    if not OPENAI_AVAILABLE:
        raise RuntimeError("OpenAI client library is not installed")
    
    messages: list[dict[str, Any]] = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.2,
            max_tokens=400,
        )
        choice = response.choices[0].message
        return choice.content or ""
    except (APITimeoutError, RateLimitError, APIError) as exc:
        logger.error("OpenAI API error: %s", exc)
        raise RuntimeError("AI service temporarily unavailable") from exc
    except Exception as exc:  # pragma: no cover - safeguard
        logger.exception("Unexpected OpenAI failure")
        raise RuntimeError("AI service unavailable") from exc


async def analyze_mission_with_intent_single_call(
    *, model: str, system_message: str, classification_payload: dict[str, Any]
) -> dict[str, Any]:
    """Classify mission intent and generate analysis in a single OpenAI call."""

    if not OPENAI_AVAILABLE:
        raise RuntimeError("OpenAI client library is not installed")

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": json.dumps(classification_payload)},
    ]

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=600,
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except (APITimeoutError, RateLimitError, APIError) as exc:
        logger.error("OpenAI API error: %s", exc)
        raise RuntimeError("AI service temporarily unavailable") from exc
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode OpenAI response as JSON: %s", exc)
        raise RuntimeError("AI response format invalid") from exc
    except Exception as exc:  # pragma: no cover - safeguard
        logger.exception("Unexpected OpenAI failure")
        raise RuntimeError("AI service unavailable") from exc


__all__ = [
    "analyze_mission_context",
    "analyze_mission_with_intent_single_call",
    "get_client",
]

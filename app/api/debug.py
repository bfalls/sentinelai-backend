"""Debug endpoints for AI connectivity checks."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.services import analyze_mission_context
from app.security import require_api_key

router = APIRouter(
    prefix="/debug", tags=["debug"], dependencies=[Depends(require_api_key)]
)

logger = logging.getLogger("sentinelai.debug")


@router.get("/ai-test", summary="Ping the AI backend")
async def ai_test() -> dict[str, str]:
    """Send a lightweight prompt to OpenAI to verify connectivity."""

    if not settings.debug_ai_endpoints:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        response = await analyze_mission_context(
            "Reply with 'pong' to confirm AI connectivity.",
            system_message="You are a connectivity probe for SentinelAI.",
        )
        return {"response": response}
    except RuntimeError as exc:
        logger.error("AI test failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable",
        )

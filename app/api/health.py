"""Health check endpoint."""

from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/healthz", summary="Health check")
def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok", "env": settings.sentinellai_env}

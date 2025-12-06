"""API routers for SentinelAI backend."""

from fastapi import APIRouter

from app.config import settings

from .analysis import router as analysis_router
from .events import router as events_router
from .health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(events_router)
api_router.include_router(analysis_router)

if settings.debug_ai_endpoints:
    from .debug import router as debug_router

    api_router.include_router(debug_router)

__all__ = ["api_router"]

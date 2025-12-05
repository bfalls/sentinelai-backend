"""API routers for SentinelAI backend."""

from fastapi import APIRouter

from .analysis import router as analysis_router
from .events import router as events_router
from .health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(events_router)
api_router.include_router(analysis_router)

__all__ = ["api_router"]

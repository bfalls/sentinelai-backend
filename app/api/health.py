"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz", summary="Health check")
def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}

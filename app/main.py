"""SentinelAI FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api import api_router

app = FastAPI(title="SentinelAI Backend")

app.include_router(api_router)


@app.get("/", summary="Root")
def read_root() -> dict[str, str]:
    """Basic root endpoint for quick verification."""
    return {"message": "SentinelAI backend is running"}

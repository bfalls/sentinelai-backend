"""SentinelAI FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI, Request

from app.api import api_router
from app.db import init_db

LOG_LEVEL = os.getenv("SENTINELAI_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
logger = logging.getLogger("sentinelai")

app = FastAPI(title="SentinelAI Backend")


@app.on_event("startup")
def on_startup() -> None:
    """Initialize application resources."""

    init_db()
    logger.info("Database initialized")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log basic request information for observability."""

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "HTTP %s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(api_router)


@app.get("/", summary="Root")
def read_root() -> dict[str, str]:
    """Basic root endpoint for quick verification."""

    return {"message": "SentinelAI backend is running"}

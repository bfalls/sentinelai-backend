from __future__ import annotations

import asyncio
import contextlib
import logging
import time

import httpx
from fastapi import FastAPI, Request

from app.api import api_router
from app.config import settings
from app.db import init_db
from app.ingestors import APRSIngestor, build_aprs_config

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("sentinelai")

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""

    # ----- Startup logic (previously on_startup) -----
    init_db()
    logger.info("Database initialized")

    if settings.aprs_enabled:
        if not settings.aprs_callsign or not settings.aprs_passcode:
            logger.warning(
                "APRS ingestion enabled but credentials are missing; skipping startup"
            )
        else:
            app.state.aprs_client = httpx.AsyncClient(
                base_url=settings.api_base_url,
                timeout=15,
            )
            aprs_config = build_aprs_config(
                host=settings.aprs_host,
                port=settings.aprs_port,
                callsign=settings.aprs_callsign,
                passcode=settings.aprs_passcode,
                aprs_filter=settings.aprs_filter,
                filter_center_lat=settings.aprs_filter_center_lat,
                filter_center_lon=settings.aprs_filter_center_lon,
                filter_radius_km=settings.aprs_filter_radius_km,
            )
            ingestor = APRSIngestor(
                config=aprs_config,
                http_client=app.state.aprs_client,
            )
            app.state.aprs_task = asyncio.create_task(ingestor.run())
            logger.info("APRS ingestor started")

    try:
        # Yield control to application (request handling, tests, etc.)
        yield
    finally:
        # ----- Shutdown logic (previously on_shutdown) -----
        task = getattr(app.state, "aprs_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        client: httpx.AsyncClient | None = getattr(app.state, "aprs_client", None)
        if client:
            await client.aclose()


app = FastAPI(title="SentinelAI Backend", lifespan=lifespan)

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

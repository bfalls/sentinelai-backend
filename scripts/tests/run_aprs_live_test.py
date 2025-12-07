#!/usr/bin/env python
"""
Run this to exercise the live APRS-IS ingestor against a real APRS-IS feed.

This script will:
  * Connect to the APRS-IS server configured in your environment
  * Stream APRS packets for a fixed amount of time
  * Post each decoded packet to the SentinelAI backend /api/v1/events endpoint
  * Log a summary line for each event so you can see activity in the terminal

Usage (from repo root):

    # Ensure your local API server is running, e.g.
    #   npm run api-dev
    #
    # Ensure these env vars are set (or in your .env.dev):
    #   APRS_ENABLED=true
    #   APRS_HOST=rotate.aprs2.net      # or your preferred server
    #   APRS_PORT=14580
    #   APRS_CALLSIGN=YOURCALL-10
    #   APRS_PASSCODE=...
    #   APRS_FILTER=...                 # optional, or use center/radius vars
    #
    # Then run:
    #
    #   npm run api-test-aprs-live
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
import logging
from typing import Any

import httpx
import os

def load_env_file(path: str) -> None:
    """Load KEY=VALUE pairs from a .env-style file without third-party packages."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
            
load_env_file(".env.dev")

from app.config import settings
from app.ingestors import APRSIngestor, build_aprs_config


logger = logging.getLogger("sentinelai.scripts.aprs_live_test")


class LoggingAsyncClient(httpx.AsyncClient):
    """httpx.AsyncClient that logs each APRS event POST."""

    async def post(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:  # type: ignore[override]
        started = datetime.now(timezone.utc)
        body = kwargs.get("json")
        event_type = None
        source = None
        try:
            if isinstance(body, dict):
                event_type = body.get("event_type")
                meta = body.get("event_metadata") or {}
                source = meta.get("source_callsign") or meta.get("source")
        except Exception:
            # Best-effort only; don't let logging break ingestion.
            pass

        logger.info("POST %s event_type=%r source=%r", url, event_type, source)
        resp = await super().post(url, *args, **kwargs)
        duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        logger.info(" -> %s in %.1f ms", resp.status_code, duration_ms)
        return resp


async def main() -> None:
    # How long to run the live APRS test.
    duration_seconds = 60

    if not settings.aprs_enabled:
        print("APRS ingestion is disabled (APRS_ENABLED is false or not set); aborting live test.")
        return

    if not settings.aprs_callsign or not settings.aprs_passcode:
        print("APRS credentials are missing (APRS_CALLSIGN / APRS_PASSCODE); aborting live test.")
        return

    # Build APRS runtime config using the same settings as app.main.
    aprs_config = build_aprs_config(
        host=settings.aprs_host,
        port=settings.aprs_port,
        callsign=settings.aprs_callsign,
        passcode=settings.aprs_passcode,
        aprs_filter=settings.aprs_filter,
        filter_center_lat=settings.aprs_filter_center_lat,
        filter_center_lon=settings.aprs_filter_center_lon,
        filter_radius_km=settings.aprs_filter_radius_km,
        mission_id=f"aprs-live-test-{datetime.now(timezone.utc).isoformat()}",
    )

    print(
        f"\nStarting APRS live test for {duration_seconds} seconds "
        f"against {aprs_config.host}:{aprs_config.port} "
        f"with callsign {aprs_config.callsign!r}"
    )
    print(f"Posting events to {settings.api_base_url}/api/v1/events\n")

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    async with LoggingAsyncClient(base_url=settings.api_base_url, timeout=15) as client:
        ingestor = APRSIngestor(
            config=aprs_config,
            http_client=client,
            events_path="/api/v1/events",
        )

        task = asyncio.create_task(ingestor.run())

        try:
            await asyncio.sleep(duration_seconds)
        finally:
            print("\nStopping APRS live test, cancelling ingestor task...")
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    print("APRS live test complete. Check your logs and database for ingested events.\n")


if __name__ == "__main__":
    asyncio.run(main())

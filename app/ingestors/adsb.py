"""ADSB ingestor for nearby air traffic using OpenSky REST API."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
from typing import Any, Optional

import httpx

from app.config import settings
from app.models.air_traffic import AircraftTrack

logger = logging.getLogger("sentinelai.ingestors.adsb")


def _parse_timestamp(raw_ts: Any) -> datetime | None:
    if raw_ts is None:
        return None
    try:
        if isinstance(raw_ts, (int, float)):
            # OpenSky returns seconds since epoch
            return datetime.fromtimestamp(raw_ts, tz=timezone.utc)
        if isinstance(raw_ts, str):
            if raw_ts.endswith("Z"):
                raw_ts = raw_ts.replace("Z", "+00:00")
            return datetime.fromisoformat(raw_ts)
    except Exception:  # pragma: no cover - defensive conversion
        logger.debug("Failed to parse ADS-B timestamp: %s", raw_ts)
        return None
    return None


def _m_to_feet(value_m: Any) -> float | None:
    if value_m is None:
        return None
    try:
        return float(value_m) * 3.28084
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        return None


def _ms_to_knots(value_ms: Any) -> float | None:
    if value_ms is None:
        return None
    try:
        return float(value_ms) * 1.94384
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        return None


def _ms_to_fpm(value_ms: Any) -> float | None:
    if value_ms is None:
        return None
    try:
        return float(value_ms) * 196.850394
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        return None


class ADSBIngestor:
    """Fetch nearby aircraft tracks using an ADS-B provider."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        default_radius_nm: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url or settings.adsb_base_url
        self.timeout = timeout or settings.adsb_timeout
        self.default_radius_nm = default_radius_nm or settings.adsb_default_radius_nm
        self.transport = transport

    async def get_air_traffic(
        self, lat: float, lon: float, radius_nm: float | None = None
    ) -> list[AircraftTrack]:
        radius = radius_nm or self.default_radius_nm
        lat_delta = radius / 60.0
        lon_delta = radius / max(60.0 * math.cos(math.radians(lat)), 0.0001)
        params = {
            "lamin": lat - lat_delta,
            "lomin": lon - lon_delta,
            "lamax": lat + lat_delta,
            "lomax": lon + lon_delta,
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(self.base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("ADSB request timed out: %s", exc)
            return []
        except httpx.RequestError as exc:
            logger.warning("ADSB request failed: %s", exc)
            return []

        if response.status_code == 429:
            logger.warning("ADSB provider rate limit encountered: %s", response.text)
            return []
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "ADSB provider returned HTTP %s: %s", exc.response.status_code, exc
            )
            return []

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("Failed to parse ADSB JSON response: %s", exc)
            return []

        raw_tracks = []
        if isinstance(payload, dict):
            raw_tracks = payload.get("states", []) or []

        tracks: list[AircraftTrack] = []
        for entry in raw_tracks:
            track = self._normalize_track(entry)
            if track:
                tracks.append(track)

        logger.debug("Ingested %s aircraft tracks", len(tracks))
        return tracks

    def _normalize_track(self, entry: Any) -> Optional[AircraftTrack]:
        if not isinstance(entry, (list, tuple)) or len(entry) < 7:
            return None

        icao = entry[0].upper() if entry[0] else None
        callsign = entry[1].strip() if entry[1] else None
        lon = entry[5]
        lat = entry[6]
        altitude_m = entry[13] if len(entry) > 13 and entry[13] is not None else entry[7]
        velocity_ms = entry[9] if len(entry) > 9 else None
        heading = entry[10] if len(entry) > 10 else None
        vertical_rate_ms = entry[11] if len(entry) > 11 else None
        last_seen = entry[4] if len(entry) > 4 and entry[4] is not None else entry[3]

        if lat is None or lon is None:
            return None

        track = AircraftTrack(
            callsign=callsign,
            icao=icao,
            lat=float(lat),
            lon=float(lon),
            altitude=_m_to_feet(altitude_m),
            ground_speed=_ms_to_knots(velocity_ms),
            heading=heading,
            vertical_rate=_ms_to_fpm(vertical_rate_ms),
            last_seen=_parse_timestamp(last_seen),
        )
        return track


__all__ = ["ADSBIngestor", "AircraftTrack"]

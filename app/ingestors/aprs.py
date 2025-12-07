"""APRS-IS ingestor for streaming radio position and message data."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
from typing import AsyncIterator, Callable

import httpx

logger = logging.getLogger("sentinelai.ingestors.aprs")


@dataclass
class BoundingBox:
    """Simple bounding box for APRS filter construction."""

    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


@dataclass
class AprsMessage:
    """Normalized APRS packet information."""

    source: str
    destination: str | None
    lat: float | None
    lon: float | None
    altitude_m: float | None
    text: str | None
    timestamp: datetime
    raw_packet: str | None = None


@dataclass
class APRSConfig:
    """Runtime configuration for the APRS ingestor."""

    host: str
    port: int
    callsign: str
    passcode: str
    aprs_filter: str | None = None
    filter_center_lat: float | None = None
    filter_center_lon: float | None = None
    filter_radius_km: float | None = None
    mission_id: str | None = None


_POSITION_RE = re.compile(
    r"(?P<lat>\d{4,5}\.\d{2})(?P<lat_dir>[NS])(?P<sym_table>.)(?P<lon>\d{5}\.\d{2})(?P<lon_dir>[EW]).*",
)
_ALTITUDE_RE = re.compile(r"/A=(?P<alt>\d{6})")


def _dm_to_decimal(raw: str, direction: str) -> float:
    degrees = float(raw[:-5])
    minutes = float(raw[-5:])
    value = degrees + minutes / 60.0
    if direction in {"S", "W"}:
        value *= -1
    return value


def parse_aprs_packet(line: str) -> AprsMessage | None:
    """Parse a single APRS-IS packet into an AprsMessage.

    This parser intentionally handles a small, common subset of APRS position
    reports (uncompressed, no mic-e). Packets that do not match are ignored.
    """

    cleaned = line.strip()
    if not cleaned or cleaned.startswith("#"):
        return None

    if ":" not in cleaned or ">" not in cleaned:
        return None

    header, body = cleaned.split(":", 1)
    source_part, _, path_part = header.partition(">")
    if not source_part:
        return None
    destination = path_part.split(",", 1)[0] if path_part else None

    position_match = _POSITION_RE.match(body)
    lat = lon = None
    if position_match:
        lat_raw = position_match.group("lat")
        lon_raw = position_match.group("lon")
        lat_dir = position_match.group("lat_dir")
        lon_dir = position_match.group("lon_dir")
        try:
            lat = _dm_to_decimal(lat_raw, lat_dir)
            lon = _dm_to_decimal(lon_raw, lon_dir)
        except ValueError:
            lat = lon = None

    altitude_m = None
    alt_match = _ALTITUDE_RE.search(body)
    if alt_match:
        try:
            altitude_m = float(alt_match.group("alt")) * 0.3048
        except ValueError:
            altitude_m = None

    text = body.strip() if body else None

    return AprsMessage(
        source=source_part,
        destination=destination,
        lat=lat,
        lon=lon,
        altitude_m=altitude_m,
        text=text,
        timestamp=datetime.now(tz=timezone.utc),
        raw_packet=cleaned,
    )


class APRSIngestor:
    """Maintain a long-running APRS-IS TCP connection and forward packets."""

    def __init__(
        self,
        *,
        config: APRSConfig,
        http_client: httpx.AsyncClient,
        events_path: str = "/api/v1/events",
        line_source: Callable[[], AsyncIterator[str]] | None = None,
        stop_on_source: bool = False,
    ) -> None:
        self.config = config
        self.http_client = http_client
        self.events_path = events_path
        self.line_source = line_source
        self.stop_on_source = stop_on_source

    async def run(self) -> None:
        """Run the APRS stream until cancelled."""

        backoff = 1
        while True:
            try:
                if self.line_source:
                    await self._consume_lines(self.line_source)
                    if self.stop_on_source:
                        return
                    await asyncio.sleep(backoff)
                    continue

                await self._connect_and_stream()
                backoff = 1
            except asyncio.CancelledError:
                logger.info("APRS ingestor cancelled")
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("APRS ingestor error: %s", exc)

            backoff = min(backoff * 2, 60)
            await asyncio.sleep(backoff)

    async def _consume_lines(
        self, source: Callable[[], AsyncIterator[str]]
    ) -> None:
        async for line in source():
            await self._handle_line(line)

    async def _connect_and_stream(self) -> None:
        reader, writer = await asyncio.open_connection(self.config.host, self.config.port)
        logger.info(
            "Connected to APRS-IS at %s:%s as %s",
            self.config.host,
            self.config.port,
            self.config.callsign,
        )
        try:
            await self._send_login(writer)
            while True:
                data = await reader.readline()
                if not data:
                    break
                await self._handle_line(data.decode(errors="ignore"))
        finally:
            writer.close()
            with contextlib.suppress(Exception):  # pragma: no cover - best effort close
                await writer.wait_closed()
            logger.info("APRS connection closed; will attempt reconnect")

    async def _send_login(self, writer: asyncio.StreamWriter) -> None:
        filter_clause = self._build_filter()
        if filter_clause:
            login_line = (
                f"user {self.config.callsign} pass {self.config.passcode} "
                f"vers SentinelAI 1.0 filter {filter_clause}\n"
            )
        else:
            login_line = (
                f"user {self.config.callsign} pass {self.config.passcode} "
                f"vers SentinelAI 1.0\n"
            )
            
        print("APRS LOGIN:", login_line.strip())  # DEBUG
        writer.write(login_line.encode())
        await writer.drain()

    def _build_filter(self) -> str | None:
        if self.config.aprs_filter:
            return self.config.aprs_filter
        if (
            self.config.filter_center_lat is not None
            and self.config.filter_center_lon is not None
            and self.config.filter_radius_km is not None
        ):
            return "r/{lat}/{lon}/{radius}".format(
                lat=self.config.filter_center_lat,
                lon=self.config.filter_center_lon,
                radius=self.config.filter_radius_km,
            )
        return None

    async def _handle_line(self, line: str) -> None:
        message = parse_aprs_packet(line)
        if message is None:
            return

        payload = {
            "event_type": "aprs",
            "description": message.text,
            "mission_id": self.config.mission_id,
            "source": "aprs_is",
            "timestamp": message.timestamp.isoformat(),
            "event_metadata": {
                "source_callsign": message.source,
                "dest_callsign": message.destination,
                "lat": message.lat,
                "lon": message.lon,
                "altitude_m": message.altitude_m,
                "text": message.text,
                "raw_packet": message.raw_packet,
            },
        }

        try:
            response = await self.http_client.post(self.events_path, json=payload)
            if response.status_code >= 400:
                logger.warning(
                    "Failed to post APRS event: status=%s body=%s",
                    response.status_code,
                    response.text,
                )
        except httpx.RequestError as exc:
            logger.warning("APRS event post failed: %s", exc)


def build_aprs_config(
    *,
    host: str,
    port: int,
    callsign: str,
    passcode: str,
    aprs_filter: str | None = None,
    filter_center_lat: float | None = None,
    filter_center_lon: float | None = None,
    filter_radius_km: float | None = None,
    mission_id: str | None = None,
) -> APRSConfig:
    return APRSConfig(
        host=host,
        port=port,
        callsign=callsign,
        passcode=passcode,
        aprs_filter=aprs_filter,
        filter_center_lat=filter_center_lat,
        filter_center_lon=filter_center_lon,
        filter_radius_km=filter_radius_km,
        mission_id=mission_id,
    )


__all__ = [
    "APRSConfig",
    "APRSIngestor",
    "AprsMessage",
    "BoundingBox",
    "build_aprs_config",
    "parse_aprs_packet",
]

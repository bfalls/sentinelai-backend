"""Build mission context payloads with optional weather, air traffic, and APRS data."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app import db_models
from app.config import settings
from app.ingestors import ADSBIngestor, AprsMessage, WeatherIngestor
from app.models.air_traffic import AircraftTrack
from app.models.analysis import MissionAnalysisRequest, MissionSignalModel
from app.models.weather import WeatherSnapshot
from app.services.analysis_engine import (
    MissionContextPayload,
    MissionLocationPayload,
    MissionSignal,
)

logger = logging.getLogger("sentinelai.context_builder")


class ContextBuilder:
    """Orchestrates enrichment of mission context for analysis."""

    def __init__(
        self,
        weather_ingestor: Optional[WeatherIngestor] = None,
        adsb_ingestor: Optional[ADSBIngestor] = None,
    ) -> None:
        self.weather_ingestor = weather_ingestor or WeatherIngestor()
        self.adsb_ingestor = adsb_ingestor or ADSBIngestor()

    async def build_context_payload(
        self, request: MissionAnalysisRequest, db: Session | None = None
    ) -> MissionContextPayload:
        mission_location = None
        weather_snapshot: WeatherSnapshot | None = None
        air_traffic: list[AircraftTrack] | None = None
        aprs_messages: list[AprsMessage] | None = None

        if request.location:
            mission_location = MissionLocationPayload(
                latitude=request.location.latitude,
                longitude=request.location.longitude,
                description=request.location.description,
            )

        if settings.enable_weather_ingestor and request.location:
            try:
                weather_snapshot = await self.weather_ingestor.get_weather(
                    request.location.latitude,
                    request.location.longitude,
                    request.time_window,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Weather ingestion unavailable: %s", exc)

        if settings.enable_adsb_ingestor and request.location:
            try:
                air_traffic = await self.adsb_ingestor.get_air_traffic(
                    request.location.latitude,
                    request.location.longitude,
                    radius_nm=None,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("ADSB ingestion unavailable: %s", exc)

        if settings.aprs_enabled and db is not None:
            aprs_messages = self._load_aprs_messages(
                db, request.mission_id, request.time_window
            )

        return MissionContextPayload(
            mission_id=request.mission_id,
            mission_metadata=request.mission_metadata,
            signals=_convert_signals(request.signals),
            notes=request.notes,
            mission_location=mission_location,
            time_window=request.time_window,
            weather=weather_snapshot,
            air_traffic=air_traffic,
            aprs_messages=aprs_messages,
        )

    def _load_aprs_messages(
        self,
        db: Session,
        mission_id: str | None,
        time_window,
    ) -> list[AprsMessage] | None:
        cutoff_start: datetime | None = None
        cutoff_end: datetime | None = None
        if time_window:
            cutoff_start = time_window.start
            cutoff_end = time_window.end
        if cutoff_start is None:
            cutoff_start = datetime.utcnow() - timedelta(hours=1)

        query = db.query(db_models.EventRecord).filter(
            db_models.EventRecord.event_type == "aprs",
            db_models.EventRecord.timestamp >= cutoff_start,
        )
        if cutoff_end is not None:
            query = query.filter(db_models.EventRecord.timestamp <= cutoff_end)
        if mission_id:
            query = query.filter(db_models.EventRecord.mission_id == mission_id)

        records = query.order_by(db_models.EventRecord.timestamp.desc()).limit(100).all()
        if not records:
            return None

        messages: list[AprsMessage] = []
        for record in records:
            metadata = record.event_metadata or {}
            messages.append(
                AprsMessage(
                    source=metadata.get("source_callsign") or record.source or "unknown",
                    destination=metadata.get("dest_callsign"),
                    lat=metadata.get("lat"),
                    lon=metadata.get("lon"),
                    altitude_m=metadata.get("altitude_m"),
                    text=metadata.get("text") or record.description,
                    timestamp=record.timestamp,
                    raw_packet=metadata.get("raw_packet"),
                )
            )
        return messages


def _convert_signals(signals: list[MissionSignalModel] | None):
    if not signals:
        return None
    return [
        MissionSignal(
            type=signal.type,
            description=signal.description,
            timestamp=signal.timestamp,
            metadata=signal.metadata,
        )
        for signal in signals
    ]


_default_builder = ContextBuilder()


async def build_context_payload(
    request: MissionAnalysisRequest, db: Session | None = None
) -> MissionContextPayload:
    """Convenience wrapper using the default context builder."""

    return await _default_builder.build_context_payload(request, db=db)


__all__ = ["ContextBuilder", "build_context_payload"]

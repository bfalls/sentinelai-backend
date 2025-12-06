"""Build mission context payloads with optional weather enrichment."""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.ingestors import WeatherIngestor
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

    def __init__(self, weather_ingestor: Optional[WeatherIngestor] = None) -> None:
        self.weather_ingestor = weather_ingestor or WeatherIngestor()

    async def build_context_payload(
        self, request: MissionAnalysisRequest
    ) -> MissionContextPayload:
        mission_location = None
        weather_snapshot: WeatherSnapshot | None = None

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

        return MissionContextPayload(
            mission_id=request.mission_id,
            mission_metadata=request.mission_metadata,
            signals=_convert_signals(request.signals),
            notes=request.notes,
            mission_location=mission_location,
            time_window=request.time_window,
            weather=weather_snapshot,
        )


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


async def build_context_payload(request: MissionAnalysisRequest) -> MissionContextPayload:
    """Convenience wrapper using the default context builder."""

    return await _default_builder.build_context_payload(request)


__all__ = ["ContextBuilder", "build_context_payload"]

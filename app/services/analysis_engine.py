"""Rule-based analysis engine with a pluggable interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Optional, Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import db_models

logger = logging.getLogger("sentinelai.analysis_engine")


@dataclass
class AnalysisResult:
    """Structured outcome of an analysis run."""

    mission_id: Optional[str]
    window_minutes: int
    event_count: int
    status: str
    summary: str
    last_event_at: Optional[datetime]
    dominant_event_type: Optional[str]


class AnalysisEngine(Protocol):
    """Interface for mission analysis engines."""

    def analyze(
        self, db: Session, *, mission_id: Optional[str], window_minutes: int
    ) -> AnalysisResult:
        """Produce a mission status and supporting metadata."""


class RuleBasedAnalysisEngine:
    """Simple rule-based analysis implementation.

    This engine can be swapped out for an AI-backed version in the future
    without changing the API layer.
    """

    def __init__(
        self,
        attention_threshold: int = 5,
        critical_threshold: int = 10,
    ) -> None:
        self.attention_threshold = attention_threshold
        self.critical_threshold = critical_threshold

    def analyze(
        self, db: Session, *, mission_id: Optional[str], window_minutes: int
    ) -> AnalysisResult:
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        query = db.query(db_models.EventRecord).filter(
            db_models.EventRecord.timestamp >= cutoff
        )
        if mission_id:
            query = query.filter(db_models.EventRecord.mission_id == mission_id)

        event_count = query.count()
        last_event = query.order_by(db_models.EventRecord.timestamp.desc()).first()

        dominant_event_type = self._compute_dominant_event_type(
            db, mission_id, cutoff
        )
        status, summary = self._score(event_count, dominant_event_type)

        result = AnalysisResult(
            mission_id=mission_id,
            window_minutes=window_minutes,
            event_count=event_count,
            status=status,
            summary=summary,
            last_event_at=last_event.timestamp if last_event else None,
            dominant_event_type=dominant_event_type,
        )
        logger.debug("Analysis result computed: %s", result)
        return result

    def _compute_dominant_event_type(
        self, db: Session, mission_id: Optional[str], cutoff: datetime
    ) -> Optional[str]:
        type_counts = (
            db.query(
                db_models.EventRecord.event_type, func.count().label("count")
            )
            .filter(db_models.EventRecord.timestamp >= cutoff)
            .group_by(db_models.EventRecord.event_type)
        )
        if mission_id:
            type_counts = type_counts.filter(
                db_models.EventRecord.mission_id == mission_id
            )

        counts = type_counts.order_by(func.count().desc()).first()
        return counts[0] if counts else None

    def _score(
        self, event_count: int, dominant_event_type: Optional[str]
    ) -> tuple[str, str]:
        if event_count >= self.critical_threshold:
            status = "critical"
            summary = "High volume of events; immediate attention required."
        elif event_count >= self.attention_threshold:
            status = "attention"
            summary = "Elevated activity detected; monitor ongoing events."
        else:
            status = "stable"
            summary = "Low activity; mission appears stable."

        if dominant_event_type:
            summary = f"{summary} Most frequent event type: {dominant_event_type}."
        return status, summary


def get_analysis_engine() -> AnalysisEngine:
    """Return the configured analysis engine.

    Hook point for future AI-driven analysis implementations.
    """

    return RuleBasedAnalysisEngine()

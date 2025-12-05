"""SQLAlchemy ORM models for SentinelAI backend."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from app.db import Base


class EventRecord(Base):
    """Persisted event captured from clients."""

    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    mission_id = Column(String, nullable=True, index=True)
    source = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metadata = Column(JSON, nullable=True)


class AnalysisSnapshot(Base):
    """Snapshot of mission analysis computed at a point in time."""

    __tablename__ = "analysis_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mission_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    event_count = Column(Integer, nullable=False, default=0)
    window_minutes = Column(Integer, nullable=False, default=60)

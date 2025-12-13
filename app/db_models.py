"""SQLAlchemy ORM models for SentinelAI backend."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApiKey(Base):
    """Stored API keys for authenticating requests."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_expires_at", "expires_at"),
        Index("ix_api_keys_revoked_at", "revoked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_prefix: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    holder_email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    holder_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # id = Column(Integer, primary_key=True, autoincrement=True)
    # key_prefix = Column(String(32), unique=True, index=True, nullable=False)
    # key_hash = Column(String(128), nullable=False)
    # holder_email = Column(String(255), index=True, nullable=False)
    # holder_label = Column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # expires_at:  Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # revoked_at = Column(DateTime, nullable=True)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # last_used_at = Column(DateTime, nullable=True)
    # last_used_ip = Column(String(64), nullable=True)
    # notes = Column(Text, nullable=True)


class EventRecord(Base):
    """Persisted event captured from clients."""

    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    mission_id = Column(String, nullable=True, index=True)
    source = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_metadata = Column(JSON, nullable=True)


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

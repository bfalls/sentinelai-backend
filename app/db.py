"""Database configuration and helpers for SentinelAI backend."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

DATABASE_URL = os.getenv("SENTINELAI_DB_URL", "sqlite:///./sentinelai.db")
CLEANUP_STATE_FILE = Path(
    os.getenv(
        "SENTINELAI_RETENTION_STATE_FILE", "/var/lib/sentinelai/retention_cleanup_state"
    )
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

logger = logging.getLogger("sentinelai.db")


def _load_last_cleanup_date() -> date | None:
    """Load the last cleanup date from disk if present."""

    try:
        if not CLEANUP_STATE_FILE.exists():
            return None

        stored = CLEANUP_STATE_FILE.read_text().strip()
        if not stored:
            return None

        return date.fromisoformat(stored)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Failed to load last cleanup date from %s: %s", CLEANUP_STATE_FILE, exc
        )
        return None


def _persist_last_cleanup_date(value: date) -> None:
    """Persist the last cleanup date to disk for reuse across restarts."""

    try:
        CLEANUP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CLEANUP_STATE_FILE.write_text(value.isoformat())
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Failed to persist cleanup date to %s: %s", CLEANUP_STATE_FILE, exc
        )


_last_cleanup_date: date | None = _load_last_cleanup_date()


def get_db() -> Generator:
    """Yield a SQLAlchemy session and ensure it is closed."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create database tables if they do not exist."""

    import app.db_models  # noqa: F401 - models are imported for side effects

    Base.metadata.create_all(bind=engine)


def maybe_cleanup_old_records(db: Session) -> None:
    """
    Delete old DB rows if the retention window has been exceeded.

    - Only run at most once per UTC day.
    - Delete events and analysis snapshots older than the configured retention.
    - Use date-based comparison, ignoring time-of-day.
    - Fail-soft: log on error but never break the caller's normal write.
    """

    global _last_cleanup_date

    try:
        today = date.today()
        if _last_cleanup_date == today:
            return

        retention_days = max(settings.retention_days, 1)
        cutoff_date = today - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()

        import app.db_models as models

        old_events_q = db.query(models.EventRecord.id).filter(
            func.date(models.EventRecord.timestamp) < cutoff_str
        )

        old_snapshots_q = db.query(models.AnalysisSnapshot.id).filter(
            func.date(models.AnalysisSnapshot.created_at) < cutoff_str
        )

        if old_events_q.limit(1).first() is None and old_snapshots_q.limit(1).first() is None:
            _last_cleanup_date = today
            _persist_last_cleanup_date(today)
            return

        db.query(models.EventRecord).filter(
            func.date(models.EventRecord.timestamp) < cutoff_str
        ).delete(synchronize_session=False)

        db.query(models.AnalysisSnapshot).filter(
            func.date(models.AnalysisSnapshot.created_at) < cutoff_str
        ).delete(synchronize_session=False)

        db.commit()
        _last_cleanup_date = today
        _persist_last_cleanup_date(today)
    except Exception as exc:  # pragma: no cover - defensive logging
        db.rollback()
        logger.warning("Retention cleanup failed: %s", exc)

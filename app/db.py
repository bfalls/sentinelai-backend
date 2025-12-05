"""Database configuration and helpers for SentinelAI backend."""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("SENTINELAI_DB_URL", "sqlite:///./sentinelai.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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

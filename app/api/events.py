"""Event ingestion endpoints."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import db_models
from app.db import get_db
from app.models import Event, EventCreateResponse

router = APIRouter(prefix="/api/v1", tags=["events"])

logger = logging.getLogger("sentinelai.events")


def _validate_event(event: Event) -> None:
    if not event.event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="event_type is required",
        )


@router.post(
    "/events",
    response_model=EventCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an event",
)
async def create_event(event: Event, db: Session = Depends(get_db)) -> EventCreateResponse:
    """Accept an event from the CivTAK plugin and persist it to SQLite."""

    _validate_event(event)
    event_id = str(uuid4())

    record = db_models.EventRecord(
        id=event_id,
        event_type=event.event_type,
        description=event.description,
        mission_id=event.mission_id,
        source=event.source,
        timestamp=event.timestamp,
        event_metadata=event.metadata,
    )

    db.add(record)
    db.commit()

    logger.info("Stored event %s of type %s", event_id, event.event_type)
    return EventCreateResponse(id=event_id, status="received")

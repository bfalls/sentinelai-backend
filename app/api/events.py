"""Event ingestion endpoints."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from app.models import Event, EventCreateResponse

router = APIRouter(prefix="/api/v1", tags=["events"])

logger = logging.getLogger("sentinelai.events")
_event_lock = Lock()
_event_buffer: list[dict[str, Any]] = []
_event_log_path = Path(__file__).resolve().parent.parent / "events.log"


def _write_event_to_disk(event_record: dict[str, Any]) -> None:
    """Append an event record to a newline-delimited JSON file."""

    try:
        with _event_lock:
            _event_log_path.parent.mkdir(parents=True, exist_ok=True)
            with _event_log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(event_record) + "\n")
    except OSError as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to persist event to disk: %s", exc)


def _store_event(event: Event, event_id: str) -> None:
    """Store an event in memory and log to disk for Phase 1."""

    event_record = {"id": event_id, **event.model_dump()}
    with _event_lock:
        _event_buffer.append(event_record)
    _write_event_to_disk(event_record)
    logger.info("Stored event %s of type %s", event_id, event.event_type)


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
async def create_event(event: Event) -> EventCreateResponse:
    """Accept an event from the CivTAK plugin and buffer it for later analysis."""

    _validate_event(event)
    event_id = str(uuid4())
    _store_event(event, event_id)
    return EventCreateResponse(id=event_id, status="received")

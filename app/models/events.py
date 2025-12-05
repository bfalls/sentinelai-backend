"""Event models for SentinelAI backend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Incoming event data from the CivTAK plugin or other sources."""

    event_type: str = Field(..., description="Type or category of the event")
    description: Optional[str] = Field(
        default=None, description="Human-readable description of the event"
    )
    mission_id: Optional[str] = Field(
        default=None, description="Identifier of the mission or operation"
    )
    source: Optional[str] = Field(
        default=None, description="Source system or device that produced the event"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the event occurred (UTC)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Additional structured metadata for the event"
    )


class EventCreateResponse(BaseModel):
    """Response returned after accepting an event."""

    id: str = Field(..., description="Server-assigned unique identifier for the event")
    status: str = Field(..., description="Status of the event submission")

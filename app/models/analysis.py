"""Analysis-related request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.domain import MissionIntent
from app.models.weather import TimeWindow


class AnalysisStatusResponse(BaseModel):
    """Response describing mission status derived from recent events."""

    mission_id: Optional[str] = Field(
        default=None, description="Mission identifier scoped for the analysis"
    )
    window_minutes: int = Field(..., description="Time window used for the analysis")
    event_count: int = Field(..., description="Number of events in the window")
    status: Literal["stable", "attention", "critical"] = Field(
        ..., description="Rule-based mission status",
    )
    last_event_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the most recent event in the window"
    )
    summary: str = Field(..., description="Short summary of how the status was derived")


class MissionSignalModel(BaseModel):
    """Signal describing a notable mission event or observation."""

    type: str = Field(..., description="Signal category or type")
    description: Optional[str] = Field(
        default=None, description="Human-readable description of the signal"
    )
    timestamp: Optional[datetime] = Field(
        default=None, description="Timestamp when the signal occurred"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Optional metadata for the signal"
    )


class MissionLocation(BaseModel):
    """Represents a mission location for contextual data lookups."""

    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    description: Optional[str] = Field(
        default=None, description="Optional descriptor for the location",
    )


class MissionAnalysisRequest(BaseModel):
    """Payload for AI-assisted mission analysis."""

    mission_id: Optional[str] = Field(
        default=None, description="Identifier for the mission"
    )
    mission_metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Metadata describing the mission"
    )
    signals: Optional[list[MissionSignalModel]] = Field(
        default=None, description="List of mission signals to analyze"
    )
    notes: Optional[str] = Field(
        default=None, description="Free-form mission notes or analyst guidance"
    )
    location: Optional[MissionLocation] = Field(
        default=None, description="Mission coordinates for contextual lookups",
    )
    time_window: Optional[TimeWindow] = Field(
        default=None, description="Time window for weather or temporal context",
    )
    intent: Optional[MissionIntent] = Field(
        default=None,
        description="Desired analysis intent that shapes AI behavior; optional for auto-selection",
    )


class MissionAnalysisResponse(BaseModel):
    """Structured response for AI-backed mission analysis."""

    intent: MissionIntent = Field(..., description="Intent applied to the analysis")
    summary: str = Field(..., description="Summary produced by the AI")
    risks: list[str] = Field(
        default_factory=list, description="List of risks highlighted by the AI"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="List of recommended actions"
    )


__all__ = [
    "AnalysisStatusResponse",
    "MissionAnalysisRequest",
    "MissionAnalysisResponse",
    "MissionSignalModel",
    "MissionLocation",
    "TimeWindow",
]

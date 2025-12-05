"""Analysis-related response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AnalysisStatusResponse(BaseModel):
    """Response describing mission status derived from recent events."""

    mission_id: Optional[str] = Field(
        default=None, description="Mission identifier scoped for the analysis"
    )
    window_minutes: int = Field(..., description="Time window used for the analysis")
    event_count: int = Field(..., description="Number of events in the window")
    status: Literal["stable", "attention", "critical"] = Field(
        ..., description="Rule-based mission status"
    )
    last_event_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the most recent event in the window"
    )
    summary: str = Field(..., description="Short summary of how the status was derived")

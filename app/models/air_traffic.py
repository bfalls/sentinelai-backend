"""Models for air traffic tracks ingested from ADS-B sources."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AircraftTrack(BaseModel):
    """Normalized representation of an aircraft track."""

    callsign: Optional[str] = Field(default=None, description="Aircraft callsign")
    icao: Optional[str] = Field(default=None, description="ICAO hex identifier")
    lat: float = Field(..., description="Latitude in decimal degrees")
    lon: float = Field(..., description="Longitude in decimal degrees")
    altitude: Optional[float] = Field(default=None, description="Altitude in feet")
    ground_speed: Optional[float] = Field(
        default=None, description="Ground speed in knots where available"
    )
    heading: Optional[float] = Field(
        default=None, description="Track heading in degrees"
    )
    vertical_rate: Optional[float] = Field(
        default=None, description="Vertical rate in feet per minute"
    )
    last_seen: Optional[datetime] = Field(
        default=None, description="Timestamp when the aircraft was last seen"
    )

    model_config = ConfigDict(extra="ignore")


__all__ = ["AircraftTrack"]

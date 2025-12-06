"""Weather data models for mission context enrichment."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    """Represents a time window for weather observations or forecasts."""

    start: Optional[datetime] = Field(
        default=None, description="Window start time (UTC)",
    )
    end: Optional[datetime] = Field(
        default=None, description="Window end time (UTC)",
    )


class WeatherSnapshot(BaseModel):
    """Mission-relevant weather details for a given location and time."""

    latitude: float = Field(..., description="Latitude of the observation point")
    longitude: float = Field(..., description="Longitude of the observation point")
    as_of: datetime = Field(..., description="Timestamp of the weather data (UTC)")
    temperature_c: Optional[float] = Field(
        default=None, description="Air temperature in Celsius",
    )
    wind_speed_mps: Optional[float] = Field(
        default=None, description="Wind speed in meters per second",
    )
    wind_direction_deg: Optional[float] = Field(
        default=None, description="Wind direction in degrees",
    )
    precipitation_probability_pct: Optional[float] = Field(
        default=None, description="Probability of precipitation in percent",
    )
    precipitation_mm: Optional[float] = Field(
        default=None, description="Total precipitation in millimeters",
    )
    visibility_km: Optional[float] = Field(
        default=None, description="Visibility in kilometers",
    )
    cloud_cover_pct: Optional[float] = Field(
        default=None, description="Cloud cover percentage",
    )
    condition: Optional[str] = Field(
        default=None, description="Short textual summary of conditions",
    )


__all__ = ["WeatherSnapshot", "TimeWindow"]

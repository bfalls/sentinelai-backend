"""Mission intent definitions for analysis routing."""

from __future__ import annotations

from enum import Enum


class MissionIntent(str, Enum):
    """Supported mission analysis intents."""

    SITUATIONAL_AWARENESS = "SITUATIONAL_AWARENESS"
    ROUTE_RISK_ASSESSMENT = "ROUTE_RISK_ASSESSMENT"
    WEATHER_IMPACT = "WEATHER_IMPACT"
    AIRSPACE_DECONFLICTION = "AIRSPACE_DECONFLICTION"
    AIR_ACTIVITY_ANALYSIS = "AIR_ACTIVITY_ANALYSIS"
    RADIO_SIGNAL_ACTIVITY_ANALYSIS = "RADIO_SIGNAL_ACTIVITY_ANALYSIS"


DEFAULT_INTENT: MissionIntent = MissionIntent.SITUATIONAL_AWARENESS

__all__ = ["MissionIntent", "DEFAULT_INTENT"]

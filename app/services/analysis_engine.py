"""Rule-based and AI-assisted analysis engines with a stable interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import math
from typing import Any, Awaitable, Callable, Optional, Protocol

try:  # pragma: no cover - allow import when SQLAlchemy is unavailable
    from sqlalchemy import func
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover - handled in runtime checks
    func = None
    Session = Any  # type: ignore

from app.config import settings
from app.domain import DEFAULT_INTENT, MissionIntent
from app.ingestors import AprsMessage
from app.models.analysis import MissionAnalysisRequest
from app.models.air_traffic import AircraftTrack
from app.models.weather import TimeWindow, WeatherSnapshot
from app.services import openai_client

logger = logging.getLogger("sentinelai.analysis_engine")


@dataclass
class AnalysisResult:
    """Structured outcome of an analysis run."""

    mission_id: Optional[str]
    window_minutes: int
    event_count: int
    status: str
    summary: str
    last_event_at: Optional[datetime]
    dominant_event_type: Optional[str]


class AnalysisEngine(Protocol):
    """Interface for mission analysis engines."""

    def analyze(
        self, db: Session, *, mission_id: Optional[str], window_minutes: int
    ) -> AnalysisResult:
        """Produce a mission status and supporting metadata."""


class RuleBasedAnalysisEngine:
    """Simple rule-based analysis implementation.

    This engine can be swapped out for an AI-backed version in the future
    without changing the API layer.
    """

    def __init__(
        self,
        attention_threshold: int = 5,
        critical_threshold: int = 10,
    ) -> None:
        self.attention_threshold = attention_threshold
        self.critical_threshold = critical_threshold

    def analyze(
        self, db: Session, *, mission_id: Optional[str], window_minutes: int
    ) -> AnalysisResult:
        if func is None:
            raise RuntimeError("SQLAlchemy is required for rule-based analysis")
        from app import db_models

        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        query = db.query(db_models.EventRecord).filter(
            db_models.EventRecord.timestamp >= cutoff
        )
        if mission_id:
            query = query.filter(db_models.EventRecord.mission_id == mission_id)

        event_count = query.count()
        last_event = query.order_by(db_models.EventRecord.timestamp.desc()).first()

        dominant_event_type = self._compute_dominant_event_type(
            db, mission_id, cutoff
        )
        status, summary = self._score(event_count, dominant_event_type)

        result = AnalysisResult(
            mission_id=mission_id,
            window_minutes=window_minutes,
            event_count=event_count,
            status=status,
            summary=summary,
            last_event_at=last_event.timestamp if last_event else None,
            dominant_event_type=dominant_event_type,
        )
        logger.debug("Analysis result computed: %s", result)
        return result

    def _compute_dominant_event_type(
        self, db: Session, mission_id: Optional[str], cutoff: datetime
    ) -> Optional[str]:
        from app import db_models

        type_counts = (
            db.query(
                db_models.EventRecord.event_type, func.count().label("count")
            )
            .filter(db_models.EventRecord.timestamp >= cutoff)
            .group_by(db_models.EventRecord.event_type)
        )
        if mission_id:
            type_counts = type_counts.filter(
                db_models.EventRecord.mission_id == mission_id
            )

        counts = type_counts.order_by(func.count().desc()).first()
        return counts[0] if counts else None

    def _score(
        self, event_count: int, dominant_event_type: Optional[str]
    ) -> tuple[str, str]:
        if event_count >= self.critical_threshold:
            status = "critical"
            summary = "High volume of events; immediate attention required."
        elif event_count >= self.attention_threshold:
            status = "attention"
            summary = "Elevated activity detected; monitor ongoing events."
        else:
            status = "stable"
            summary = "Low activity; mission appears stable."

        if dominant_event_type:
            summary = f"{summary} Most frequent event type: {dominant_event_type}."
        return status, summary


def get_analysis_engine() -> AnalysisEngine:
    """Return the configured analysis engine.

    Hook point for future AI-driven analysis implementations.
    """

    return RuleBasedAnalysisEngine()


@dataclass
class MissionSignal:
    """Structured mission signal to pass into the AI model."""

    type: str
    description: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: dict[str, Any] | None = None


@dataclass
class MissionLocationPayload:
    """Simple mission location container for prompt building."""

    latitude: float
    longitude: float
    description: str | None = None


@dataclass
class MissionContextPayload:
    """Payload combining mission metadata and signals for AI analysis."""

    mission_id: Optional[str]
    mission_metadata: dict[str, Any] | None = None
    signals: list[MissionSignal] | None = None
    notes: str | None = None
    mission_location: MissionLocationPayload | None = None
    time_window: TimeWindow | None = None
    weather: WeatherSnapshot | None = None
    air_traffic: list[AircraftTrack] | None = None
    aprs_messages: list[AprsMessage] | None = None


@dataclass
class IntentDefinition:
    """Intent metadata used for AI-driven classification."""

    id: MissionIntent
    label: str
    description: str
    guidance: str


def _get_candidate_intents() -> list[IntentDefinition]:
    """Return the set of intents the AI model can classify and analyze."""

    return [
        IntentDefinition(
            id=MissionIntent.SITUATIONAL_AWARENESS,
            label="Situational Awareness",
            description="General situational summary of events and activity near the mission location.",
            guidance="Summarize key activity, risks, and recommended actions for the operator.",
        ),
        IntentDefinition(
            id=MissionIntent.ROUTE_RISK_ASSESSMENT,
            label="Route Risk Assessment",
            description="Assess risks related to movement or routing for the mission team.",
            guidance="Identify chokepoints, hazards along potential routes, and mitigation steps.",
        ),
        IntentDefinition(
            id=MissionIntent.WEATHER_IMPACT,
            label="Weather Impact",
            description="Evaluate how weather conditions affect mission execution.",
            guidance="Give exact temperature, wind speed and direction, precipitation info, visibility, and cloud cover. Highlight weather-related hazards, timing, and operational constraints.",
        ),
        IntentDefinition(
            id=MissionIntent.AIRSPACE_DECONFLICTION,
            label="Airspace Deconfliction",
            description="Identify and describe airspace conflicts or coordination needs.",
            guidance="Summarize conflicting flight activity and coordination requirements for safe operations.",
        ),
        IntentDefinition(
            id=MissionIntent.AIR_ACTIVITY_ANALYSIS,
            label="Aircraft Activity Analysis",
            description="Analyze ADS-B tracks and identify aircraft exhibiting unusual behavior, low-altitude patterns, holding loops, or training maneuvers.",
            guidance="Report exactly which aircraft were detected, how many, their altitude/speed changes, heading stability, and whether any show signs of abnormal behavior. Name aircraft (ICAO or callsign) if available. If no aircraft are present, explicitly say so.",
        ),
        IntentDefinition(
            id=MissionIntent.RADIO_SIGNAL_ACTIVITY_ANALYSIS,
            label="APRS Activity Analysis",
            description="Analyze APRS packet traffic within the area and time window, identifying units, movement patterns, signal anomalies, or unusual transmission behavior.",
            guidance=(
                "Give exact identification details."
                "Report which APRS stations transmitted, how many packets were received, "
                "their approximate locations or movement if available, timestamps, and message content trends. "
                "If no APRS packets are present, explicitly state that."
    ),
)
    ]


def _build_classification_payload(
    payload: MissionContextPayload, request: MissionAnalysisRequest
) -> dict[str, Any]:
    """Construct the JSON payload sent to OpenAI for intent + analysis."""

    signals_payload = []
    for signal in payload.signals or []:
        signals_payload.append(
            {
                "type": signal.type,
                "description": signal.description,
                "timestamp": signal.timestamp.isoformat() if signal.timestamp else None,
                "metadata": signal.metadata,
            }
        )

    mission_location = None
    if payload.mission_location:
        mission_location = {
            "latitude": payload.mission_location.latitude,
            "longitude": payload.mission_location.longitude,
            "description": payload.mission_location.description,
        }

    time_window = None
    if payload.time_window:
        time_window = {
            "start": payload.time_window.start.isoformat() if payload.time_window.start else None,
            "end": payload.time_window.end.isoformat() if payload.time_window.end else None,
        }

    weather_snapshot = None
    if payload.weather:
        weather_snapshot = {
            "as_of": payload.weather.as_of.isoformat(),
            "latitude": payload.weather.latitude,
            "longitude": payload.weather.longitude,
            "temperature_c": payload.weather.temperature_c,
            "wind_speed_mps": payload.weather.wind_speed_mps,
            "wind_direction_deg": payload.weather.wind_direction_deg,
            "precipitation_probability_pct": payload.weather.precipitation_probability_pct,
            "precipitation_mm": payload.weather.precipitation_mm,
            "visibility_km": payload.weather.visibility_km,
            "cloud_cover_pct": payload.weather.cloud_cover_pct,
            "condition": payload.weather.condition,
        }

    air_traffic_summary = _summarize_air_traffic(payload) or []
    aprs_summary = _summarize_aprs(payload) or []

    logger.info(
        "Building classification payload: signals=%s air_tracks=%s aprs_msgs=%s",
        len(signals_payload),
        len(payload.air_traffic or []),
        len(payload.aprs_messages or []),
    )

    return {
        "mission": {
            "mission_id": payload.mission_id,
            "mission_metadata": payload.mission_metadata,
        },
        "request": {
            "notes": request.notes,
        },
        "context": {
            "signals": signals_payload,
            "notes": payload.notes,
            "location": mission_location,
            "time_window": time_window,
            "weather_snapshot": weather_snapshot,
            "air_traffic_tracks": len(payload.air_traffic or []),
            "air_traffic_summary": air_traffic_summary,
            "aprs_messages": len(payload.aprs_messages or []),
            "aprs_summary": aprs_summary,
        },
        "candidate_intents": [
            {
                "id": intent.id.value,
                "label": intent.label,
                "description": intent.description,
                "guidance": intent.guidance,
            }
            for intent in _get_candidate_intents()
        ],
        "response_schema": {
            "intent_id": "One of the candidate intent IDs provided above.",
            "intent_label": "Human-readable label for the selected intent.",
            "summary": "Concise mission summary.",
            "risks": "List of notable risks.",
            "recommendations": "List of recommended actions.",
        },
    }


def _build_prompt_from_payload(payload: MissionContextPayload) -> str:
    """Construct a concise prompt for the AI model from structured context."""

    lines: list[str] = ["You are assisting a mission analyst."]
    if payload.mission_id:
        lines.append(f"Mission ID: {payload.mission_id}")
    if payload.mission_metadata:
        lines.append("Mission metadata:")
        for key, value in payload.mission_metadata.items():
            lines.append(f"- {key}: {value}")

    if payload.mission_location:
        loc = payload.mission_location
        loc_line = f"Location: {loc.latitude:.4f}, {loc.longitude:.4f}"
        if loc.description:
            loc_line = f"{loc_line} ({loc.description})"
        lines.append(loc_line)

    if payload.weather:
        weather = payload.weather
        lines.append(
            f"Weather as of {weather.as_of.isoformat()} UTC at {weather.latitude:.4f}, {weather.longitude:.4f}:"
        )
        if weather.temperature_c is not None:
            lines.append(f"- Temperature: {weather.temperature_c} C")
        if weather.wind_speed_mps is not None:
            wind_desc = f"- Wind: {weather.wind_speed_mps} m/s"
            if weather.wind_direction_deg is not None:
                wind_desc = f"{wind_desc} @ {weather.wind_direction_deg} deg"
            lines.append(wind_desc)
        if weather.precipitation_probability_pct is not None:
            lines.append(
                f"- Precipitation probability: {weather.precipitation_probability_pct}%"
            )
        if weather.precipitation_mm is not None:
            lines.append(f"- Precipitation: {weather.precipitation_mm} mm")
        if weather.visibility_km is not None:
            lines.append(f"- Visibility: {weather.visibility_km} km")
        if weather.cloud_cover_pct is not None:
            lines.append(f"- Cloud cover: {weather.cloud_cover_pct}%")
        if weather.condition:
            lines.append(f"- Condition code: {weather.condition}")

    if payload.signals:
        lines.append("Recent signals:")
        for signal in payload.signals:
            ts = signal.timestamp.isoformat() if signal.timestamp else "unspecified time"
            lines.append(
                f"- [{signal.type}] at {ts}: {signal.description or 'no description'}"
            )
            if signal.metadata:
                for meta_key, meta_value in signal.metadata.items():
                    lines.append(f"    * {meta_key}: {meta_value}")

    air_traffic_lines = _summarize_air_traffic(payload)
    if air_traffic_lines:
        lines.append("Nearby air traffic:")
        lines.extend(air_traffic_lines)

    aprs_lines = _summarize_aprs(payload)
    if aprs_lines:
        lines.append("Recent APRS radio traffic:")
        lines.extend(aprs_lines)

    if payload.notes:
        lines.append(f"Notes: {payload.notes}")

    lines.append(
        "Provide a short mission status summary and any immediate risks based on these signals."
    )
    return "\n".join(lines)


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance between two coordinates in nautical miles."""

    r_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        d_lambda / 2
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = r_km * c
    return distance_km * 0.539957


def _summarize_air_traffic(payload: MissionContextPayload) -> list[str] | None:
    tracks = payload.air_traffic or []
    if not tracks:
        return None

    lines: list[str] = []
    loc = payload.mission_location
    distances: list[tuple[AircraftTrack, float | None]] = []
    for track in tracks:
        if loc:
            dist_nm = _haversine_nm(loc.latitude, loc.longitude, track.lat, track.lon)
        else:
            dist_nm = None
        distances.append((track, dist_nm))

    bands = {"<=5k": 0, "5-10k": 0, "10-20k": 0, ">20k": 0}
    for track, _ in distances:
        if track.altitude is None:
            continue
        if track.altitude <= 5000:
            bands["<=5k"] += 1
        elif track.altitude <= 10000:
            bands["5-10k"] += 1
        elif track.altitude <= 20000:
            bands["10-20k"] += 1
        else:
            bands[">20k"] += 1

    if any(bands.values()):
        lines.append(
            "Altitude bands (ft): "
            f"<=5k:{bands['<=5k']}; 5-10k:{bands['5-10k']}; "
            f"10-20k:{bands['10-20k']}; >20k:{bands['>20k']}"
        )

    nearest: list[tuple[AircraftTrack, float | None]]
    if loc:
        nearest = sorted(distances, key=lambda t: t[1] if t[1] is not None else math.inf)[
            :3
        ]
    else:
        nearest = distances[:3]

    for track, dist_nm in nearest:
        ident = track.callsign or track.icao or "unknown"
        alt_desc = f"{int(track.altitude)} ft" if track.altitude is not None else "alt unknown"
        speed_desc = f", {track.ground_speed} kt" if track.ground_speed is not None else ""
        heading_desc = f", hdg {track.heading}" if track.heading is not None else ""
        distance_desc = (
            f", {dist_nm:.1f} nm from mission" if dist_nm is not None else ""
        )
        lines.append(f"- {ident}: {alt_desc}{speed_desc}{heading_desc}{distance_desc}")

    return lines


def _summarize_aprs(payload: MissionContextPayload) -> list[str] | None:
    messages = payload.aprs_messages or []
    if not messages:
        return None

    lines: list[str] = []
    for message in messages[:5]:
        time_desc = message.timestamp.isoformat()
        route = f"{message.source}->{message.destination}" if message.destination else message.source
        location_desc = (
            f" at {message.lat:.4f},{message.lon:.4f}"
            if message.lat is not None and message.lon is not None
            else ""
        )
        altitude_desc = (
            f" alt {int(message.altitude_m)} m" if message.altitude_m is not None else ""
        )
        text_desc = message.text or ""
        lines.append(
            f"- {route}{location_desc}{altitude_desc} at {time_desc}: {text_desc}".strip()
        )

    return lines


@dataclass
class MissionAnalysisResult:
    """Structured AI analysis result."""

    intent: MissionIntent
    summary: str
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


MissionIntentHandler = Callable[
    [MissionContextPayload, str | None], Awaitable[MissionAnalysisResult]
]


def _build_intent_prompt(
    payload: MissionContextPayload, intent: MissionIntent, intent_lines: list[str]
) -> str:
    base_prompt = _build_prompt_from_payload(payload)
    directive = "\n".join(intent_lines)
    return "\n\n".join([base_prompt, f"Intent: {intent.value}", directive])


async def _call_openai(prompt: str, system_message: str | None) -> str:
    try:
        return await openai_client.analyze_mission_context(
            prompt, system_message=system_message
        )
    except RuntimeError as exc:
        logger.error("AI analysis failed: %s", exc)
        return "AI analysis is currently unavailable. Please try again later."


async def _handle_situational_awareness(
    payload: MissionContextPayload, system_message: str | None
) -> MissionAnalysisResult:
    prompt = _build_intent_prompt(
        payload,
        MissionIntent.SITUATIONAL_AWARENESS,
        [
            "Provide a concise situational awareness summary.",
            "List notable risks and recommended immediate actions.",
        ],
    )
    response = await _call_openai(prompt, system_message)
    return MissionAnalysisResult(
        intent=MissionIntent.SITUATIONAL_AWARENESS,
        summary=response.strip(),
        risks=[],
        recommendations=[],
    )


async def _handle_route_risk_assessment(
    payload: MissionContextPayload, system_message: str | None
) -> MissionAnalysisResult:
    prompt = _build_intent_prompt(
        payload,
        MissionIntent.ROUTE_RISK_ASSESSMENT,
        [
            "Assess route and movement risks.",
            "Call out chokepoints, threats along the path, and mitigations.",
        ],
    )
    response = await _call_openai(prompt, system_message)
    return MissionAnalysisResult(
        intent=MissionIntent.ROUTE_RISK_ASSESSMENT,
        summary=response.strip(),
        risks=[],
        recommendations=[],
    )


async def _handle_weather_impact(
    payload: MissionContextPayload, system_message: str | None
) -> MissionAnalysisResult:
    prompt = _build_intent_prompt(
        payload,
        MissionIntent.WEATHER_IMPACT,
        [
            "Describe weather impacts on mission execution.",
            "Highlight hazards, timing, and operational constraints.",
        ],
    )
    response = await _call_openai(prompt, system_message)
    return MissionAnalysisResult(
        intent=MissionIntent.WEATHER_IMPACT,
        summary=response.strip(),
        risks=[],
        recommendations=[],
    )


async def _handle_airspace_deconfliction(
    payload: MissionContextPayload, system_message: str | None
) -> MissionAnalysisResult:
    prompt = _build_intent_prompt(
        payload,
        MissionIntent.AIRSPACE_DECONFLICTION,
        [
            "Provide an airspace deconfliction overview.",
            "Identify conflicting flight activity and coordination needs.",
        ],
    )
    response = await _call_openai(prompt, system_message)
    return MissionAnalysisResult(
        intent=MissionIntent.AIRSPACE_DECONFLICTION,
        summary=response.strip(),
        risks=[],
        recommendations=[],
    )

async def _handle_air_activity(
    payload: MissionContextPayload, system_message: str | None
) -> MissionAnalysisResult:
    prompt = _build_intent_prompt(
        payload,
        MissionIntent.AIR_ACTIVITY_ANALYSIS,
        [
            "Provide an airspace activity overview.",
            "Identify air traffic activity and report flight details.",
        ],
    )
    response = await _call_openai(prompt, system_message)
    return MissionAnalysisResult(
        intent=MissionIntent.AIR_ACTIVITY_ANALYSIS,
        summary=response.strip(),
        risks=[],
        recommendations=[],
    )

async def _handle_radio_signal_activity(
    payload: MissionContextPayload, system_message: str | None
) -> MissionAnalysisResult:
    prompt = _build_intent_prompt(
        payload,
        MissionIntent.RADIO_SIGNAL_ACTIVITY_ANALYSIS,
        [
            "Provide an overview of radio signal activity.",
            "Give specific radio signal data for the mission.",
        ],
    )
    response = await _call_openai(prompt, system_message)
    return MissionAnalysisResult(
        intent=MissionIntent.RADIO_SIGNAL_ACTIVITY_ANALYSIS,
        summary=response.strip(),
        risks=[],
        recommendations=[],
    )


INTENT_HANDLERS: dict[MissionIntent, MissionIntentHandler] = {
    MissionIntent.SITUATIONAL_AWARENESS: _handle_situational_awareness,
    MissionIntent.ROUTE_RISK_ASSESSMENT: _handle_route_risk_assessment,
    MissionIntent.WEATHER_IMPACT: _handle_weather_impact,
    MissionIntent.AIRSPACE_DECONFLICTION: _handle_airspace_deconfliction,
    MissionIntent.AIR_ACTIVITY_ANALYSIS: _handle_air_activity,
    MissionIntent.RADIO_SIGNAL_ACTIVITY_ANALYSIS: _handle_radio_signal_activity,

}


async def analyze_mission(
    payload: MissionContextPayload,
    *,
    system_message: str | None = None,
    intent: MissionIntent = DEFAULT_INTENT,
) -> MissionAnalysisResult:
    """Analyze mission context using the AI client wrapper with intent routing."""

    handler = INTENT_HANDLERS.get(intent)
    if handler is None:
        raise ValueError(f"Unsupported mission intent: {intent}")

    return await handler(payload, system_message)


async def analyze_mission_auto_intent(
    request: MissionAnalysisRequest,
    payload: MissionContextPayload,
    *,
    system_message: str | None = None,
) -> MissionAnalysisResult:
    """Perform intent classification and mission analysis in a single OpenAI call."""

    classification_payload = _build_classification_payload(payload, request)
    system_prompt = system_message or (
        "You are SentinelAI, an assistant for mission analysts. Given candidate intents "
        "and mission context, select the single best intent and perform the mission analysis *strictly according* to that intent’s guidance. "
        "Respond ONLY with a JSON object containing intent_id, intent_label, summary, "
        "risks (list of strings), and recommendations (list of strings)."
        "Your analysis must be concrete, not vague."
        "Never invent data beyond what is provided."
    )

    try:
        result_data = await openai_client.analyze_mission_with_intent_single_call(
            model=settings.openai_model,
            system_message=system_prompt,
            classification_payload=classification_payload,
        )
        intent_id = result_data.get("intent_id")
        intent_label = result_data.get("intent_label")
        summary = result_data.get("summary") or ""
        risks = result_data.get("risks") or []
        recommendations = result_data.get("recommendations") or []

        if not isinstance(risks, list):
            risks = [str(risks)]
        if not isinstance(recommendations, list):
            recommendations = [str(recommendations)]

        selected_intent = MissionIntent(intent_id) if intent_id else DEFAULT_INTENT
        logger.info(
            "AI selected intent: id=%s label=%s", intent_id, intent_label or selected_intent
        )
        return MissionAnalysisResult(
            intent=selected_intent,
            summary=summary.strip(),
            risks=list(risks),
            recommendations=list(recommendations),
        )
    except (ValueError, RuntimeError) as exc:
        logger.error("AI classification+analysis failed: %s", exc)
        return MissionAnalysisResult(
            intent=DEFAULT_INTENT,
            summary="AI analysis is currently unavailable. Please try again later.",
            risks=[],
            recommendations=[],
        )


__all__ = [
    "AnalysisEngine",
    "AnalysisResult",
    "RuleBasedAnalysisEngine",
    "MissionSignal",
    "MissionLocationPayload",
    "MissionContextPayload",
    "MissionAnalysisResult",
    "MissionIntent",
    "INTENT_HANDLERS",
    "analyze_mission_auto_intent",
    "analyze_mission",
    "get_analysis_engine",
]

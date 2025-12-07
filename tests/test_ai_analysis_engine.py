from datetime import datetime
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain import MissionIntent
from app.models.air_traffic import AircraftTrack
from app.models.weather import WeatherSnapshot
from app.services import analysis_engine
from app.services.analysis_engine import (
    MissionAnalysisResult,
    MissionContextPayload,
    MissionLocationPayload,
    MissionSignal,
)


@pytest.mark.anyio
async def test_analyze_mission_calls_wrapper(monkeypatch):
    captured = {}

    async def fake_analyze(prompt: str, *, system_message: str | None = None) -> str:
        captured["prompt"] = prompt
        captured["system_message"] = system_message
        return "analysis-ok"

    monkeypatch.setattr(analysis_engine.openai_client, "analyze_mission_context", fake_analyze)

    payload = MissionContextPayload(
        mission_id="mission-123",
        mission_metadata={"team": "Alpha", "priority": "high"},
        signals=[
            MissionSignal(
                type="movement",
                description="Possible hostile movement detected",
                timestamp=datetime(2024, 1, 1, 12, 0, 0),
                metadata={"bearing": 180},
            )
        ],
        notes="Watch south approach",
    )

    response = await analysis_engine.analyze_mission(
        payload,
        system_message="System guardrails",
        intent=MissionIntent.SITUATIONAL_AWARENESS,
    )

    assert isinstance(response, MissionAnalysisResult)
    assert response.summary == "analysis-ok"
    assert response.intent == MissionIntent.SITUATIONAL_AWARENESS
    assert "mission-123" in captured["prompt"]
    assert "movement" in captured["prompt"]
    assert "Intent: SITUATIONAL_AWARENESS" in captured["prompt"]
    assert captured["system_message"] == "System guardrails"


@pytest.mark.anyio
async def test_analyze_mission_handles_errors(monkeypatch, caplog):
    async def failing_analyze(prompt: str, *, system_message: str | None = None) -> str:
        raise RuntimeError("upstream failure")

    monkeypatch.setattr(analysis_engine.openai_client, "analyze_mission_context", failing_analyze)

    payload = MissionContextPayload(mission_id=None, mission_metadata=None, signals=None, notes=None)

    with caplog.at_level("ERROR"):
        result = await analysis_engine.analyze_mission(payload)

    assert "AI analysis failed" in caplog.text
    assert isinstance(result, MissionAnalysisResult)
    assert "unavailable" in result.summary.lower()


@pytest.mark.anyio
async def test_analyze_mission_routes_by_intent(monkeypatch):
    prompts: dict[MissionIntent, str] = {}

    async def fake_analyze(prompt: str, *, system_message: str | None = None) -> str:
        for intent in MissionIntent:
            if intent.value in prompt:
                prompts[intent] = prompt
        return "ok"

    monkeypatch.setattr(
        analysis_engine.openai_client, "analyze_mission_context", fake_analyze
    )

    payload = MissionContextPayload(
        mission_id="mission-456", mission_metadata=None, signals=None, notes=None
    )

    for intent in MissionIntent:
        result = await analysis_engine.analyze_mission(payload, intent=intent)
        assert result.intent == intent
        assert intent in prompts
        assert intent.value in prompts[intent]


@pytest.mark.anyio
async def test_analyze_mission_rejects_unknown_intent():
    payload = MissionContextPayload(mission_id=None, mission_metadata=None, signals=None, notes=None)

    class FakeIntent:
        value = "UNKNOWN"

    with pytest.raises(ValueError):
        await analysis_engine.analyze_mission(payload, intent=FakeIntent())


@pytest.mark.anyio
async def test_prompt_includes_weather(monkeypatch):
    captured_prompt: dict[str, str] = {}

    async def fake_analyze(prompt: str, *, system_message: str | None = None) -> str:
        captured_prompt["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(analysis_engine.openai_client, "analyze_mission_context", fake_analyze)

    weather = WeatherSnapshot(
        latitude=10.0,
        longitude=20.0,
        as_of=datetime(2024, 1, 1, 0, 0, 0),
        temperature_c=5.0,
        wind_speed_mps=3.2,
        wind_direction_deg=120,
        precipitation_probability_pct=40,
        precipitation_mm=1.2,
        visibility_km=8.5,
        cloud_cover_pct=80,
        condition="rain",
    )

    payload = MissionContextPayload(
        mission_id="mission-weather",
        mission_metadata=None,
        signals=None,
        notes=None,
        mission_location=MissionLocationPayload(latitude=10.0, longitude=20.0, description=None),
        weather=weather,
    )

    result = await analysis_engine.analyze_mission(payload, intent=MissionIntent.WEATHER_IMPACT)

    assert result.intent == MissionIntent.WEATHER_IMPACT
    assert "Weather as of" in captured_prompt["prompt"]
    assert "Temperature" in captured_prompt["prompt"]
    assert "rain" in captured_prompt["prompt"]


@pytest.mark.anyio
async def test_prompt_includes_air_traffic(monkeypatch):
    captured_prompt: dict[str, str] = {}

    async def fake_analyze(prompt: str, *, system_message: str | None = None) -> str:
        captured_prompt["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(analysis_engine.openai_client, "analyze_mission_context", fake_analyze)

    tracks = [
        AircraftTrack(
            callsign="AIR1",
            icao="ABC",
            lat=10.1,
            lon=20.1,
            altitude=8000,
            ground_speed=250,
            heading=90,
        ),
        AircraftTrack(
            callsign="AIR2",
            icao="DEF",
            lat=10.2,
            lon=20.2,
            altitude=15000,
            ground_speed=300,
            heading=180,
        ),
    ]

    payload = MissionContextPayload(
        mission_id="mission-air",
        mission_metadata=None,
        signals=None,
        notes=None,
        mission_location=MissionLocationPayload(latitude=10.0, longitude=20.0, description=None),
        air_traffic=tracks,
    )

    result = await analysis_engine.analyze_mission(payload, intent=MissionIntent.AIRSPACE_DECONFLICTION)

    assert result.intent == MissionIntent.AIRSPACE_DECONFLICTION
    assert "Nearby air traffic" in captured_prompt["prompt"]
    assert "AIR1" in captured_prompt["prompt"]
    assert "Altitude bands" in captured_prompt["prompt"]


@pytest.mark.anyio
async def test_prompt_skips_air_traffic_when_absent(monkeypatch):
    captured_prompt: dict[str, str] = {}

    async def fake_analyze(prompt: str, *, system_message: str | None = None) -> str:
        captured_prompt["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(analysis_engine.openai_client, "analyze_mission_context", fake_analyze)

    payload = MissionContextPayload(
        mission_id="mission-air",
        mission_metadata=None,
        signals=None,
        notes=None,
        mission_location=MissionLocationPayload(latitude=10.0, longitude=20.0, description=None),
        air_traffic=None,
    )

    result = await analysis_engine.analyze_mission(payload, intent=MissionIntent.AIRSPACE_DECONFLICTION)

    assert result.intent == MissionIntent.AIRSPACE_DECONFLICTION
    assert "Nearby air traffic" not in captured_prompt["prompt"]

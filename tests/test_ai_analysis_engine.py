from datetime import datetime
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain import MissionIntent
from app.services import analysis_engine
from app.services.analysis_engine import (
    MissionAnalysisResult,
    MissionContextPayload,
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

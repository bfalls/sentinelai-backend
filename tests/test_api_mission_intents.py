from pathlib import Path
import sys
import importlib.util
from typing import Any

import pytest

if importlib.util.find_spec("sqlalchemy") is None:  # pragma: no cover - optional dependency guard
    pytest.skip("SQLAlchemy is required for API intent tests", allow_module_level=True)
import sqlalchemy  # noqa: F401

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api import analysis as analysis_module
from app.domain import DEFAULT_INTENT, MissionIntent
from app.models.analysis import MissionAnalysisRequest
from app.services.analysis_engine import MissionAnalysisResult, MissionContextPayload


@pytest.mark.anyio
async def test_mission_analysis_defaults_intent(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_analyze(payload: MissionContextPayload, *, intent, system_message=None):
        captured["intent"] = intent
        return MissionAnalysisResult(intent=intent, summary="ok", risks=[], recommendations=[])

    monkeypatch.setattr(analysis_module, "analyze_mission", fake_analyze)

    request = MissionAnalysisRequest(mission_id="abc")
    response = await analysis_module.analyze_mission_context(request)

    assert response.intent == DEFAULT_INTENT
    assert captured["intent"] == DEFAULT_INTENT


@pytest.mark.anyio
async def test_mission_analysis_respects_intent(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_analyze(payload: MissionContextPayload, *, intent, system_message=None):
        captured["intent"] = intent
        return MissionAnalysisResult(intent=intent, summary="ok", risks=[], recommendations=[])

    monkeypatch.setattr(analysis_module, "analyze_mission", fake_analyze)

    request = MissionAnalysisRequest(mission_id="abc", intent=MissionIntent.ROUTE_RISK_ASSESSMENT)
    response = await analysis_module.analyze_mission_context(request)

    assert response.intent == MissionIntent.ROUTE_RISK_ASSESSMENT
    assert captured["intent"] == MissionIntent.ROUTE_RISK_ASSESSMENT


@pytest.mark.anyio
async def test_mission_analysis_rejects_unknown_intent(monkeypatch):
    # model_construct bypasses validation to simulate malformed request
    request = MissionAnalysisRequest.model_construct(mission_id="abc", intent="UNKNOWN")

    async def fake_analyze(payload: MissionContextPayload, *, intent, system_message=None):
        raise ValueError(f"Unsupported mission intent: {intent}")

    monkeypatch.setattr(analysis_module, "analyze_mission", fake_analyze)

    with pytest.raises(Exception) as exc_info:
        await analysis_module.analyze_mission_context(request)

    assert "Unsupported mission intent" in str(exc_info.value)

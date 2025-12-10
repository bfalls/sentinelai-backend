from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import db_models
from app.api import analysis as analysis_module
from app.config import settings
from app.db import SessionLocal, init_db
from app.domain import MissionIntent
from app.main import app
from app.services.analysis_engine import MissionAnalysisResult, MissionContextPayload


@pytest.mark.anyio
async def test_analysis_includes_aprs_messages(monkeypatch):
    monkeypatch.setattr(settings, "enable_weather_ingestor", False)
    monkeypatch.setattr(settings, "enable_adsb_ingestor", False)
    monkeypatch.setattr(settings, "aprs_enabled", True)

    init_db()
    session = SessionLocal()
    try:
        session.add(
            db_models.EventRecord(
                id="aprs-api-1",
                event_type="aprs",
                mission_id="mission-123",
                description="APRS payload",
                source="N0CALL",
                timestamp=datetime.utcnow(),
                event_metadata={
                    "source_callsign": "N0CALL",
                    "lat": 10.0,
                    "lon": 20.0,
                    "text": "hello world",
                },
            )
        )
        session.commit()

        captured: dict[str, MissionContextPayload] = {}

        async def fake_analyze_auto(
            request_payload, payload: MissionContextPayload, *, system_message=None
        ):
            captured["payload"] = payload
            return MissionAnalysisResult(
                intent=request_payload.intent or MissionIntent.SITUATIONAL_AWARENESS,
                summary="ok",
                risks=[],
                recommendations=[],
            )

        monkeypatch.setattr(analysis_module, "analyze_mission_auto_intent", fake_analyze_auto)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analysis/mission",
                json={
                    "mission_id": "mission-123",
                    "location": {"latitude": 10.0, "longitude": 20.0},
                },
            )

        assert response.status_code == 200
        assert "payload" in captured
        aprs = captured["payload"].aprs_messages
        assert aprs is not None
        assert len(aprs) == 1
        assert aprs[0].source == "N0CALL"
    finally:
        session.query(db_models.EventRecord).delete()
        session.commit()
        session.close()

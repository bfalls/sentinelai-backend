import asyncio
import json
from datetime import datetime, timedelta

import anyio
import httpx
import pytest

from app.ingestors.aprs import APRSConfig, APRSIngestor, parse_aprs_packet
from app.security.api_keys import API_KEY_HEADER


def test_parse_aprs_packet_parses_position():
    line = "N0CALL>APRS,TCPIP*:4903.50N/07201.75W>Test message /A=001234"
    message = parse_aprs_packet(line)

    assert message is not None
    assert message.source == "N0CALL"
    assert pytest.approx(message.lat, rel=1e-3) == 49.0583
    assert pytest.approx(message.lon, rel=1e-3) == -72.0291
    assert pytest.approx(message.altitude_m, rel=1e-3) == 375.9392
    assert "Test message" in (message.text or "")


def test_parse_aprs_packet_ignores_comments_and_invalid():
    assert parse_aprs_packet("# comment line") is None
    assert parse_aprs_packet("invalid packet") is None


@pytest.mark.anyio
async def test_aprs_ingestor_posts_events(monkeypatch):
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(201, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        config = APRSConfig(
            host="example.com",
            port=14580,
            callsign="TEST",
            passcode="12345",
        )

        async def fake_line_source():
            yield "N0CALL>APRS,TCPIP*:4903.50N/07201.75W>Test message /A=001234"
            yield "# ignored"

        ingestor = APRSIngestor(
            config=config,
            http_client=client,
            api_key="test_ingestor_key",
            line_source=fake_line_source,
            stop_on_source=True,
        )

        with anyio.fail_after(5):
            await ingestor.run()

    assert len(captured) == 1
    assert captured[0].headers.get(API_KEY_HEADER) == "test_ingestor_key"
    body = json.loads(captured[0].content.decode())
    assert body["event_type"] == "aprs"
    assert body["event_metadata"]["source_callsign"] == "N0CALL"
    assert pytest.approx(body["event_metadata"]["lat"], rel=1e-3) == 49.0583
    assert pytest.approx(body["event_metadata"]["lon"], rel=1e-3) == -72.0291
    timestamp = datetime.fromisoformat(body["timestamp"])
    assert timestamp <= datetime.now(tz=timestamp.tzinfo) + timedelta(seconds=5)

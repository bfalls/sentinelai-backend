from datetime import datetime, timezone

import httpx
import pytest

from app.ingestors.adsb import ADSBIngestor


@pytest.mark.anyio
async def test_adsb_ingestor_parses_tracks():
    payload = {
        "time": 1714765200,
        "states": [
            [
                "abc123",  # icao24
                "TEST123 ",  # callsign with trailing space
                "USA",
                1714765198,  # time_position
                1714765200,  # last_contact
                20.0,  # longitude
                10.0,  # latitude
                3657.6,  # baro_altitude meters
                False,  # on_ground
                164.6,  # velocity m/s
                90.0,  # true_track
                2.0,  # vertical_rate m/s
                None,  # sensors
                3700.0,  # geo_altitude meters
                "7000",  # squawk
                False,  # spi
                0,  # position_source
            ]
        ],
    }

    def handler(request: httpx.Request):
        assert "lamin" in request.url.params
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    ingestor = ADSBIngestor(base_url="https://example.test", transport=transport)

    tracks = await ingestor.get_air_traffic(10.0, 20.0, radius_nm=50.0)

    assert len(tracks) == 1
    track = tracks[0]
    assert track.callsign == "TEST123"
    assert track.icao == "ABC123"
    assert track.altitude == pytest.approx(12139.108)
    assert track.ground_speed == pytest.approx(319.7, rel=1e-3)
    assert track.heading == 90
    assert track.vertical_rate == pytest.approx(393.7008, rel=1e-3)
    assert track.last_seen == datetime(2024, 5, 3, 19, 40, tzinfo=timezone.utc)


@pytest.mark.anyio
async def test_adsb_ingestor_handles_rate_limit():
    def handler(request: httpx.Request):
        return httpx.Response(429, text="rate limited")

    transport = httpx.MockTransport(handler)
    ingestor = ADSBIngestor(base_url="https://example.test", transport=transport)

    tracks = await ingestor.get_air_traffic(0.0, 0.0, radius_nm=10.0)

    assert tracks == []


@pytest.mark.anyio
async def test_adsb_ingestor_handles_error_response():
    def handler(request: httpx.Request):
        return httpx.Response(503, text="unavailable")

    transport = httpx.MockTransport(handler)
    ingestor = ADSBIngestor(base_url="https://example.test", transport=transport)

    tracks = await ingestor.get_air_traffic(0.0, 0.0)

    assert tracks == []

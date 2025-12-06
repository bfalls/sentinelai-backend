import httpx
import pytest

from app.ingestors.weather import WeatherIngestor
from app.models.weather import TimeWindow


@pytest.mark.anyio
async def test_weather_ingestor_parses_current_weather(monkeypatch):
    payload = {
        "latitude": 10.0,
        "longitude": 20.0,
        "current_weather": {
            "temperature": 12.5,
            "windspeed": 4.2,
            "winddirection": 90,
            "weathercode": 63,
            "time": "2024-01-01T00:00",
        },
        "hourly": {
            "time": ["2024-01-01T00:00"],
            "precipitation_probability": [55],
            "precipitation": [1.0],
            "visibility": [10000],
            "cloudcover": [80],
        },
    }

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_client)

    ingestor = WeatherIngestor(base_url="http://test-weather")
    snapshot = await ingestor.get_weather(10.0, 20.0)

    assert snapshot.temperature_c == 12.5
    assert snapshot.wind_speed_mps == 4.2
    assert snapshot.wind_direction_deg == 90
    assert snapshot.precipitation_probability_pct == 55
    assert snapshot.precipitation_mm == 1.0
    assert snapshot.visibility_km == 10.0
    assert snapshot.cloud_cover_pct == 80


@pytest.mark.anyio
async def test_weather_ingestor_handles_http_error(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_client)

    ingestor = WeatherIngestor(base_url="http://test-weather")
    with pytest.raises(RuntimeError):
        await ingestor.get_weather(1.0, 2.0)


@pytest.mark.anyio
async def test_weather_ingestor_handles_timeout(monkeypatch):
    class TimeoutClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "AsyncClient", TimeoutClient)

    ingestor = WeatherIngestor(base_url="http://test-weather")
    with pytest.raises(RuntimeError):
        await ingestor.get_weather(1.0, 2.0, time_window=TimeWindow())

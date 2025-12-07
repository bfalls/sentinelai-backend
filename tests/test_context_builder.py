from datetime import datetime

import pytest

from app.config import settings
from app.models.air_traffic import AircraftTrack
from app.models.analysis import MissionAnalysisRequest, MissionLocation, MissionSignalModel
from app.models.weather import WeatherSnapshot
from app.services.context_builder import ContextBuilder


class FakeWeatherIngestor:
    def __init__(self, snapshot: WeatherSnapshot | None = None, fail: bool = False):
        self.snapshot = snapshot
        self.fail = fail
        self.call_count = 0

    async def get_weather(self, lat: float, lon: float, time_window=None):
        self.call_count += 1
        if self.fail:
            raise RuntimeError("fail")
        return self.snapshot


class FakeADSBIngestor:
    def __init__(self, tracks: list[AircraftTrack] | None = None, fail: bool = False):
        self.tracks = tracks or []
        self.fail = fail
        self.call_count = 0

    async def get_air_traffic(self, lat: float, lon: float, radius_nm=None):
        self.call_count += 1
        if self.fail:
            raise RuntimeError("adsb fail")
        return self.tracks


@pytest.mark.anyio
async def test_context_builder_adds_weather(monkeypatch):
    monkeypatch.setattr(settings, "enable_weather_ingestor", True)
    monkeypatch.setattr(settings, "enable_adsb_ingestor", False)
    snapshot = WeatherSnapshot(
        latitude=1.0,
        longitude=2.0,
        as_of=datetime(2024, 1, 1, 0, 0, 0),
        temperature_c=15.0,
        wind_speed_mps=2.0,
        wind_direction_deg=180,
        precipitation_probability_pct=10,
        precipitation_mm=0.2,
        visibility_km=10.0,
        cloud_cover_pct=20,
        condition="clear",
    )
    ingestor = FakeWeatherIngestor(snapshot=snapshot)
    builder = ContextBuilder(weather_ingestor=ingestor)

    request = MissionAnalysisRequest(
        mission_id="m1",
        mission_metadata={"team": "alpha"},
        signals=[MissionSignalModel(type="movement", description="desc")],
        location=MissionLocation(latitude=1.0, longitude=2.0),
    )

    payload = await builder.build_context_payload(request)

    assert payload.weather == snapshot
    assert payload.mission_location is not None
    assert payload.mission_location.latitude == 1.0
    assert payload.mission_location.longitude == 2.0
    assert ingestor.call_count == 1


@pytest.mark.anyio
async def test_context_builder_graceful_on_failure(monkeypatch):
    monkeypatch.setattr(settings, "enable_weather_ingestor", True)
    monkeypatch.setattr(settings, "enable_adsb_ingestor", False)
    ingestor = FakeWeatherIngestor(fail=True)
    builder = ContextBuilder(weather_ingestor=ingestor)

    request = MissionAnalysisRequest(
        mission_id="m1",
        signals=None,
        location=MissionLocation(latitude=1.0, longitude=2.0),
    )

    payload = await builder.build_context_payload(request)

    assert payload.weather is None
    assert ingestor.call_count == 1


@pytest.mark.anyio
async def test_context_builder_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "enable_weather_ingestor", False)
    monkeypatch.setattr(settings, "enable_adsb_ingestor", False)
    snapshot = WeatherSnapshot(
        latitude=1.0,
        longitude=2.0,
        as_of=datetime(2024, 1, 1, 0, 0, 0),
    )
    ingestor = FakeWeatherIngestor(snapshot=snapshot)
    builder = ContextBuilder(weather_ingestor=ingestor)

    request = MissionAnalysisRequest(
        mission_id="m1",
        signals=None,
        location=MissionLocation(latitude=1.0, longitude=2.0),
    )

    payload = await builder.build_context_payload(request)

    assert payload.weather is None
    assert ingestor.call_count == 0


@pytest.mark.anyio
async def test_context_builder_adds_adsb(monkeypatch):
    monkeypatch.setattr(settings, "enable_weather_ingestor", False)
    monkeypatch.setattr(settings, "enable_adsb_ingestor", True)
    tracks = [
        AircraftTrack(
            callsign="AIR1",
            icao="ABC",
            lat=1.0,
            lon=2.0,
            altitude=10000,
        )
    ]
    adsb_ingestor = FakeADSBIngestor(tracks=tracks)
    builder = ContextBuilder(weather_ingestor=FakeWeatherIngestor(), adsb_ingestor=adsb_ingestor)

    request = MissionAnalysisRequest(
        mission_id="m1",
        signals=None,
        location=MissionLocation(latitude=1.0, longitude=2.0),
    )

    payload = await builder.build_context_payload(request)

    assert payload.air_traffic == tracks
    assert adsb_ingestor.call_count == 1


@pytest.mark.anyio
async def test_context_builder_handles_adsb_failure(monkeypatch):
    monkeypatch.setattr(settings, "enable_weather_ingestor", False)
    monkeypatch.setattr(settings, "enable_adsb_ingestor", True)
    adsb_ingestor = FakeADSBIngestor(fail=True)
    builder = ContextBuilder(weather_ingestor=FakeWeatherIngestor(), adsb_ingestor=adsb_ingestor)

    request = MissionAnalysisRequest(
        mission_id="m1",
        signals=None,
        location=MissionLocation(latitude=1.0, longitude=2.0),
    )

    payload = await builder.build_context_payload(request)

    assert payload.air_traffic is None
    assert adsb_ingestor.call_count == 1


@pytest.mark.anyio
async def test_context_builder_skips_adsb_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "enable_weather_ingestor", False)
    monkeypatch.setattr(settings, "enable_adsb_ingestor", False)
    adsb_ingestor = FakeADSBIngestor(tracks=[])
    builder = ContextBuilder(weather_ingestor=FakeWeatherIngestor(), adsb_ingestor=adsb_ingestor)

    request = MissionAnalysisRequest(
        mission_id="m1",
        signals=None,
        location=MissionLocation(latitude=1.0, longitude=2.0),
    )

    payload = await builder.build_context_payload(request)

    assert payload.air_traffic is None
    assert adsb_ingestor.call_count == 0

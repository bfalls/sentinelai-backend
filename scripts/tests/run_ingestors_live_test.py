#!/usr/bin/env python
"""
Run this to exercise the live weather and ADS-B ingestors without calling OpenAI.

Usage (from repo root):
    python scripts/tests/run_ingestors_live_test.py
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.ingestors import WeatherIngestor, ADSBIngestor
from app.models.weather import TimeWindow


# Boise, Idaho (matches what you’ve been using)
LAT = 43.6173
LON = -116.2035


async def main() -> None:
    now = datetime.now(timezone.utc)

    # Narrow window; WeatherIngestor mostly needs dates, but this keeps it explicit
    time_window = TimeWindow(
        start=now,
        end=now + timedelta(hours=1),
    )

    weather_ingestor = WeatherIngestor()
    adsb_ingestor = ADSBIngestor()

    print(f"=== Live weather + air traffic test for {LAT}, {LON} (UTC now: {now.isoformat()}) ===\n")

    # --- Weather ---
    print("Requesting weather from Open-Meteo...")
    weather = await weather_ingestor.get_weather(LAT, LON, time_window)
    print("\nWeatherSnapshot:")
    # Pydantic model: use model_dump for a clean dict
    print(weather.model_dump())

    # --- ADS-B / air traffic ---
    print("\nRequesting nearby aircraft from OpenSky...")
    tracks = await adsb_ingestor.get_air_traffic(LAT, LON)

    if not tracks:
        print("\nNo aircraft tracks returned.")
    else:
        print(f"\nReceived {len(tracks)} aircraft tracks. Showing a few:")
        for idx, t in enumerate(tracks[:5], start=1):
            # AircraftTrack model fields: callsign, icao, lat, lon, altitude, ground_speed, heading, vertical_rate, last_seen
            print(
                f"{idx}. callsign={t.callsign!r}, icao={t.icao!r}, "
                f"lat={t.lat:.5f}, lon={t.lon:.5f}, "
                f"alt_ft={t.altitude}, gs_kt={t.ground_speed}, "
                f"hdg={t.heading}, vr_fpm={t.vertical_rate}, "
                f"last_seen={t.last_seen}"
            )


if __name__ == "__main__":
    asyncio.run(main())

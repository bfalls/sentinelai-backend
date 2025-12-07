#!/usr/bin/env python
# Run this with `npm run api-smoke`
# Note this is only intented to run against a local dev server, not prod.
import importlib.util
import json
from datetime import datetime, timedelta, timezone

pytest = None
if importlib.util.find_spec("pytest") is not None:  # pragma: no cover - optional dependency guard
    import pytest

if importlib.util.find_spec("requests") is None:  # pragma: no cover - handled for test collection
    if pytest is not None:
        pytest.skip("requests is required for smoke test", allow_module_level=True)
    requests = None
else:
    import requests

BASE_URL = "http://localhost:8000"
MISSION_ID = "Smoke Test Mission"
SOURCE = "smoke-test"

def require_requests():
    """
    Return the requests module or raise if it's unavailable.

    This function gives Pylance a non-optional object to work with so
    calls like .get() / .post() don't trigger Optional member warnings.
    """
    if requests is None:  # pragma: no cover - runtime guard
        raise RuntimeError("requests library required for smoke test")
    return requests

def check_server_health() -> None:
    """Ensure the API server is up before running the smoke test."""
    req = require_requests()
    
    url = f"{BASE_URL}/healthz"
    print(f"Checking API health at {url} ...")
    try:
        resp = req.get(url, timeout=5)
    except Exception as exc:
        raise SystemExit(f"ERROR: The server is probably not running. Failed to reach {url}: {exc}")

    if resp.status_code != 200:
        raise SystemExit(f"ERROR: {url} returned {resp.status_code}: {resp.text}")

    try:
        payload = resp.json()
    except Exception:
        payload = {}

    if not isinstance(payload, dict) or payload.get("status") != "ok" or payload.get("env", "unknown") in ("prod",):
        raise SystemExit(f"ERROR: unexpected /healthz payload: {payload}")

    print("Health check OK.\n")

def build_test_events():
    """
    Build ~10 events over the last ~30 minutes for a single mission.
    Newest event is 'now', older ones are spaced 3 minutes apart.
    """
    now = datetime.now(timezone.utc)

    descriptions = [
        "Unknown vehicle approaching south perimeter",
        "Patrol reports increased foot traffic near gate",
        "Thermal sensor detected heat signature near fence line",
        "Camera detected possible drone at low altitude",
        "Guard reports suspicious activity near loading dock",
        "Vehicle stopped near restricted entrance",
        "Motion detected behind storage building",
        "Unidentified radio chatter on local frequency",
        "Perimeter sensor triggered twice in rapid succession",
        "Vehicle left perimeter heading west",
    ]

    types = [
        "movement",
        "patrol_report",
        "sensor",
        "drone",
        "patrol_report",
        "movement",
        "movement",
        "signal_intel",
        "sensor",
        "movement",
    ]

    events = []
    for i in range(len(descriptions)):
        ts = now - timedelta(minutes=3 * i)
        event = {
            "event_type": types[i],
            "description": descriptions[i],
            "mission_id": MISSION_ID,
            "source": SOURCE,
            "timestamp": ts.isoformat(),
            "event_metadata": {
                "index": i,
                "priority": "high" if types[i] in ("movement", "sensor", "drone") else "medium",
            },
        }
        events.append(event)
        
    # Add a couple of synthetic air traffic events so the database contains
    # examples of flight-related activity for this mission.
    flight_events = [
        {
            "event_type": "air_traffic",
            "description": "Small aircraft orbiting near mission area",
            "mission_id": MISSION_ID,
            "source": SOURCE,
            "timestamp": now.isoformat(),
            "event_metadata": {
                "callsign": "N945MC",
                "icao": "AD20D1",
                "altitude_ft": 4500,
                "ground_speed_kt": 120,
            },
        },
        {
            "event_type": "air_traffic",
            "description": "Regional flight passing overhead",
            "mission_id": MISSION_ID,
            "source": SOURCE,
            "timestamp": (now - timedelta(minutes=2)).isoformat(),
            "event_metadata": {
                "callsign": "QXE2032",
                "altitude_ft": 12000,
                "ground_speed_kt": 320,
            },
        },
    ]
    events.extend(flight_events)
    
    # Add a couple of synthetic APRS events so the database contains examples
    # of radio-style traffic for this mission as well.
    aprs_events = [
        {
            "event_type": "aprs",
            "description": "APRS weather station near mission area",
            "mission_id": MISSION_ID,
            "source": "aprs_smoke",
            "timestamp": now.isoformat(),
            "event_metadata": {
                "source_callsign": "TESTWX-1",
                "dest_callsign": "APRS",
                "lat": 43.615,
                "lon": -116.202,
                "altitude_m": 820.0,
                "text": "@000000z4336.15N/11612.02W_090/005g010t070r000p000P000h50b10150AmbientWX",
                "raw_packet": "TESTWX-1>APRS,TCPIP*:@000000z4336.15N/11612.02W_090/005g010t070r000p000P000h50b10150AmbientWX",
            },
        },
        {
            "event_type": "aprs",
            "description": "APRS mobile station reporting position",
            "mission_id": MISSION_ID,
            "source": "aprs_smoke",
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "event_metadata": {
                "source_callsign": "TESTCAR-1",
                "dest_callsign": "APRS",
                "lat": 43.60,
                "lon": -116.25,
                "altitude_m": 840.0,
                "text": "!4336.00N/11615.00W>Moving through mission area",
                "raw_packet": "TESTCAR-1>APRS,TCPIP*:!4336.00N/11615.00W>Moving through mission area",
            },
        },
    ]
    events.extend(aprs_events)

    return events


def post_events(events):
    req = require_requests()
    print(f"Posting {len(events)} events to {BASE_URL}/api/v1/events ...")
    ids = []
    for e in events:
        resp = req.post(f"{BASE_URL}/api/v1/events", json=e)
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        print(f"  POST /events -> {resp.status_code}: {data}")
        if isinstance(data, dict) and "id" in data:
            ids.append(data["id"])
    return ids


def get_analysis_status():
    req = require_requests()
    params = {"mission_id": MISSION_ID, "window_minutes": 60}
    resp = req.get(f"{BASE_URL}/api/v1/analysis/status", params=params)
    try:
        data = resp.json()
    except Exception:
        data = resp.text

    print("\n=== Analysis status response ===")
    print(f"GET /analysis/status -> {resp.status_code}")
    print(json.dumps(data, indent=2, default=str))


def main():
    _ = require_requests()

    check_server_health()
    events = build_test_events()
    post_events(events)
    get_analysis_status()
    print("\n(If you want to clear these out, use your dev DB reset script.)")


if __name__ == "__main__":
    main()

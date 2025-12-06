#!/usr/bin/env python
import json
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = "http://localhost:8000"
MISSION_ID = "Grocery Store"


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
            "source": "smoke-test",
            "timestamp": ts.isoformat(),
            "event_metadata": {
                "index": i,
                "priority": "high" if types[i] in ("movement", "sensor", "drone") else "medium",
            },
        }
        events.append(event)

    return events


def post_events(events):
    print(f"Posting {len(events)} events to {BASE_URL}/api/v1/events ...")
    ids = []
    for e in events:
        resp = requests.post(f"{BASE_URL}/api/v1/events", json=e)
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        print(f"  POST /events -> {resp.status_code}: {data}")
        if isinstance(data, dict) and "id" in data:
            ids.append(data["id"])
    return ids


def get_analysis_status():
    params = {"mission_id": MISSION_ID, "window_minutes": 60}
    resp = requests.get(f"{BASE_URL}/api/v1/analysis/status", params=params)
    try:
        data = resp.json()
    except Exception:
        data = resp.text

    print("\n=== Analysis status response ===")
    print(f"GET /analysis/status -> {resp.status_code}")
    print(json.dumps(data, indent=2, default=str))


def main():
    events = build_test_events()
    post_events(events)
    get_analysis_status()
    print("\n(If you want to clear these out, use your dev DB reset script.)")


if __name__ == "__main__":
    main()

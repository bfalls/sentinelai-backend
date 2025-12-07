# SentinelAI Backend

Backend service for **SentinelAI**, an AI-assisted situational awareness plugin for CivTAK.  
It ingests real-world data feeds (e.g. aviation, ground tracks, weather), keeps a live in-memory view of the world, and exposes an API that turns **natural language requests** into **map overlays** for the CivTAK plugin.

Example query from CivTAK:

> “Show me all low-flying aircraft within 10 km of my team in the last 15 minutes and highlight anything heading toward us.”

The backend responds with structured overlays (markers, routes, polygons, annotations) that CivTAK can render on the map.

---

## Features

Planned / in-scope for this backend:

- **Natural language → overlays**
  - FastAPI endpoint that accepts a free-form prompt plus context (location, viewport, time window).
  - Uses an LLM (OpenAI) to decide what data to query and how to represent it visually.
- **Live SensorStore**
  - Periodic ingestors for:
    - Aviation tracks (e.g. ADS-B–style feeds).
    - Ground positions (later: APRS, team tracking, other feeds).
    - Weather and environment layers.
  - Aggregated into an in-memory “SensorStore” optimized for geospatial queries.
- **CivTAK-friendly responses**
  - JSON responses designed to be easy for the CivTAK plugin to turn into:
    - Markers and icons.
    - Tracks and polylines.
    - Danger areas / corridors / search grids.
- **Ops-friendly**
  - Health and readiness endpoints.
  - Structured logging.
  - Config via environment variables for easy deployment on EC2 or containers.

### Mission intents

The AI analysis engine uses **mission intents** to route prompts and behaviors. Supported intents:

- `SITUATIONAL_AWARENESS` (default)
- `ROUTE_RISK_ASSESSMENT`
- `WEATHER_IMPACT`
- `AIRSPACE_DECONFLICTION`

Requests can omit `intent` and will default to `SITUATIONAL_AWARENESS` for backward compatibility.

---

## Tech Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Web server:** Uvicorn (local), compatible with Gunicorn in production
- **Data / runtime:**
  - In-memory SensorStore for live tracks
  - Async background tasks for feed ingestion
- **AI integration:** OpenAI Chat/Completion API (LLM used as a “planner” and “explainer”)
- **Testing:** pytest

---

## Repository Layout (proposed)

This is the intended structure for `sentinelai-backend`:

```text
sentinelai-backend/
  README.md
  pyproject.toml           # or requirements.txt/setup.cfg if you prefer
  .env.example
  sentinelai_backend/
    __init__.py
    config.py              # settings, env loading
    main.py                # FastAPI app, startup/shutdown hooks
    api/
      __init__.py
      routes_query.py      # /v1/query
      routes_sensors.py    # /v1/sensors/*
      routes_health.py     # /health, /ready
    core/
      sensor_store.py      # in-memory world model
      models.py            # Pydantic models (DTOs)
      geo_utils.py         # geospatial helpers
    ingestors/
      __init__.py
      aviation_adsb.py     # ADS-B-style feed
      weather.py
      mock_feeds.py        # synthetic data for local dev
    services/
      ai_planner.py        # LLM call + prompt building
      overlay_builder.py   # convert query result → overlay DTOs
    logging_config.py
  tests/
    test_health.py
    test_query_api.py
    test_sensor_store.py
```

You can adjust as the implementation evolves, but this gives Codex/LLMs a clear target layout.

# Getting Started
## Prerequisites

- Python 3.11+
- `pip`
- An OpenAI API key (or compatible LLM endpoint)

## Clone and install

```bash
git clone https://github.com/bfalls/sentinelai-backend.git
cd sentinelai-backend

# Create and activate a virtual environment (example using venv)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# -- OR, if you're in development mode
pip install -r requirements-dev.txt
```


## Configuration
Configuration is driven by environment variables.

Key AI settings (add these to a local .env for dev):
- OPENAI_API_KEY: API key for OpenAI (not committed to git).
- OPENAI_MODEL: Model name (defaults to gpt-4o-mini).
- DEBUG_AI_ENDPOINTS: Enable /debug/ai-test when true.

A typical `.env`:

```env
# General
SENTINELAI_ENV=local
SENTINELAI_LOG_LEVEL=INFO

# API
SENTINELAI_HOST=0.0.0.0
SENTINELAI_PORT=8000

# OpenAI / LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
DEBUG_AI_ENDPOINTS=false

# Sensor ingestion
SENTINELAI_INGESTORS_ENABLED=aviation,weather
SENTINELAI_INGEST_INTERVAL_SECONDS=15

ENABLE_WEATHER_INGESTOR=true
ENABLE_ADSB_INGESTOR=false
ADSB_BASE_URL=https://opensky-network.org/api/states/all
ADSB_DEFAULT_RADIUS_NM=25
ADSB_TIMEOUT=10
```

Enable ADS-B ingestion by setting `ENABLE_ADSB_INGESTOR=true`. The default endpoint uses the unauthenticated OpenSky REST feed and does not require any credentials.

### APRS-IS ingestion

APRS is supported via a background TCP connection to an APRS-IS server that continuously posts packets into the `/api/v1/events` pipeline. Configure it with environment variables:

- `APRS_ENABLED` (true/false)
- `APRS_HOST` / `APRS_PORT` (defaults: `rotate.aprs2.net` / `14580`)
- `APRS_CALLSIGN` and `APRS_PASSCODE` (required when enabled; sourced from the environment only)
- `APRS_FILTER` (optional raw filter string) **or** `APRS_FILTER_CENTER_LAT`, `APRS_FILTER_CENTER_LON`, `APRS_FILTER_RADIUS_KM` for a simple range filter
- `API_BASE_URL` (base URL used by background ingestors to post events; defaults to `http://localhost:8000`)

When enabled, the APRS ingestor runs inside the FastAPI app process. It will log connection issues and back off, but it will not block the API from serving requests. Missions and analysis endpoints read APRS-derived events from the database; no live APRS calls are made while handling a request.

Local development example:

1. Export APRS credentials and filter (example radius filter around a test area):

   ```bash
   export APRS_ENABLED=true
   export APRS_CALLSIGN=N0CALL
   export APRS_PASSCODE=12345
   export APRS_FILTER_CENTER_LAT=40.0
   export APRS_FILTER_CENTER_LON=-105.0
   export APRS_FILTER_RADIUS_KM=50
   ```

2. Start the API: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Watch logs for incoming APRS packets; new events will appear in `/api/v1/events` responses and be included automatically when calling `/api/v1/analysis/mission`.

At startup, `config.py` should load these (e.g. via `pydantic-settings` or `python-dotenv`).

## Running the Server Locally

With the virtualenv active:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- OpenAPI docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## API Overview (initial design)
`GET /health`

Simple liveness probe:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

`GET /ready`

Optional readiness probe that checks:

- SensorStore is initialized.
- Ingestor background tasks are running (if enabled).
- LLM configuration is present.

`POST /v1/query`

Primary endpoint used by the CivTAK plugin.

Request (example):
```json
{
  "prompt": "Show all aircraft under 5,000 ft within 20 km heading towards my team in the last 10 minutes.",
  "user_location": { "lat": 43.615, "lon": -116.202 },
  "viewport": {
    "north": 43.8,
    "south": 43.4,
    "east": -115.8,
    "west": -116.5
  },
  "time_window_minutes": 10
}
```

Response (example shape):
```json
{
  "overlays": [
    {
      "type": "marker",
      "id": "aircraft-N123AB",
      "position": { "lat": 43.62, "lon": -116.18 },
      "label": "N123AB (3,200 ft, 140 kt)",
      "category": "aircraft",
      "metadata": {
        "altitude_ft": 3200,
        "ground_speed_kt": 140,
        "heading_deg": 215
      }
    },
    {
      "type": "polyline",
      "id": "track-N123AB",
      "points": [
        { "lat": 43.65, "lon": -116.15 },
        { "lat": 43.63, "lon": -116.16 },
        { "lat": 43.62, "lon": -116.18 }
      ],
      "label": "Last 10 minutes",
      "category": "track"
    }
  ],
  "explanation": "Found 1 low-flying aircraft approaching your position within 20 km in the last 10 minutes."
}
```

The CivTAK plugin is responsible for mapping `type`, `position`, `points`, and `category` into TAK overlay elements.

`GET /v1/sensors/snapshot`

Returns a summarized view of what the SensorStore currently holds (for debugging / UI later).

```json
{
  "timestamp": "2025-12-04T22:15:00Z",
  "feeds": {
    "aviation": { "count": 27, "last_update": "2025-12-04T22:14:45Z" },
    "weather": { "count": 3, "last_update": "2025-12-04T22:14:30Z" }
  }
}
```

## Development Notes
### Running tests

```bash
pytest
```

You can start with:

- tests/test_health.py – verifies /health and /ready.
- tests/test_sensor_store.py – basic CRUD and query behavior for SensorStore.
- tests/test_query_api.py – integration test that stubs LLM responses.

### Mocking the LLM

For local tests and offline development, the `ai_planner` service should support a “mock mode”:

- If `OPENAI_API_KEY` is missing and `SENTINELAI_ENV=local_mock`, return canned overlays instead of calling the real API.

This lets you develop the CivTAK plugin and backend integration without burning tokens.

### Deployment

High-level options (pick what you want to implement first):

1. Systemd + Uvicorn/Gunicorn on EC2
    - Install Python and dependencies on an EC2 instance.
    - Run uvicorn or gunicorn as a systemd service.
    - Terminate TLS at an ALB or nginx.

2. Containerized
    - Build a Docker image for sentinelai-backend.
    - Run on:
      - EC2 with docker-compose, or
      - ECS / Fargate, or
      - Any container platform.

3. Reverse proxy
    - Front the app with nginx or an ALB.
    - Restrict access to the API to trusted CIVTAK devices / networks.

Detailed deployment scripts (Dockerfile, compose, systemd units) can live under:

```text
deploy/
  Dockerfile
  docker-compose.yml
  systemd/
    sentinelai-backend.service
  aws/
    ec2-notes.md
```

### Roadmap Ideas
  - Add more ingestors (APRS, blue force trackers, additional aviation sources).
  - Support temporal queries like “since last time I asked” per device.
  - Push notifications / streams for ongoing alerts.
  - Role-based behavior (different overlays or thresholds per unit type).
  - Metrics and tracing (e.g. Prometheus, OTEL, Honeycomb, etc.).


## Weather ingestion

Weather enrichment can be toggled with environment variables:

- `ENABLE_WEATHER_INGESTOR`: Set to `true`/`1` to fetch weather context from Open-Meteo.
- `WEATHER_BASE_URL`: Override the Open-Meteo endpoint if needed.
- `WEATHER_TIMEOUT`: Timeout (seconds) for weather HTTP requests.

When disabled or if the provider is unavailable, mission analysis continues without weather data.

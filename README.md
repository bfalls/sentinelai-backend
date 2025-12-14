# SentinelAI Server

**AI orchestration and mission analysis service for the SentinelAI CivTAK plugin.**

This service ingests field signals, enriches them with weather and air-traffic context, and routes mission analysis requests to rule-based scoring or AI-powered intent handlers. Every request returns structured outputs that the CivTAK plugin can render as mission-aware overlays and summaries.

---

## Why SentinelAI

Modern missions generate noisy, multi-source data. The backend keeps the heavy lifting off the device and under your control:

- Centralize sensor ingestion (APRS, ADS-B, weather) and normalize context
- Enforce API-key access and auditing on every request
- Deliver structured, explainable analysis results to the plugin
- Keep model access and credentials on infrastructure you operate

---

## Key Capabilities

- **Mission status and AI analysis**
  - `/api/v1/analysis/status` returns a rule-based stability score using recent events.
  - `/api/v1/analysis/mission` builds a full mission context payload, performs intent routing, and returns summary, risks, and recommendations.
- **Intent-aware AI routing**
  - Supports explicit or auto-selected intents: `SITUATIONAL_AWARENESS`, `ROUTE_RISK_ASSESSMENT`, `WEATHER_IMPACT`, `AIRSPACE_DECONFLICTION`, `AIR_ACTIVITY_ANALYSIS`, and `RADIO_SIGNAL_ACTIVITY_ANALYSIS`.
- **Event ingestion**
  - `/api/v1/events` accepts structured mission events from the CivTAK plugin and persists them to SQLite with automatic retention cleanup.
- **Context enrichment**
  - Optional background ingestors for ADS-B tracks, weather snapshots, and APRS radio packets; results are summarized in AI prompts.
- **Operational guardrails**
  - API-key enforcement with hashed storage and peppers, request logging middleware, and optional debug AI connectivity checks.

---

## Architecture Overview

```
CivTAK Plugin (Android)
        |
        | HTTPS + API key (JSON)
        v
SentinelAI Backend (FastAPI)
        |
        | Context builders + AI / rule-based analysis
        v
Structured mission summaries and overlays
```

- **API layer:** FastAPI routers for health, event ingestion, and mission analysis.
- **Service layer:** Context builder, intent router, OpenAI client wrapper, and rule-based status engine.
- **Ingestors:** Optional background jobs for ADS-B, weather, and APRS to feed mission context.
- **Persistence:** SQLite by default (configurable via `SENTINELAI_DB_URL`) with daily retention cleanup.

---

## API Surface

- `GET /healthz` – basic liveness probe.
- `POST /api/v1/events` – store a mission event. Required fields include `event_type`; optional mission ID, description, timestamp, and metadata.
- `GET /api/v1/analysis/status` – compute a rule-based mission status using events in a configurable time window (`window_minutes`, default 60) and optional `mission_id` filter.
- `POST /api/v1/analysis/mission` – perform AI-assisted analysis. Payload accepts mission metadata, signals, notes, location, optional time window, and either a specific `intent` or automatic intent selection.
- `GET /debug/ai-test` – lightweight connectivity probe to the AI provider; only enabled when `DEBUG_AI_ENDPOINTS=true`.

All endpoints (except `/healthz`) require an API key in the `X-Sentinel-API-Key` header.

---

## Configuration

Configuration is environment-driven. Key settings from `app/config.py` include:

- **Runtime**
  - `SENTINELAI_ENV` (default `local`), `SENTINELAI_LOG_LEVEL`, `SENTINELAI_DB_URL`, `SENTINELAI_RETENTION_DAYS`
- **API**
  - `API_BASE_URL` (used by background ingestors), `REQUIRE_API_KEY` (defaults to true in production environments)
- **OpenAI / AI**
  - `OPENAI_MODEL` (default `gpt-4o-mini`), `OPENAI_TIMEOUT`, `DEBUG_AI_ENDPOINTS`
  - Secrets: OpenAI API key from SSM parameter `/sentinel/openai/api_key`
- **API key security**
  - Pepper from SSM parameter `/sentinel/api_key_pepper`; keys are stored hashed with HMAC-SHA256
- **Ingestors**
  - Weather: `ENABLE_WEATHER_INGESTOR`, `WEATHER_PROVIDER`, `WEATHER_BASE_URL`, `WEATHER_TIMEOUT`
  - ADS-B Flight Activity: `ENABLE_ADSB_INGESTOR`, `ADSB_BASE_URL`, `ADSB_TIMEOUT`, `ADSB_DEFAULT_RADIUS_NM`
  - APRS Radio Signals: `APRS_ENABLED`, `APRS_HOST`, `APRS_PORT`, `APRS_CALLSIGN`, `APRS_PASSCODE`, optional filters (`APRS_FILTER` or `APRS_FILTER_CENTER_LAT`/`_LON`/`_RADIUS_KM`)

AWS credentials/instance roles must permit `ssm:GetParameter` (with decryption) for the required secrets.

---

## Authentication & Key Management

- API key header: `X-Sentinel-API-Key`
- Keys are stored in the `api_keys` table with prefix-based lookup, hashed using a pepper from SSM.
- Use `scripts/admin_api_keys.py` to create, list, or revoke keys. Example:

  ```bash
  python scripts/admin_api_keys.py create --email user@example.com --label "CivTAK device"
  python scripts/admin_api_keys.py list
  python scripts/admin_api_keys.py revoke --prefix sk_sentinel_abcd --yes
  ```

- You can also use the `npm run` command from your local computer while in the repo and pass arguments. This will run remotely on the EC2 instance:
  ```bash
  npm run ec2-sentinel-admin-api-keys -- list

  1: prefix=034bc49f email=user@example.com label=admin expires=none revoked=active
  ```

Test-only keys (`sk_test_*`) are rejected outside test environments.

---

## Ingestors

- **APRS Radio Signals**
  - Background TCP connection posts APRS packets into the event pipeline using `API_BASE_URL`.
  - Runs only when `APRS_ENABLED=true` and credentials are provided.
- **ADS-B Flight Data**
  - Fetches OpenSky-style track data when `ENABLE_ADSB_INGESTOR=true` and summarizes nearby aircraft for AI prompts.
  - *IMPORTANT*: OpenSky likely will not allow requests from AWS IP addresses. You will have to create a free [Cloudflare](https://dash.cloudflare.com/) Worker to forward the requests.
- **Weather**
  - Pulls snapshots from Open-Meteo by default when `ENABLE_WEATHER_INGESTOR=true`.

If an ingestor is disabled or unavailable, analysis continues with whatever context is present.

---

## Running Locally

### Prerequisites
- Python 3.11+
- `pip`
- AWS credentials with access to the required SSM parameters (or set `SENTINELAI_ENV` to a non-production value and disable API-key enforcement for local testing)

### Install & Run

```bash
git clone https://github.com/bfalls/sentinelai-backend.git
cd sentinelai-backend

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt  # or requirements-dev.txt for local development

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI docs: http://localhost:8000/docs
- Health check: http://localhost:8000/healthz
- Default database: `sqlite:///./sentinelai.db` (configurable via `SENTINELAI_DB_URL`)

---

## Development & Testing

- Formatting/linting: follow the existing Python style (no custom tooling required by default).
- Tests: `pytest`

```bash
pytest
```

---

## Deployment Notes

- Built on FastAPI + Uvicorn; can run via systemd, Docker, or any container/orchestration platform.
- Provide environment variables for configuration and ensure the runtime has access to AWS SSM for secrets.
- API-key enforcement can be disabled in non-production environments by setting `REQUIRE_API_KEY=false`.
- Consider creating a free [DYNU](https://www.dynu.com/) account and setting up dynamic DNS.
  - See `scripts/update-ddns.sh` for where to store your key variables and create an EC2 service that runs on boot to call this script to update the IP address of the consistent domain you want to use.
  - *I'll commit the service scripts and add them to the deployment GitHub Actions soon.*
  - Here's an example `/etc/systemd/system/dynu-update.service`
  ```ini
  [Unit]
  Description=Update Dynu DDNS on boot
  After=network-online.target
  Wants=network-online.target

  [Service]
  Type=oneshot
  User=ec2-user
  WorkingDirectory=/opt/app-release-directory/current
  ExecStart=/usr/bin/env bash /opt/app-release-directory/current/scripts/update-ddns.sh

  [Install]
  WantedBy=multi-user.target
  ```

---

## Technology Stack

- Python 3.11+
- FastAPI
- SQLAlchemy + SQLite (or any SQLAlchemy-supported database via `SENTINELAI_DB_URL`)
- httpx for HTTP clients
- OpenAI API for AI orchestration

---

## Status

SentinelAI backend is in **active development** and suited for internal evaluations, demos, and controlled pilots.

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.

---

## Contact

For demos, integration discussions, or questions, contact the **SentinelAI Team**.

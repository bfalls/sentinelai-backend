# SentinelAI Backend – DESIGN

## 1. Overview

The SentinelAI backend is a small, hardened API service that connects TAK/CivTAK clients (via the SentinelAI plugin) to an AI assistant. It is responsible for:

- Receiving context-rich requests from the SentinelAI TAK plugin (map objects, mission notes, free-form questions).
- Shaping and routing those requests to an LLM provider (for example, OpenAI).
- Enforcing guardrails and redactions so operationally sensitive data is not leaked.
- Returning structured, predictable responses the plugin can render (chat answers, suggested tasks, annotations).
- Logging and observability for debugging and audit.

The backend is intentionally simple: a single stateless web service running on an EC2 instance, fronted by a stable DNS hostname (for example, `sentinelai.ddnsfree.com`) using dynamic DNS.

---

## 2. Goals and Non-Goals

### Goals

1. **Low-friction integration for TAK plugin**
   - Simple, well-documented HTTPS API.
   - JSON request/response contracts optimized for plugin usage.

2. **Safe AI usage**
   - Apply system prompts and content filters server-side.
   - Centralize LLM credentials and policy rather than baking them into the TAK plugin.

3. **Operationally practical**
   - Easy to deploy on a single EC2 instance.
   - Supports dynamic DNS so the plugin can connect via a stable hostname even if the EC2 IP changes.

4. **Extensible**
   - Start with one or two endpoints, leave room for future expansions (mission summarization, event analysis, training data ingestion).

### Non-Goals

- No multi-tenant, multi-user account system in v1.
- No large persistent data store beyond simple logs/config.
- No fine-grained RBAC or per-unit auth in v1 (API-key style is sufficient initially).

---

## 3. High-Level Architecture

### Components

- **SentinelAI TAK Plugin**
  - Runs inside CivTAK/ATAK.
  - Sends user prompts + context to backend via HTTPS.
  - Renders AI responses in the client (chat, annotations, notifications).

- **SentinelAI Backend (this repo)**
  - Suggested tech: Python + FastAPI (or Flask) with Uvicorn/Gunicorn.
  - Exposes REST endpoints:
    - `/api/v1/ping`
    - `/api/v1/chat`
    - `/api/v1/analyze_context`
    - `/api/v1/healthz` (internal)
  - Integrates with an LLM provider via HTTPS.

- **LLM Provider**
  - External provider (OpenAI or equivalent).
  - Called only from the backend; credentials never leave the server.

- **Dynamic DNS Updater**
  - A small script and systemd service on the EC2 instance.
  - On boot (and optionally on a timer), it calls the Dynu API to update the A record for `sentinelai.ddnsfree.com` to the EC2 public IP.

### Data Flow (Typical Chat Request)

1. User selects data or opens an AI panel in CivTAK.
2. SentinelAI plugin builds a JSON payload with:
   - `prompt` (user question)
   - `context` (mission name, selected markers, recent events)
   - `client_metadata` (TAK device ID, plugin version)
3. Plugin sends `POST /api/v1/chat` with an API key header over HTTPS.
4. Backend validates the API key and request format.
5. Backend:
   - Applies system prompt and redaction logic.
   - Calls LLM with structured messages.
   - Receives and normalizes response.
6. Backend returns a response object to the plugin.
7. Plugin displays the answer and may create annotations or messages based on response.

---

## 4. API Design

All endpoints are JSON over HTTPS.

### 4.1 Common Elements

**Headers**

- `Content-Type: application/json`
- `X-Sentinel-API-Key: <shared_secret>` (later upgradeable to mTLS or per-device keys)

**Error Shape**

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Human-readable description",
    "details": {}
  }
}
```

### 4.2 `GET /api/v1/ping`

Basic connectivity probe for the plugin.

**Request**: no body.

**Response**:

```json
{
  "status": "ok",
  "service": "sentinel-backend",
  "version": "v0.1.0"
}
```

### 4.3 `POST /api/v1/chat`

Primary endpoint used by the plugin for conversational AI.

**Request body:**

```json
{
  "prompt": "What are the main risks in this mission plan?",
  "context": {
    "mission_name": "TRAINING-ALPHA-03",
    "selected_markers": [
      {
        "uid": "MARKER-123",
        "type": "friendly_unit",
        "lat": 43.615,
        "lon": -116.201,
        "elevation_m": 850,
        "label": "Alpha Squad"
      }
    ],
    "notes": [
      "Route follows main road for 5km through valley.",
      "Known traffic checkpoints at 3km and 4km."
    ]
  },
  "history": [
    {
      "role": "user",
      "content": "Summarize current mission in one paragraph."
    },
    {
      "role": "assistant",
      "content": "Short summary..."
    }
  ],
  "client_metadata": {
    "tak_device_id": "ABC123",
    "plugin_version": "0.1.0",
    "platform": "CivTAK-Android"
  }
}
```

**Response body:**

```json
{
  "answer": "Based on the current mission plan, the main risks are...",
  "summary": "Top 3 risks identified.",
  "suggested_actions": [
    "Consider an alternate route that reduces exposure to the main road.",
    "Add waypoints for possible cover positions.",
    "Clarify communication plan for checkpoints."
  ],
  "raw_model_output": null
}
```

Notes:

- `raw_model_output` can be optionally included for debugging or left null/omitted for the plugin.

### 4.4 `POST /api/v1/analyze_context` (optional v1)

Used for purely context-based analysis (e.g., attached mission file or snapshot).

**Request body** (example):

```json
{
  "context_blob": "<opaque mission JSON or text>",
  "prompt": "Summarize this mission for a new team member."
}
```

**Response body** mirrors `/api/v1/chat`.

---

## 5. LLM Integration

### 5.1 Provider Abstraction

Implement a small interface layer so the rest of the code does not depend heavily on one provider:

- `llm_client.py`:
  - `generate_chat_response(messages: List[Message], temperature: float = 0.2, max_tokens: int = 512) -> str`

Messages will be in a provider-agnostic format (role/content pairs). The implementation converts them to the chosen SDK’s format.

### 5.2 System Prompt and Guardrails

Backend defines a system prompt that guides the AI in this domain:

- Assist with **tactical reasoning**, but do **not** claim access to real-time sensors.
- Avoid hallucinating orders or authoritative directives; phrase guidance as suggestions.
- Never fabricate or guess classified data.
- Avoid generating sensitive personally identifiable information.

Prompt is not exposed to the client.

---

## 6. Configuration and Secrets

Configuration via environment variables (or .env for local dev):

- `SENTINEL_ENV` (local, dev, prod)
- `SENTINEL_API_KEY` (shared secret with plugin)
- `SENTINEL_LLM_PROVIDER` (e.g. `openai`)
- `SENTINEL_LLM_MODEL` (e.g. `gpt-4.1-mini`)
- `OPENAI_API_KEY` (if applicable)
- `SENTINEL_LOG_LEVEL` (info, debug, warning)
- `SENTINEL_BIND_HOST` (0.0.0.0 in EC2)
- `SENTINEL_BIND_PORT` (e.g. 8000)

Dynu / DDNS specific:

- `DYNU_API_KEY`
- `DYNU_HOSTNAME` (e.g. `sentinelai.ddnsfree.com`)

---

## 7. Dynamic DNS Updater

A small script will be deployed with the backend to keep the Dynu hostname pointing at the correct EC2 public IP.

### 7.1 Responsibilities

- On instance boot:
  - Discover the current public IP (via EC2 metadata or an external “what is my IP” service).
  - Call Dynu’s API to update the A record for `DYNU_HOSTNAME`.
- Optionally run periodically (e.g., via systemd timer) in case the IP changes without a reboot.

### 7.2 Implementation Sketch (not full code)

- Script `scripts/update_dynu_dns.sh` or `scripts/update_dynu_dns.py`.
- systemd unit:
  - `sentinel-dynu-update.service` – runs once at boot.
  - Optional `.timer` to re-run periodically.

---

## 8. Repo Layout

Proposed layout for `sentinel-backend`:

```text
sentinel-backend/
  README.md
  DESIGN.md
  .gitignore
  requirements.txt        # or pyproject.toml
  sentinel_backend/
    __init__.py
    main.py               # FastAPI app
    api/
      __init__.py
      routes_chat.py
      routes_health.py
    core/
      config.py
      logging.py
      security.py         # API key checks, basic rate limiting hooks
      llm_client.py
      prompt_builder.py
    models/
      chat.py             # Pydantic models for request/response
    infra/
      dynu_dns_updater.py # optional Python variant
  scripts/
    run_dev.sh
    update_dynu_dns.sh    # shell helper if needed
  tests/
    test_chat_api.py
    test_health_api.py
  .github/
    workflows/
      ci.yml              # lint + tests
```

---

## 9. Deployment

### 9.1 Local Development

- `uvicorn sentinel_backend.main:app --reload --host 0.0.0.0 --port 8000`
- Use a `.env` file for local environment variables.
- Connect from a local TAK emulator or curl / Postman.

### 9.2 EC2 Deployment

- EC2 instance (Amazon Linux or Ubuntu).
- Python runtime + virtualenv.
- Reverse proxy (nginx) recommended:
  - Terminate TLS.
  - Proxy `/api/` to `localhost:8000`.
- Systemd service `sentinel-backend.service`:
  - Starts the app on boot.
  - Restarts on failure.

Startup sequence:

1. `sentinel-dynu-update.service` (or timer) runs and updates Dynu.
2. `sentinel-backend.service` starts the FastAPI app.
3. CivTAK/ATAK plugin connects via `https://sentinelai.ddnsfree.com/api/v1/ping`.

### Recommended `npm` Scripts for Service Management

Below is a suggested `package.json` snippet you can include in the repo. These scripts allow clean, predictable management of both the **EC2 system service** and the **local development FastAPI server**:

```jsonc
{
  "scripts": {
    "ec2:start": "ssh $EC2_HOST 'sudo systemctl start sentinel-backend.service'",
    "ec2:stop": "ssh $EC2_HOST 'sudo systemctl stop sentinel-backend.service'",
    "ec2:restart": "ssh $EC2_HOST 'sudo systemctl restart sentinel-backend.service'",
    "ec2:status": "ssh $EC2_HOST 'sudo systemctl status sentinel-backend.service'",

    "api:start": "uvicorn sentinel_backend.main:app --reload --host 0.0.0.0 --port 8000",
    "api:stop": "pkill -f 'uvicorn sentinel_backend.main:app' || true",

    "api:ping": "curl -s http://localhost:8000/api/v1/ping",
    "ec2:ping": "curl -s https://$BACKEND_HOST/api/v1/ping"
  }
}
```

### Environment Variables Required

```bash
export EC2_HOST=ec2-user@ec2-3-91-xxx-xxx.compute-1.amazonaws.com
export BACKEND_HOST=sentinelai.ddnsfree.com
```

### Examples

```bash
npm run ec2:start
npm run ec2:restart
npm run api:start
npm run ec2:ping
```

---

## 10. Observability and Logging

- Structured JSON logs (at least in production) for:
  - Incoming requests (without sensitive content where possible).
  - LLM calls (timings, token usage, truncated prompts).
  - Errors / exceptions.
- Health probes:
  - `GET /api/v1/healthz` returns basic health info for use with uptime checks.

At this stage, logs can be stored locally or shipped to CloudWatch; design leaves room for later Sumo Logic / Honeycomb integration.

---

## 11. Future Enhancements

- **Role-based flows**: different system prompts for “Planner,” “Medic,” “Analyst,” etc.
- **Mission thread IDs**: maintain conversation threads keyed to missions.
- **Offline caching**: provide pre-computed briefings that can be synced and used when disconnected.
- **Fine-grained auth**: device-level keys, revocation lists, and per-org configuration.

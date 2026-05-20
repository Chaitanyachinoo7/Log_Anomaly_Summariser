# Log Anomaly Summariser — Implementation Plan

## Summary

Build a small service that accepts Datadog log webhooks via FastAPI, runs a LangGraph pipeline to detect anomalies and generate a plain-English incident summary using a local Ollama model, persists full inputs/outputs in Postgres, and notifies Slack + email.

## Current State Analysis

- Repo contains only a placeholder README: [README.md](file:///workspace/README.md).
- No application code, dependency manifests, container artifacts, or tests exist yet.

## Goal & Success Criteria

- Provide a FastAPI endpoint that accepts Datadog log webhook payloads and responds with an incident decision plus an incident ID (when created).
- Implement a LangGraph stateful graph with conditional routing:
  - Route to summarization + notifications only when anomaly rules indicate an incident.
  - Route to a “no-incident” path otherwise.
- Persist full retention data in Postgres:
  - Raw webhook payloads.
  - Normalized log events.
  - Incident records + summaries + notification outcomes.
- Send the incident summary to:
  - Slack via Incoming Webhook URL.
  - Email via SMTP.
- Provide Docker-based local run path (app + Postgres; Ollama assumed reachable from the app container).
- Include automated tests for core parsing/routing/summarization orchestration.

## Proposed Changes

### Project Structure (new)

- Create a Python package under `src/log_anomaly_summariser/` using a `pyproject.toml` (PEP 621).
- Add `tests/` with pytest-based unit tests.
- Add container artifacts (`Dockerfile`, `docker-compose.yml`) for local runs.

Planned top-level layout:

- `pyproject.toml`
- `README.md` (expand with usage + env vars)
- `src/log_anomaly_summariser/`
  - `__init__.py`
  - `main.py` (FastAPI app + routes)
  - `settings.py` (env-driven configuration)
  - `webhooks/datadog.py` (payload models + normalization)
  - `graph/`
    - `state.py` (graph state schema)
    - `build.py` (LangGraph compilation)
    - `nodes/` (pipeline node implementations)
  - `anomaly/`
    - `rules.py` (hybrid detection: rules → score → incident decision)
  - `llm/ollama.py` (Ollama client wrapper via HTTP)
  - `notify/`
    - `slack.py`
    - `email.py`
  - `storage/`
    - `db.py` (engine/session)
    - `models.py` (SQLAlchemy models)
    - `repo.py` (persistence functions)
  - `util/` (small shared helpers, e.g., time parsing, hashing)
- `alembic/` + `alembic.ini` (schema migrations)
- `Dockerfile`
- `docker-compose.yml`

### Dependencies (new)

Add to `pyproject.toml` (exact pins decided during implementation based on compatibility):

- API/service: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
- Graph/orchestration: `langgraph` (and minimal langchain core deps if required by langgraph)
- HTTP: `httpx`
- DB: `sqlalchemy`, `asyncpg`, `alembic`
- Testing: `pytest`, `pytest-asyncio`, `respx` (httpx mocking) or equivalent

### FastAPI Webhook (new)

File: `src/log_anomaly_summariser/main.py`

- `POST /webhooks/datadog`
  - Accept JSON payload compatible with Datadog logs webhook.
  - Validate with permissive Pydantic models (allow extra fields).
  - Pass the payload into the LangGraph pipeline.
  - Return response JSON with:
    - `received_at`
    - `incident`: boolean
    - `incident_id`: string|null
    - `summary`: string|null (optional; can be omitted for very large outputs)
    - `reason`: short explanation of rule/threshold triggers
- Add `GET /healthz` and `GET /readyz`.

### Datadog Payload Normalization (new)

File: `src/log_anomaly_summariser/webhooks/datadog.py`

- Define Pydantic models with a focus on extracting:
  - timestamp
  - status/level
  - service/source
  - host
  - message
  - tags (when present)
- Implement a normalizer that produces an internal `NormalizedLogEvent` list used by anomaly detection and summarization.
- Keep raw JSON for full retention persistence.

### Storage (Postgres) + Retention (new)

Files:
- `src/log_anomaly_summariser/storage/db.py`
- `src/log_anomaly_summariser/storage/models.py`
- `src/log_anomaly_summariser/storage/repo.py`
- `alembic/` migrations

Schema (initial):

- `webhook_payloads`
  - `id` (uuid)
  - `vendor` (e.g., `datadog`)
  - `received_at`
  - `payload_json` (JSONB)
  - `payload_hash` (dedupe/idempotency)
- `log_events`
  - `id` (uuid)
  - `payload_id` (fk)
  - `ts`, `level`, `service`, `host`, `message`, `attributes_json` (JSONB)
- `incidents`
  - `id` (uuid)
  - `created_at`
  - `payload_id` (fk)
  - `decision` (incident/non-incident)
  - `severity` (string)
  - `rule_reason` (text)
  - `summary` (text)
  - `model` (string)
- `notifications`
  - `id` (uuid)
  - `incident_id` (fk)
  - `channel` (`slack`/`email`)
  - `sent_at`
  - `status` (`sent`/`failed`)
  - `error` (text nullable)

Idempotency:

- Compute `payload_hash` as a stable hash of the raw payload body; if the same payload is received again, return the existing incident decision/ID rather than re-summarizing and re-notifying.

### LangGraph Pipeline (new)

Files:
- `src/log_anomaly_summariser/graph/state.py`
- `src/log_anomaly_summariser/graph/build.py`
- `src/log_anomaly_summariser/graph/nodes/*`

State:

- `raw_payload` (dict)
- `payload_id` (uuid)
- `normalized_events` (list)
- `anomaly_result` (score, decision, reason, severity)
- `summary` (string|null)
- `incident_id` (uuid|null)
- `notification_results` (per-channel outcomes)

Nodes (proposed):

1. `persist_payload`
   - Insert into `webhook_payloads` (or load existing by hash).
2. `normalize`
   - Parse/normalize Datadog payload into internal events.
3. `persist_events`
   - Insert normalized events linked to payload.
4. `detect_anomaly`
   - Hybrid approach: rules produce signals, optionally produce a compact “context” for the LLM.
5. Conditional routing:
   - If `decision == incident` → `summarize_incident`
   - Else → `finish_no_incident`
6. `summarize_incident`
   - Call Ollama to generate a plain-English incident report.
7. `persist_incident`
   - Store summary + metadata in `incidents`.
8. `notify_slack` and `notify_email`
   - Execute and store results in `notifications`.
9. `finish`

### Hybrid Anomaly Detection (new)

File: `src/log_anomaly_summariser/anomaly/rules.py`

Implement deterministic rules (first pass), then allow LLM to refine severity/explanation during summarization:

- Rules examples (env-configurable):
  - count of `error`/`exception` messages over a rolling window in the payload
  - presence of “panic”, “traceback”, “out of memory”, “connection refused”
  - distinct affected services/hosts above threshold
- Output a structured `AnomalyResult` with:
  - `incident` boolean
  - `severity` (e.g., low/medium/high)
  - `reason` (machine-readable + human-readable)
  - `top_signals` (for prompt grounding)

### Ollama Summarization (new)

File: `src/log_anomaly_summariser/llm/ollama.py`

- Use `httpx` to call Ollama’s HTTP API.
- Config via env:
  - `OLLAMA_BASE_URL` (default `http://host.docker.internal:11434` for Docker-on-desktop; override for Linux)
  - `OLLAMA_MODEL` (e.g., `llama3.1:8b`)
- Prompt design:
  - Provide short incident brief: time range, services, error counts, top representative messages, rule triggers.
  - Ask for a plain-English output with consistent headings:
    - What happened
    - Impact
    - Most likely cause
    - Evidence (key log lines)
    - Suggested next actions

### Notifications (new)

Files:
- `src/log_anomaly_summariser/notify/slack.py`
- `src/log_anomaly_summariser/notify/email.py`

Slack:

- Send formatted text to a channel via Incoming Webhook URL (`SLACK_WEBHOOK_URL`).

Email:

- Send via SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TO`).
- Keep the email body as a text version of the summary; optionally include incident ID and key metadata.

### Docker Runtime (new)

Files:
- `Dockerfile`
- `docker-compose.yml`

Compose services:

- `api` (FastAPI app)
- `postgres` (database)
- Environment variables passed via `.env` (documented in README; `.env` itself not committed)

Ollama connectivity:

- Prefer `OLLAMA_BASE_URL` as a config knob.
- Document platform-specific values:
  - Docker Desktop: `http://host.docker.internal:11434`
  - Linux: run Ollama in another container or use the host gateway IP; document a working compose alternative if needed.

### Tests (new)

- Unit tests for:
  - Datadog payload parsing and normalization.
  - Rule-based anomaly scoring and decision.
  - Graph routing (incident path vs no-incident path).
- Mock external effects:
  - Ollama HTTP calls via httpx mocking.
  - Slack webhook calls via httpx mocking.
  - SMTP send via monkeypatch/mock.
- Optional: DB-backed tests using a temporary Postgres container are possible, but default to repository/unit tests to keep CI simple.

## Assumptions & Decisions

- Payload type: Datadog logs webhook JSON.
- LLM runtime: Ollama, accessed over HTTP from the API process.
- Notification channels: Slack Incoming Webhook + SMTP email.
- Retention: full retention, stored in Postgres (payloads, events, incidents, notification outcomes).
- Dependency management: `pyproject.toml`-based (tooling choice finalized during implementation; structure will be compatible with `uv`).
- Deployment: Docker-first local deployment (compose).

## Verification Steps

- Static checks:
  - Import the app module and run type/model validation paths exercised by tests.
- Tests:
  - Run pytest suite and ensure all unit tests pass.
- Local run (Docker):
  - Start Postgres + API via docker-compose.
  - Send a sample Datadog-like payload to `POST /webhooks/datadog`.
  - Verify:
    - HTTP response contains incident decision and incident_id when incident.
    - Records exist in `webhook_payloads`, `log_events`, `incidents`, `notifications`.
    - Slack + email delivery attempts recorded; failures are captured with error text.


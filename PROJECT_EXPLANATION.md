# Project Explanation — Log Anomaly Summariser

## 1) What This Project Does (Big Picture)

This project is a small incident summarisation service.

It receives application logs (currently shaped like a Datadog logs webhook payload), decides whether those logs look like an “incident”, and if yes:

1. Generates a plain-English incident summary using a local LLM (Ollama).
2. Stores the raw payload, normalized log events, incident record, and notification results in Postgres (full retention).
3. Sends the incident summary to Slack and email.

If the logs do not look like an incident, the service still stores the payload + events and records a “no_incident” decision in the database.

The main entrypoint is a FastAPI endpoint:

- `POST /webhooks/datadog`

Related: [main.py](file:///workspace/src/log_anomaly_summariser/main.py)

## 2) Core Concepts (Step-by-Step, in the Order the System Runs)

The system is built around a pipeline (a “graph”) where each step (node) updates a shared state and then passes it to the next step.

This design is implemented using LangGraph.

The key concepts you’ll see throughout the code:

- **Webhook ingestion**: accept a vendor payload (Datadog), validate it as JSON, and hand it to the pipeline.
- **Normalization**: convert unknown vendor JSON shapes into a consistent internal list of log events.
- **Anomaly detection**: rule-based decision that flags likely incidents.
- **LLM summarisation**: only for incidents; uses Ollama via HTTP.
- **Persistence**: store payloads, events, incidents, and notifications in Postgres.
- **Notifications**: send incident summary to Slack + SMTP email.
- **Idempotency / dedupe**: if the exact same payload comes in again, do not re-summarize or re-notify; just return the existing incident decision.

## 3) Repository Layout (What Each Folder/File Is For)

Top level:

- [pyproject.toml](file:///workspace/pyproject.toml): Python package metadata + dependencies.
- [README.md](file:///workspace/README.md): quickstart instructions.
- [Dockerfile](file:///workspace/Dockerfile): builds the API container and runs migrations + server.
- [docker-compose.yml](file:///workspace/docker-compose.yml): runs Postgres + API locally.
- [alembic.ini](file:///workspace/alembic.ini), [alembic/](file:///workspace/alembic): database migrations.
- [tests/](file:///workspace/tests): unit tests.

Application code:

- [src/log_anomaly_summariser/main.py](file:///workspace/src/log_anomaly_summariser/main.py): FastAPI app + endpoints + graph invocation.
- [src/log_anomaly_summariser/settings.py](file:///workspace/src/log_anomaly_summariser/settings.py): environment-based configuration (DB URL, Slack/email creds, Ollama config, thresholds).
- [src/log_anomaly_summariser/webhooks/datadog.py](file:///workspace/src/log_anomaly_summariser/webhooks/datadog.py): vendor payload normalization.
- [src/log_anomaly_summariser/anomaly/rules.py](file:///workspace/src/log_anomaly_summariser/anomaly/rules.py): deterministic “incident or not” rules.
- [src/log_anomaly_summariser/llm/ollama.py](file:///workspace/src/log_anomaly_summariser/llm/ollama.py): minimal Ollama chat client.
- [src/log_anomaly_summariser/notify/](file:///workspace/src/log_anomaly_summariser/notify): Slack and SMTP implementations.
- [src/log_anomaly_summariser/storage/](file:///workspace/src/log_anomaly_summariser/storage): SQLAlchemy models, DB session factory, and persistence functions.
- [src/log_anomaly_summariser/graph/](file:///workspace/src/log_anomaly_summariser/graph): LangGraph state, nodes, and graph builder.
- [src/log_anomaly_summariser/util/](file:///workspace/src/log_anomaly_summariser/util): small helpers (hashing, timestamp parsing).

## 4) Tech Stack (What Is Used and Why)

Defined in [pyproject.toml](file:///workspace/pyproject.toml).

### API

- **FastAPI**: provides the webhook HTTP endpoint and service lifecycle hooks.
- **Uvicorn**: ASGI server to run FastAPI.

### Pipeline / Orchestration

- **LangGraph**: defines a stateful graph where nodes run in order and can branch based on state.

### Validation / Configuration

- **Pydantic v2**: models vendor payload items with permissive parsing.
- **pydantic-settings**: loads configuration from environment variables (and `.env` file).

### Database / Retention

- **Postgres**: stores payloads, events, incidents, and notifications.
- **SQLAlchemy (async)**: ORM for async Postgres usage.
- **asyncpg**: Postgres driver for async SQLAlchemy.
- **Alembic**: migrations and schema management.

### Integrations

- **Ollama**: local LLM runtime. Called via HTTP.
- **Slack Incoming Webhooks**: sends the incident summary into a channel.
- **SMTP**: sends the incident summary to an email inbox.

### Testing

- **pytest** + **pytest-asyncio**: test runner + async support.
- **respx**: mocking httpx calls (used by Ollama/Slack).

## 5) How Configuration Works (Environment Variables)

All settings are defined in [settings.py](file:///workspace/src/log_anomaly_summariser/settings.py).

### Required

- `DATABASE_URL`: async SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@host:5432/dbname`

### LLM (Ollama)

- `OLLAMA_BASE_URL`: default is `http://host.docker.internal:11434`
- `OLLAMA_MODEL`: default is `llama3.1:8b`

### Slack

- `SLACK_WEBHOOK_URL`: if set, Slack notifications will be attempted.

### Email (SMTP)

- `SMTP_HOST`, `SMTP_PORT`
- `SMTP_USER`, `SMTP_PASS` (optional)
- `SMTP_FROM`, `SMTP_TO` (required to send)

### Incident Heuristics

- `INCIDENT_ERROR_COUNT_THRESHOLD`: default `10`
- `INCIDENT_KEYWORDS`: comma-separated list of keywords

## 6) The Main Flow: From Webhook to Summary (Very Step-by-Step)

This section walks through what happens when the system receives a webhook request.

### Step 1 — HTTP request enters FastAPI

Endpoint: `POST /webhooks/datadog` in [main.py](file:///workspace/src/log_anomaly_summariser/main.py#L44-L85).

What happens:

1. FastAPI reads the request body as JSON.
2. The app computes a `payload_hash` using a stable JSON serialization + SHA-256:
   - [stable_json_hash](file:///workspace/src/log_anomaly_summariser/util/hashing.py#L8-L10)
3. The app opens a Postgres session using the async sessionmaker created at startup:
   - engine/session creation is in [main.py](file:///workspace/src/log_anomaly_summariser/main.py#L19-L28)
   - sessionmaker helpers are in [db.py](file:///workspace/src/log_anomaly_summariser/storage/db.py#L8-L13)
4. The app builds an initial graph state (a dict) and calls `graph.ainvoke(state)`:
   - [main.py](file:///workspace/src/log_anomaly_summariser/main.py#L55-L67)

### Step 2 — Graph orchestration begins (LangGraph)

The graph definition is built in [build_graph](file:///workspace/src/log_anomaly_summariser/graph/build.py#L16-L75).

LangGraph holds a shared state object (a dictionary-like structure). Each node returns a partial dictionary update, which gets merged into the state.

The state shape is documented as a `TypedDict`:

- [GraphState](file:///workspace/src/log_anomaly_summariser/graph/state.py#L10-L36)

### Step 3 — persist_payload node (idempotency / dedupe)

Node: [persist_payload](file:///workspace/src/log_anomaly_summariser/graph/nodes/persist.py#L7-L25)

What it does:

1. Inserts the raw payload into `webhook_payloads` *or* reuses an existing row with the same `payload_hash`.
   - DB helper: [get_or_create_payload](file:///workspace/src/log_anomaly_summariser/storage/repo.py#L36-L47)
2. Checks whether this payload already has an incident decision stored.
   - [get_incident_for_payload](file:///workspace/src/log_anomaly_summariser/storage/repo.py#L65-L67)
3. If an incident already exists, it returns:
   - `existing_incident_id`, `incident_id`, and `summary` (if any)
4. The graph then conditionally exits early if this is an existing payload:
   - [build.py](file:///workspace/src/log_anomaly_summariser/graph/build.py#L41-L48)

This prevents double-notifying and double-summarising for identical payloads.

### Step 4 — normalize node (vendor payload → internal event list)

Node: [normalize](file:///workspace/src/log_anomaly_summariser/graph/nodes/normalize.py#L7-L9)

What it does:

1. Calls [normalize_datadog_payload](file:///workspace/src/log_anomaly_summariser/webhooks/datadog.py#L42-L71).
2. Produces a list of internal event dictionaries with keys:
   - `ts`, `level`, `service`, `host`, `message`, `attributes`

Why normalization matters:

Datadog payloads can vary. The normalizer tries several common keys (`logs`, `events`, `data`, etc.) to locate a list of records and then extracts a minimal “core schema”.

Timestamp parsing:

- [parse_timestamp](file:///workspace/src/log_anomaly_summariser/util/time.py#L7-L30) supports:
  - `datetime` objects
  - Unix seconds/milliseconds
  - ISO-8601 strings (including `Z` suffix)

### Step 5 — persist_events node (full retention of normalized events)

Node: [persist_events](file:///workspace/src/log_anomaly_summariser/graph/nodes/persist_events.py#L7-L9)

What it does:

1. Inserts each normalized event into the `log_events` table, linked to the payload id.
2. The raw vendor record is stored as JSON in `attributes_json`.

Helper:

- [insert_events](file:///workspace/src/log_anomaly_summariser/storage/repo.py#L49-L63)

### Step 6 — detect node (hybrid incident detection)

Node: [detect](file:///workspace/src/log_anomaly_summariser/graph/nodes/detect.py#L8-L21)

Under the hood:

- It calls [detect_anomaly](file:///workspace/src/log_anomaly_summariser/anomaly/rules.py#L15-L62) which:
  1. Counts error-like events (level in `{error, err, fatal, critical}` or message contains “exception”).
  2. Scans messages for configured keywords (`INCIDENT_KEYWORDS`).
  3. Declares an incident if either condition triggers.
  4. Produces:
     - `incident` boolean
     - `severity` (low/medium/high)
     - `score`
     - `reason` (a machine-readable explanation like `error_count=...; keyword_hits=...`)
     - `top_signals` (compact signals used for LLM grounding)

### Step 7 — Conditional routing (incident vs no-incident)

Routing logic:

- [build.py](file:///workspace/src/log_anomaly_summariser/graph/build.py#L53-L60)

If incident:

1. Go to summarization node.

If no-incident:

1. Skip LLM summarization and go straight to persisting an incident record with decision `no_incident`.

### Step 8 — summarize node (only for incidents)

Node: [summarize_incident](file:///workspace/src/log_anomaly_summariser/graph/nodes/summarize.py#L34-L58)

What it does:

1. Builds a compact prompt containing:
   - incident decision, severity, reason
   - time range of logs (if timestamps exist)
   - “signals” from the rule engine
   - up to 25 sample log lines
2. Sends a chat request to Ollama:
   - [OllamaClient.chat](file:///workspace/src/log_anomaly_summariser/llm/ollama.py#L11-L24)
3. Stores the returned text in state as `summary`.

### Step 9 — persist_incident node (store decision + summary)

Node: [persist_incident](file:///workspace/src/log_anomaly_summariser/graph/nodes/persist_incident.py#L8-L23)

What it does:

1. Creates a row in `incidents` with:
   - decision: `incident` or `no_incident`
   - severity, rule_reason
   - summary + model (only when decision is `incident`)
2. Adds `incident_id` to graph state so later nodes can reference it.

Helper:

- [create_incident](file:///workspace/src/log_anomaly_summariser/storage/repo.py#L70-L89)

### Step 10 — notify node (Slack + Email, only for incidents)

Node: [notify](file:///workspace/src/log_anomaly_summariser/graph/nodes/notify.py#L10-L53)

What it does:

1. Builds a notification text: title + summary.
2. If `SLACK_WEBHOOK_URL` is configured:
   - posts to Slack via [send_slack](file:///workspace/src/log_anomaly_summariser/notify/slack.py#L6-L9)
3. If SMTP settings are configured:
   - sends via [send_email](file:///workspace/src/log_anomaly_summariser/notify/email.py#L8-L30)
4. Stores a row in `notifications` for each channel attempt:
   - [add_notification_result](file:///workspace/src/log_anomaly_summariser/storage/repo.py#L92-L102)

Failure behavior:

- Exceptions are caught per channel and recorded as `status=failed` with `error=str(e)`.
- The webhook request itself still returns successfully as long as the overall transaction is committed.

### Step 11 — Return response to the webhook caller

Back in [main.py](file:///workspace/src/log_anomaly_summariser/main.py#L72-L84), the response is built from graph state:

- `incident`: boolean
- `incident_id`: uuid string (or null)
- `reason`: rule explanation
- `summary`: only included if `incident=true`

## 7) Database Schema (What We Store and Why)

SQLAlchemy models:

- [models.py](file:///workspace/src/log_anomaly_summariser/storage/models.py)

Tables:

1. `webhook_payloads`
   - stores the raw incoming webhook payload
   - `payload_hash` enables dedupe/idempotency
2. `log_events`
   - stores normalized events extracted from the raw payload
   - `attributes_json` stores the original vendor record per event
3. `incidents`
   - stores the decision + severity + reason
   - stores the LLM summary for real incidents
4. `notifications`
   - stores each outbound notification attempt (slack/email), status, and any error text

Migration:

- [0001_init.py](file:///workspace/alembic/versions/0001_init.py)

## 8) Running Locally (Docker) — What Happens at Startup

### docker-compose

Defined in [docker-compose.yml](file:///workspace/docker-compose.yml):

1. Starts Postgres.
2. Waits until Postgres healthcheck passes.
3. Starts the API container.

### Dockerfile behavior

Defined in [Dockerfile](file:///workspace/Dockerfile):

On container start, it runs:

1. `alembic upgrade head` (applies DB schema).
2. `uvicorn log_anomaly_summariser.main:app ...` (starts the HTTP server).

## 9) Testing Strategy (How Tests Are Written)

Tests live in [tests/](file:///workspace/tests).

Key patterns:

- Normalization tests validate extraction of core fields from a sample payload:
  - [test_datadog_normalize.py](file:///workspace/tests/test_datadog_normalize.py)
- Anomaly rule tests validate “incident” vs “no incident” decisions:
  - [test_anomaly_rules.py](file:///workspace/tests/test_anomaly_rules.py)
- Graph routing tests mock out DB calls (no real Postgres required) and assert:
  - “no incident” path skips summarization and persists `no_incident`:
    - [test_graph_routing.py](file:///workspace/tests/test_graph_routing.py)

## 10) Extending the Project (Common Next Steps)

### Add support for more vendors

1. Add a new module under `src/log_anomaly_summariser/webhooks/`.
2. Implement `normalize_<vendor>_payload(payload) -> list[events]`.
3. Add a new endpoint `POST /webhooks/<vendor>` that populates graph state with:
   - `vendor=<vendor>`
   - `raw_payload=<payload>`
4. Either:
   - reuse the same graph but swap the normalize node based on vendor, or
   - compile a separate graph per vendor.

### Improve anomaly detection (still “hybrid”)

Right now the “incident decision” is deterministic rules.

Typical upgrades:

- include per-service thresholds
- compute rates, bursts, or error percentage
- cluster similar messages
- add an additional “LLM classification node” (after rules) to refine severity

### Make notifications richer

For Slack, you can switch from plain text to structured blocks.

For email, you can generate both text and HTML bodies.

## 11) Important Operational Notes

- This project intentionally keeps secrets out of the repository.
- Notification failures are recorded in Postgres (table `notifications`).
- Ollama must be reachable from the API container via `OLLAMA_BASE_URL`.


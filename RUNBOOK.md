# Runbook — Log Anomaly Summariser

This document explains how to run the application end-to-end and how to run a local Llama-family model via terminal (Ollama), which the app uses for incident summaries.

## 1) Prerequisites

- Docker + Docker Compose (for the recommended setup)
- (Optional) Python 3.11+ (for running without Docker)
- A reachable Ollama server running a model (for real incident summaries)
  - If Ollama is not reachable, the app can still ingest and persist logs, but incident summarization will fail when an incident is detected.

## 2) Run Ollama Locally (Terminal)

The application calls Ollama over HTTP:

- `OLLAMA_BASE_URL` (example: `http://localhost:11434`)
- Endpoint used by the app: `POST /api/chat`

### 2.1 Install Ollama

Follow Ollama’s official installation instructions for your OS.

### 2.2 Start the Ollama service

In a terminal:

```bash
ollama serve
```

Keep this running. By default it listens on:

- `http://localhost:11434`

### 2.3 Pull a Llama model (one-time)

In another terminal:

```bash
ollama pull llama3.1:8b
```

You can use other model tags; just set `OLLAMA_MODEL` to match.

### 2.4 Quick terminal sanity check (chat)

```bash
ollama run llama3.1:8b
```

Type a prompt and confirm you get a response.

### 2.5 HTTP sanity check (the same interface the app uses)

```bash
curl http://localhost:11434/api/chat \
  -H 'content-type: application/json' \
  -d '{
    "model": "llama3.1:8b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Say hello in one sentence."}
    ],
    "stream": false
  }'
```

You should see a JSON response containing `message.content`.

## 3) Run the App (Recommended: Docker Compose)

### 3.1 Create `.env`

Create a file named `.env` in the project root.

Minimum required:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/logs
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
```

Enable Slack notifications (optional):

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

Enable email notifications (optional):

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
SMTP_FROM=alerts@example.com
SMTP_TO=oncall@example.com
```

Anomaly detection tuning (optional):

```env
INCIDENT_ERROR_COUNT_THRESHOLD=10
INCIDENT_KEYWORDS=traceback,panic,out of memory,connection refused
```

Notes on `OLLAMA_BASE_URL`:

- Docker Desktop (macOS/Windows): `http://host.docker.internal:11434` typically works.
- Linux: `host.docker.internal` may not exist by default. Use one of:
  - Run Ollama in another container and set `OLLAMA_BASE_URL` to that service name.
  - Set `OLLAMA_BASE_URL` to a reachable host IP address from inside Docker.

### 3.2 Start services

From the project root:

```bash
docker compose up --build
```

What happens:

1. Postgres starts.
2. The API container starts, runs `alembic upgrade head` automatically, then starts Uvicorn.

### 3.3 Verify health endpoints

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### 3.4 Send a sample webhook payload

Non-incident example:

```bash
curl -X POST http://localhost:8000/webhooks/datadog \
  -H 'content-type: application/json' \
  -d '{"logs":[{"timestamp":"2026-05-20T12:00:00Z","status":"info","service":"api","host":"app-1","message":"ok"}]}'
```

Incident example (keyword “traceback” + error level):

```bash
curl -X POST http://localhost:8000/webhooks/datadog \
  -H 'content-type: application/json' \
  -d '{"logs":[{"timestamp":"2026-05-20T12:00:00Z","status":"error","service":"api","host":"app-1","message":"Traceback: boom"}]}'
```

Expected response fields:

- `incident`: true/false
- `incident_id`: present when an incident decision is stored
- `reason`: why rules triggered (or not)
- `summary`: only included when `incident=true` (and Ollama succeeded)

### 3.5 Confirm dedupe/idempotency behavior

Send the exact same JSON again. The service should return the existing `incident_id` and should not re-notify.

Idempotency is based on a stable JSON hash:

- [stable_json_hash](file:///workspace/src/log_anomaly_summariser/util/hashing.py)

## 4) Run the App Without Docker (Local Python)

### 4.1 Install dependencies

```bash
python -m pip install -e ".[test]"
```

### 4.2 Export environment variables

Example (using a locally running Postgres):

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/logs"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.1:8b"
```

### 4.3 Run migrations

```bash
alembic upgrade head
```

### 4.4 Start the server

```bash
uvicorn log_anomaly_summariser.main:app --host 0.0.0.0 --port 8000
```

## 5) Common Troubleshooting

### 5.1 “Ollama connection failed” during incidents

Symptoms:

- Webhook returns 500 (or incident summary missing), and notifications may record `failed`.

Checks:

1. Confirm Ollama is running:
   - `curl http://localhost:11434/api/tags`
2. Confirm `OLLAMA_BASE_URL` from the app can reach Ollama:
   - Docker networking is the most common issue.
3. Confirm the model exists:
   - `ollama list`
   - `ollama pull llama3.1:8b`

### 5.2 Slack notifications not sent

Checks:

- `SLACK_WEBHOOK_URL` is set correctly in `.env`.
- The webhook URL is reachable from the container.

Notification attempts are recorded in Postgres (`notifications` table).

### 5.3 Email notifications not sent

Checks:

- `SMTP_HOST`, `SMTP_FROM`, `SMTP_TO` must be set.
- Credentials and TLS requirements depend on your SMTP provider.

### 5.4 Database errors / migrations

Checks:

- Postgres is up and reachable from the API container.
- `DATABASE_URL` points to the correct host (`postgres` when running in compose).
- Re-run:
  - `alembic upgrade head`

## 6) Useful References (Code)

- API entrypoint: [main.py](file:///workspace/src/log_anomaly_summariser/main.py)
- Graph definition: [build.py](file:///workspace/src/log_anomaly_summariser/graph/build.py)
- Settings/env vars: [settings.py](file:///workspace/src/log_anomaly_summariser/settings.py)
- Ollama client: [ollama.py](file:///workspace/src/log_anomaly_summariser/llm/ollama.py)
- Docker runtime: [Dockerfile](file:///workspace/Dockerfile), [docker-compose.yml](file:///workspace/docker-compose.yml)


# Log Anomaly Summariser

FastAPI webhook that ingests Datadog logs, runs a LangGraph pipeline to detect anomalies, generates a plain-English incident summary using a local Ollama model, persists everything in Postgres, and notifies Slack + email.

## Quickstart (Docker)

1. Create an `.env` file:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/logs
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
SMTP_FROM=alerts@example.com
SMTP_TO=oncall@example.com
INCIDENT_ERROR_COUNT_THRESHOLD=10
INCIDENT_KEYWORDS=traceback,panic,out of memory,connection refused
```

2. Start services:

```
docker compose up --build
```

3. Send a sample payload:

```
curl -X POST http://localhost:8000/webhooks/datadog \
  -H 'content-type: application/json' \
  -d '{"logs":[{"timestamp":"2026-05-20T12:00:00Z","status":"error","service":"api","host":"app-1","message":"Traceback: boom"}]}'
```

## Endpoints

- `POST /webhooks/datadog`
- `GET /healthz`
- `GET /readyz`

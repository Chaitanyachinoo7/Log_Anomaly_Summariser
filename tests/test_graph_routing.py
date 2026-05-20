from __future__ import annotations

import datetime as dt
import uuid

import pytest

from log_anomaly_summariser.graph.build import build_graph
from log_anomaly_summariser.settings import get_settings
from log_anomaly_summariser.storage import repo


@pytest.mark.asyncio
async def test_graph_routes_no_incident(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    settings = get_settings()

    payload_id = uuid.uuid4()
    incident_id = uuid.uuid4()
    created: dict = {}

    class Payload:
        def __init__(self, id_):
            self.id = id_

    class Incident:
        def __init__(self, id_):
            self.id = id_

    async def _get_or_create_payload(*, session, vendor, received_at, payload_json, payload_hash):
        return Payload(payload_id), True

    async def _get_incident_for_payload(session, payload_id_):
        return None

    async def _insert_events(session, payload_id_, events):
        created["events"] = events

    async def _create_incident(*, session, payload_id, decision, severity, rule_reason, summary, model):
        created["decision"] = decision
        created["severity"] = severity
        created["summary"] = summary
        return Incident(incident_id)

    monkeypatch.setattr(repo, "get_or_create_payload", _get_or_create_payload)
    monkeypatch.setattr(repo, "get_incident_for_payload", _get_incident_for_payload)
    monkeypatch.setattr(repo, "insert_events", _insert_events)
    monkeypatch.setattr(repo, "create_incident", _create_incident)

    graph = build_graph(settings)
    state = {
        "vendor": "datadog",
        "received_at": dt.datetime.now(tz=dt.timezone.utc),
        "raw_payload": {"logs": [{"status": "info", "message": "ok"}]},
        "payload_hash": "x",
        "db_session": object(),
        "notify_slack": False,
        "notify_email": False,
    }
    result = await graph.ainvoke(state)

    assert created["decision"] == "no_incident"
    assert result["incident_id"] == incident_id
    assert result.get("summary") is None


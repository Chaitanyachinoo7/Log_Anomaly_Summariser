from __future__ import annotations

from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.storage import repo


async def persist_payload(state: GraphState) -> GraphState:
    session = state["db_session"]
    payload, _created = await repo.get_or_create_payload(
        session=session,
        vendor=state["vendor"],
        received_at=state["received_at"],
        payload_json=state["raw_payload"],
        payload_hash=state["payload_hash"],
    )
    existing_incident = await repo.get_incident_for_payload(session, payload.id)
    return {
        "payload_id": payload.id,
        "existing_incident_id": existing_incident.id if existing_incident else None,
        "incident_id": existing_incident.id if existing_incident else None,
        "summary": existing_incident.summary if existing_incident else None,
        "anomaly_incident": (existing_incident.decision == "incident") if existing_incident else False,
        "anomaly_severity": existing_incident.severity if existing_incident else "low",
        "anomaly_reason": existing_incident.rule_reason if existing_incident else "",
    }


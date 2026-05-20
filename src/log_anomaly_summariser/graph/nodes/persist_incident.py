from __future__ import annotations

from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.settings import Settings
from log_anomaly_summariser.storage import repo


async def persist_incident(state: GraphState, settings: Settings) -> GraphState:
    if state.get("existing_incident_id") is not None:
        return {}

    session = state["db_session"]
    decision = "incident" if state.get("anomaly_incident") else "no_incident"
    incident = await repo.create_incident(
        session=session,
        payload_id=state["payload_id"],
        decision=decision,
        severity=state.get("anomaly_severity") or "low",
        rule_reason=state.get("anomaly_reason") or "",
        summary=state.get("summary") if decision == "incident" else None,
        model=settings.ollama_model if decision == "incident" else None,
    )
    return {"incident_id": incident.id}


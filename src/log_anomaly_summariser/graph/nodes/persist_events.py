from __future__ import annotations

from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.storage import repo


async def persist_events(state: GraphState) -> GraphState:
    await repo.insert_events(state["db_session"], state["payload_id"], state.get("normalized_events", []))
    return {}


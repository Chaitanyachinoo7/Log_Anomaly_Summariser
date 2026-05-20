from __future__ import annotations

from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.webhooks.datadog import normalize_datadog_payload


async def normalize(state: GraphState) -> GraphState:
    events = normalize_datadog_payload(state["raw_payload"])
    return {"normalized_events": events}


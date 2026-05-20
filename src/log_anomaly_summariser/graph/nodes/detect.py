from __future__ import annotations

from log_anomaly_summariser.anomaly.rules import detect_anomaly
from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.settings import Settings


async def detect(state: GraphState, settings: Settings) -> GraphState:
    result = detect_anomaly(
        events=state.get("normalized_events", []),
        error_count_threshold=settings.incident_error_count_threshold,
        keywords_csv=settings.incident_keywords,
    )
    return {
        "anomaly_incident": result.incident,
        "anomaly_severity": result.severity,
        "anomaly_score": result.score,
        "anomaly_reason": result.reason,
        "anomaly_signals": result.top_signals,
    }


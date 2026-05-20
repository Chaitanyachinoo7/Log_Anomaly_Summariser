from __future__ import annotations

from langgraph.graph import END, StateGraph

from log_anomaly_summariser.graph.nodes.detect import detect
from log_anomaly_summariser.graph.nodes.normalize import normalize
from log_anomaly_summariser.graph.nodes.notify import notify
from log_anomaly_summariser.graph.nodes.persist import persist_payload
from log_anomaly_summariser.graph.nodes.persist_events import persist_events
from log_anomaly_summariser.graph.nodes.persist_incident import persist_incident
from log_anomaly_summariser.graph.nodes.summarize import summarize_incident
from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.settings import Settings


def build_graph(settings: Settings):
    graph = StateGraph(GraphState)

    async def _detect(state: GraphState) -> GraphState:
        return await detect(state, settings)

    async def _summarize(state: GraphState) -> GraphState:
        return await summarize_incident(state, settings)

    async def _persist_incident(state: GraphState) -> GraphState:
        return await persist_incident(state, settings)

    async def _notify(state: GraphState) -> GraphState:
        return await notify(state, settings)

    graph.add_node("persist_payload", persist_payload)
    graph.add_node("normalize", normalize)
    graph.add_node("persist_events", persist_events)
    graph.add_node("detect", _detect)
    graph.add_node("summarize", _summarize)
    graph.add_node("persist_incident", _persist_incident)
    graph.add_node("notify", _notify)

    graph.set_entry_point("persist_payload")

    def _after_persist(state: GraphState) -> str:
        return "existing" if state.get("existing_incident_id") is not None else "new"

    graph.add_conditional_edges(
        "persist_payload",
        _after_persist,
        {"existing": END, "new": "normalize"},
    )

    graph.add_edge("normalize", "persist_events")
    graph.add_edge("persist_events", "detect")

    def _after_detect(state: GraphState) -> str:
        return "incident" if state.get("anomaly_incident") else "no_incident"

    graph.add_conditional_edges(
        "detect",
        _after_detect,
        {"incident": "summarize", "no_incident": "persist_incident"},
    )

    graph.add_edge("summarize", "persist_incident")

    def _after_persist_incident(state: GraphState) -> str:
        return "notify" if state.get("anomaly_incident") else "done"

    graph.add_conditional_edges(
        "persist_incident",
        _after_persist_incident,
        {"notify": "notify", "done": END},
    )

    graph.add_edge("notify", END)

    return graph.compile()

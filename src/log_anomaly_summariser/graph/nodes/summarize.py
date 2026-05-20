from __future__ import annotations

import datetime as dt

from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.llm.ollama import OllamaClient
from log_anomaly_summariser.settings import Settings


def _time_range(events: list[dict]) -> tuple[str | None, str | None]:
    ts = [e.get("ts") for e in events if isinstance(e.get("ts"), dt.datetime)]
    if not ts:
        return None, None
    start = min(ts).isoformat()
    end = max(ts).isoformat()
    return start, end


def _sample_lines(events: list[dict], limit: int = 25) -> list[str]:
    lines: list[str] = []
    for e in events:
        msg = e.get("message")
        if not msg:
            continue
        level = e.get("level") or ""
        service = e.get("service") or ""
        host = e.get("host") or ""
        lines.append(f"[{level}] {service} {host} {msg}".strip())
        if len(lines) >= limit:
            break
    return lines


async def summarize_incident(state: GraphState, settings: Settings) -> GraphState:
    events = state.get("normalized_events", [])
    start, end = _time_range(events)
    sample = _sample_lines(events)
    system = "You are an on-call assistant. Write concise, plain-English incident summaries from application logs."
    user_parts: list[str] = []
    user_parts.append(f"Decision: incident=true severity={state.get('anomaly_severity')} reason={state.get('anomaly_reason')}")
    if start and end:
        user_parts.append(f"Time range: {start} to {end}")
    signals = state.get("anomaly_signals") or []
    if signals:
        user_parts.append("Signals: " + "; ".join(signals))
    if sample:
        user_parts.append("Key log lines:")
        user_parts.extend(sample)
    user_parts.append(
        "Return a report with headings: What happened; Impact; Most likely cause; Evidence; Suggested next actions."
    )
    client = OllamaClient(settings.ollama_base_url)
    summary = await client.chat(
        model=settings.ollama_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": "\n".join(user_parts)}],
    )
    return {"summary": summary}


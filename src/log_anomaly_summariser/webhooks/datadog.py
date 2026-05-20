from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from log_anomaly_summariser.util.time import parse_timestamp


class DatadogLogItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str | None = None
    status: str | None = None
    service: str | None = None
    host: str | None = None
    timestamp: Any | None = None


def _as_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    return [payload]


def _find_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("logs", "data", "events", "items", "records"):
        value = payload.get(key)
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            return value
    if all(isinstance(v, (str, int, float, dict, list, type(None))) for v in payload.values()):
        return [payload]
    return []


def normalize_datadog_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = _find_records(payload)
    events: list[dict[str, Any]] = []
    for raw in items:
        item = DatadogLogItem.model_validate(raw)
        error_message = None
        if isinstance(raw.get("error"), dict):
            error_message = raw["error"].get("message")
        message = (
            item.message
            or raw.get("content")
            or raw.get("msg")
            or raw.get("title")
            or error_message
        )
        level = item.status or raw.get("level") or raw.get("severity")
        service = item.service or raw.get("service_name") or raw.get("app") or raw.get("ddsource")
        host = item.host or raw.get("hostname") or raw.get("host_name")
        ts = parse_timestamp(item.timestamp or raw.get("date") or raw.get("time"))
        events.append(
            {
                "ts": ts,
                "level": (str(level).lower() if level is not None else None),
                "service": str(service) if service is not None else None,
                "host": str(host) if host is not None else None,
                "message": str(message) if message is not None else None,
                "attributes": raw,
            }
        )
    return events

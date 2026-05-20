from __future__ import annotations

from log_anomaly_summariser.webhooks.datadog import normalize_datadog_payload


def test_normalize_datadog_payload_extracts_core_fields():
    payload = {
        "logs": [
            {
                "timestamp": "2026-05-20T12:00:00Z",
                "status": "error",
                "service": "api",
                "host": "app-1",
                "message": "Traceback: boom",
                "extra": {"k": "v"},
            }
        ]
    }
    events = normalize_datadog_payload(payload)
    assert len(events) == 1
    e = events[0]
    assert e["level"] == "error"
    assert e["service"] == "api"
    assert e["host"] == "app-1"
    assert "Traceback" in (e["message"] or "")
    assert e["ts"] is not None


from __future__ import annotations

from log_anomaly_summariser.anomaly.rules import detect_anomaly


def test_detect_anomaly_no_incident():
    result = detect_anomaly(events=[{"level": "info", "message": "ok"}], error_count_threshold=3, keywords_csv="panic")
    assert result.incident is False
    assert result.severity == "low"


def test_detect_anomaly_incident_by_error_count():
    events = [{"level": "error", "message": "boom"} for _ in range(3)]
    result = detect_anomaly(events=events, error_count_threshold=3, keywords_csv="")
    assert result.incident is True
    assert result.severity in {"medium", "high"}


from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnomalyResult:
    incident: bool
    severity: str
    score: float
    reason: str
    top_signals: list[str]


def detect_anomaly(
    events: list[dict],
    error_count_threshold: int,
    keywords_csv: str,
) -> AnomalyResult:
    keywords = [k.strip().lower() for k in keywords_csv.split(",") if k.strip()]
    error_events = [
        e for e in events if (e.get("level") or "").lower() in {"error", "err", "fatal", "critical"} or "exception" in (e.get("message") or "").lower()
    ]
    error_count = len(error_events)
    keyword_hits: list[str] = []
    for e in events:
        msg = (e.get("message") or "").lower()
        for k in keywords:
            if k and k in msg:
                keyword_hits.append(k)
    keyword_hits = sorted(set(keyword_hits))

    signals: list[str] = []
    signals.append(f"errors={error_count}")
    if keyword_hits:
        signals.append("keywords=" + ",".join(keyword_hits[:5]))

    incident = error_count >= error_count_threshold or bool(keyword_hits)
    if not incident:
        return AnomalyResult(False, "low", 0.0, "No incident rules triggered.", signals)

    if error_count >= max(error_count_threshold * 2, error_count_threshold + 10) or any(
        k in {"panic", "out of memory", "segmentation fault"} for k in keyword_hits
    ):
        severity = "high"
        score = 0.9
    elif error_count >= error_count_threshold:
        severity = "medium"
        score = 0.6
    else:
        severity = "medium"
        score = 0.5

    reasons: list[str] = []
    if error_count >= error_count_threshold:
        reasons.append(f"error_count={error_count}>=threshold={error_count_threshold}")
    if keyword_hits:
        reasons.append("keyword_hits=" + ",".join(keyword_hits))
    reason = "; ".join(reasons) if reasons else "Rules triggered."

    return AnomalyResult(True, severity, score, reason, signals)


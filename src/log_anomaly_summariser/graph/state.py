from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession


class GraphState(TypedDict, total=False):
    vendor: str
    received_at: dt.datetime
    raw_payload: dict[str, Any]
    payload_hash: str

    db_session: AsyncSession

    payload_id: uuid.UUID
    existing_incident_id: uuid.UUID | None
    normalized_events: list[dict[str, Any]]

    anomaly_incident: bool
    anomaly_severity: str
    anomaly_score: float
    anomaly_reason: str
    anomaly_signals: list[str]

    summary: str | None
    incident_id: uuid.UUID | None

    notify_slack: bool
    notify_email: bool
    slack_status: str | None
    email_status: str | None
    slack_error: str | None
    email_error: str | None


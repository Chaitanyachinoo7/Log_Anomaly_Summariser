from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from log_anomaly_summariser.storage.models import Incident, LogEvent, Notification, WebhookPayload


async def get_payload_by_hash(session: AsyncSession, payload_hash: str) -> WebhookPayload | None:
    result = await session.execute(select(WebhookPayload).where(WebhookPayload.payload_hash == payload_hash))
    return result.scalar_one_or_none()


async def create_payload(
    session: AsyncSession,
    vendor: str,
    received_at: dt.datetime,
    payload_json: dict[str, Any],
    payload_hash: str,
) -> WebhookPayload:
    payload = WebhookPayload(
        vendor=vendor,
        received_at=received_at,
        payload_json=payload_json,
        payload_hash=payload_hash,
    )
    session.add(payload)
    await session.flush()
    return payload


async def get_or_create_payload(
    session: AsyncSession,
    vendor: str,
    received_at: dt.datetime,
    payload_json: dict[str, Any],
    payload_hash: str,
) -> tuple[WebhookPayload, bool]:
    existing = await get_payload_by_hash(session, payload_hash)
    if existing is not None:
        return existing, False
    return await create_payload(session, vendor, received_at, payload_json, payload_hash), True


async def insert_events(session: AsyncSession, payload_id: uuid.UUID, events: list[dict[str, Any]]) -> None:
    rows = [
        LogEvent(
            payload_id=payload_id,
            ts=e.get("ts"),
            level=e.get("level"),
            service=e.get("service"),
            host=e.get("host"),
            message=e.get("message"),
            attributes_json=e.get("attributes") or {},
        )
        for e in events
    ]
    session.add_all(rows)


async def get_incident_for_payload(session: AsyncSession, payload_id: uuid.UUID) -> Incident | None:
    result = await session.execute(select(Incident).where(Incident.payload_id == payload_id))
    return result.scalar_one_or_none()


async def create_incident(
    session: AsyncSession,
    payload_id: uuid.UUID,
    decision: str,
    severity: str,
    rule_reason: str,
    summary: str | None,
    model: str | None,
) -> Incident:
    incident = Incident(
        payload_id=payload_id,
        decision=decision,
        severity=severity,
        rule_reason=rule_reason,
        summary=summary,
        model=model,
    )
    session.add(incident)
    await session.flush()
    return incident


async def add_notification_result(
    session: AsyncSession,
    incident_id: uuid.UUID,
    channel: str,
    status: str,
    error: str | None,
) -> Notification:
    row = Notification(incident_id=incident_id, channel=channel, status=status, error=error)
    session.add(row)
    await session.flush()
    return row


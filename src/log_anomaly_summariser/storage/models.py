from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class WebhookPayload(Base):
    __tablename__ = "webhook_payloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=dt.datetime.utcnow)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    events: Mapped[list["LogEvent"]] = relationship(back_populates="payload", cascade="all, delete-orphan")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="payload", cascade="all, delete-orphan")


class LogEvent(Base):
    __tablename__ = "log_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("webhook_payloads.id"), nullable=False)

    ts: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    host: Mapped[str | None] = mapped_column(String(256), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    payload: Mapped[WebhookPayload] = relationship(back_populates="events")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=dt.datetime.utcnow)
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("webhook_payloads.id"), nullable=False)

    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_reason: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    payload: Mapped[WebhookPayload] = relationship(back_populates="incidents")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="incident", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=dt.datetime.utcnow)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="notifications")


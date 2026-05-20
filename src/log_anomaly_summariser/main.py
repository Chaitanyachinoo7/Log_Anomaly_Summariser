from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from log_anomaly_summariser.graph.build import build_graph
from log_anomaly_summariser.settings import Settings, get_settings
from log_anomaly_summariser.storage.db import create_engine, create_sessionmaker
from log_anomaly_summariser.util.hashing import stable_json_hash


def create_app() -> FastAPI:
    app = FastAPI(title="Log Anomaly Summariser")

    @app.on_event("startup")
    async def _startup() -> None:
        settings = get_settings()
        engine = create_engine(settings)
        sessionmaker = create_sessionmaker(engine)
        graph = build_graph(settings)
        app.state.settings = settings
        app.state.engine = engine
        app.state.sessionmaker = sessionmaker
        app.state.graph = graph

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            await engine.dispose()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/webhooks/datadog")
    async def datadog_webhook(request: Request) -> JSONResponse:
        try:
            payload: dict[str, Any] = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        settings: Settings = app.state.settings
        received_at = dt.datetime.now(tz=dt.timezone.utc)
        payload_hash = stable_json_hash(payload)

        async with app.state.sessionmaker() as session:
            try:
                state = {
                    "vendor": "datadog",
                    "received_at": received_at,
                    "raw_payload": payload,
                    "payload_hash": payload_hash,
                    "db_session": session,
                    "notify_slack": True,
                    "notify_email": True,
                }
                result = await app.state.graph.ainvoke(state)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        incident_id = result.get("incident_id")
        summary = result.get("summary")
        incident = bool(result.get("anomaly_incident"))
        reason = result.get("anomaly_reason") or ""

        out = {
            "received_at": received_at.isoformat(),
            "incident": incident,
            "incident_id": str(incident_id) if isinstance(incident_id, uuid.UUID) else None,
            "reason": reason,
            "summary": summary if incident else None,
        }
        return JSONResponse(out)

    return app


app = create_app()


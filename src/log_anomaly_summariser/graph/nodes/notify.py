from __future__ import annotations

from log_anomaly_summariser.graph.state import GraphState
from log_anomaly_summariser.notify.email import send_email
from log_anomaly_summariser.notify.slack import send_slack
from log_anomaly_summariser.settings import Settings
from log_anomaly_summariser.storage import repo


async def notify(state: GraphState, settings: Settings) -> GraphState:
    incident_id = state.get("incident_id")
    if incident_id is None:
        return {}

    session = state["db_session"]
    summary = state.get("summary") or ""
    title = f"Incident {incident_id} ({state.get('anomaly_severity')})"
    text = f"{title}\n\n{summary}".strip()

    out: dict = {}

    if settings.slack_webhook_url and state.get("notify_slack", True):
        try:
            await send_slack(settings.slack_webhook_url, text)
            await repo.add_notification_result(session, incident_id, "slack", "sent", None)
            out["slack_status"] = "sent"
        except Exception as e:
            await repo.add_notification_result(session, incident_id, "slack", "failed", str(e))
            out["slack_status"] = "failed"
            out["slack_error"] = str(e)

    if settings.smtp_host and settings.smtp_from and settings.smtp_to and state.get("notify_email", True):
        to_addrs = [a.strip() for a in settings.smtp_to.split(",") if a.strip()]
        if to_addrs:
            try:
                await send_email(
                    host=settings.smtp_host,
                    port=settings.smtp_port,
                    user=settings.smtp_user,
                    password=settings.smtp_pass,
                    from_addr=settings.smtp_from,
                    to_addrs=to_addrs,
                    subject=title,
                    body=text,
                )
                await repo.add_notification_result(session, incident_id, "email", "sent", None)
                out["email_status"] = "sent"
            except Exception as e:
                await repo.add_notification_result(session, incident_id, "email", "failed", str(e))
                out["email_status"] = "failed"
                out["email_error"] = str(e)

    return out


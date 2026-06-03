from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.api import IncidentInput


def send_summary_to_pulsewatch(incident: IncidentInput, summary: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.pulsewatch_callback_enabled:
        return {"status": "skipped", "reason": "pulsewatch callback disabled"}
    if not settings.pulsewatch_base_url or not incident.incident_id:
        return {"status": "skipped", "reason": "pulsewatch callback is not configured"}

    url = (
        settings.pulsewatch_base_url.rstrip("/")
        + settings.pulsewatch_summary_path.format(incident_id=incident.incident_id)
    )
    headers = {"Content-Type": "application/json"}
    if settings.pulsewatch_api_key:
        headers["X-API-Key"] = settings.pulsewatch_api_key

    payload = {"comment": _render_summary_comment(summary)}
    try:
        with httpx.Client(timeout=settings.http_timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {"status": "failed", "error": str(exc)}

    return {"status": "sent", "target": "pulsewatch", "status_code": response.status_code}


def send_enriched_notification(incident: IncidentInput, summary: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.notification_callback_enabled:
        return {"status": "skipped", "reason": "notification callback disabled"}
    if not settings.notification_service_url or not settings.notification_service_api_key:
        return {"status": "skipped", "reason": "notification service is not configured"}

    user_id = incident.metadata.get("notification_user_id")
    if not user_id:
        return {"status": "skipped", "reason": "incident metadata has no notification_user_id"}

    url = f"{settings.notification_service_url.rstrip('/')}/api/notifications/"
    payload = {
        "user_id": user_id,
        "subject": summary.get("headline", f"{incident.severity.value}: {incident.fingerprint}"),
        "message": _render_summary_comment(summary),
        "idempotency_key": f"pulseops:{incident.incident_id or incident.fingerprint}",
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": settings.notification_service_api_key,
    }

    try:
        with httpx.Client(timeout=settings.http_timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {"status": "failed", "error": str(exc)}

    return {"status": "sent", "target": "notification_service", "status_code": response.status_code}


def _render_summary_comment(summary: dict[str, Any]) -> str:
    evidence = summary.get("evidence", [])
    evidence_lines = "\n".join(f"- {item}" for item in evidence[:8])
    comment = (
        f"{summary.get('headline', 'Incident diagnostics')}\n\n"
        f"Suspected cause: {summary.get('suspected_cause', 'unknown')}\n"
        f"Confidence: {int(float(summary.get('confidence', 0)) * 100)}%\n\n"
        f"Evidence:\n{evidence_lines or '- no evidence collected'}\n\n"
        f"Next action: {summary.get('next_action', 'operator review required')}"
    )
    if len(comment) <= 2000:
        return comment
    return comment[:1997].rstrip() + "..."

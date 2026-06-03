from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import Execution, ServiceDependency
from app.schemas.api import IncidentInput


def build_incident_context(db: Session, incident: IncidentInput) -> dict[str, Any]:
    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)

    previous_executions = list(
        db.scalars(
            select(Execution)
            .where(Execution.fingerprint == incident.fingerprint)
            .where(Execution.created_at >= since_24h)
            .order_by(Execution.created_at.desc())
            .limit(10)
        ).all()
    )

    dependencies = list(
        db.scalars(
            select(ServiceDependency)
            .where(ServiceDependency.service_name == incident.target)
            .order_by(ServiceDependency.criticality.asc(), ServiceDependency.dependency_name.asc())
        ).all()
    )

    similar_active_incidents = _fetch_similar_active_incidents(incident)
    deploy_marker = _extract_deploy_marker(incident)
    context_notes = _build_context_notes(
        incident=incident,
        previous_executions=previous_executions,
        similar_active_incidents=similar_active_incidents,
        deploy_marker=deploy_marker,
    )

    return {
        "incident_details": incident.model_dump(mode="json"),
        "fingerprint_occurrences_24h": len(previous_executions),
        "previous_executions_for_fingerprint": [
            {
                "id": execution.id,
                "status": execution.status,
                "created_at": execution.created_at.isoformat(),
                "suspected_cause": execution.suspected_cause,
                "confidence": execution.confidence,
                "summary": execution.summary,
            }
            for execution in previous_executions[:5]
        ],
        "last_notifications": _extract_last_notifications(previous_executions),
        "similar_active_incidents": similar_active_incidents,
        "target_health": {
            "target": incident.target,
            "healthcheck_url": incident.metadata.get("healthcheck_url"),
        },
        "recent_deploy_marker": deploy_marker,
        "dependencies": [
            {
                "service_name": dependency.service_name,
                "dependency_name": dependency.dependency_name,
                "dependency_type": dependency.dependency_type,
                "healthcheck_url": dependency.healthcheck_url,
                "criticality": dependency.criticality,
            }
            for dependency in dependencies
        ],
        "context_notes": context_notes,
    }


def _build_context_notes(
    incident: IncidentInput,
    previous_executions: list[Execution],
    similar_active_incidents: list[dict[str, Any]],
    deploy_marker: dict[str, Any] | None,
) -> list[str]:
    notes: list[str] = []
    if previous_executions:
        notes.append(
            f"This fingerprint occurred {len(previous_executions)} times in the last 24h."
        )
        last_execution = previous_executions[0]
        if last_execution.status == "FAILED":
            notes.append(
                "Last runbook execution failed for this fingerprint; inspect the prior "
                f"execution {last_execution.id}."
            )
        elif last_execution.suspected_cause:
            notes.append(
                "Last runbook execution suspected "
                f"{last_execution.suspected_cause} with confidence {last_execution.confidence:.2f}."
            )

    if similar_active_incidents:
        critical_related = [
            item for item in similar_active_incidents if item.get("severity") == "CRITICAL"
        ]
        if critical_related:
            notes.append(
                f"A related CRITICAL incident is active for target {incident.target}."
            )

    if deploy_marker:
        version = deploy_marker.get("version") or "unknown version"
        notes.append(f"Recent deploy marker detected for {incident.target}: {version}.")

    return notes


def _extract_last_notifications(previous_executions: list[Execution]) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []
    for execution in previous_executions:
        integration_result = execution.summary.get("integrations", {}) if execution.summary else {}
        notification = integration_result.get("notification_service")
        if notification:
            notifications.append(
                {
                    "execution_id": execution.id,
                    "status": notification.get("status"),
                    "detail": notification,
                }
            )
    return notifications[:5]


def _extract_deploy_marker(incident: IncidentInput) -> dict[str, Any] | None:
    version = incident.metadata.get("deploy_version") or incident.metadata.get("release")
    deployed_at = incident.metadata.get("deployed_at")
    if not version and not deployed_at:
        return None
    return {
        "version": version,
        "deployed_at": deployed_at,
        "source": incident.metadata.get("deploy_source", "incident_metadata"),
    }


def _fetch_similar_active_incidents(incident: IncidentInput) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.pulsewatch_base_url:
        return []

    url = f"{settings.pulsewatch_base_url.rstrip('/')}/api/v1/incidents"
    headers = {}
    if settings.pulsewatch_api_key:
        headers["X-API-Key"] = settings.pulsewatch_api_key

    try:
        with httpx.Client(timeout=settings.http_timeout_seconds) as client:
            response = client.get(
                url,
                params={"target": incident.target, "limit": 10},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []

    incidents = payload if isinstance(payload, list) else payload.get("items", [])

    active_statuses = {"NEW", "ACKNOWLEDGED", "IN_PROGRESS"}
    return [
        item
        for item in incidents
        if item.get("fingerprint") != incident.fingerprint
        and item.get("status") in active_statuses
    ][:5]

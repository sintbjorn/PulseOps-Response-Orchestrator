from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ExecutionStatus
from app.domain.models import Execution, ResponsePolicy
from app.schemas.api import IncidentInput


@dataclass(frozen=True)
class SuppressionDecision:
    action: str
    reason: str
    reused_execution: Execution | None = None


FINAL_REUSABLE_STATUSES = {
    ExecutionStatus.SUCCEEDED.value,
    ExecutionStatus.FAILED.value,
    ExecutionStatus.WAITING_FOR_OPERATOR.value,
}


def evaluate_suppression(
    db: Session,
    incident: IncidentInput,
    policy: ResponsePolicy,
) -> SuppressionDecision:
    if incident.idempotency_key:
        existing = db.scalar(
            select(Execution).where(Execution.idempotency_key == incident.idempotency_key)
        )
        if existing:
            return SuppressionDecision(
                action="reuse",
                reason="idempotency key already processed",
                reused_execution=existing,
            )

    now = datetime.now(UTC)
    active_statuses = [
        ExecutionStatus.RUNNING.value,
        ExecutionStatus.WAITING_FOR_OPERATOR.value,
    ]

    active_existing = db.scalar(
        select(Execution)
        .where(Execution.fingerprint == incident.fingerprint)
        .where(Execution.status.in_(active_statuses))
        .order_by(Execution.created_at.desc())
    )
    if active_existing:
        return SuppressionDecision(
            action="reuse" if policy.reuse_recent_execution else "suppress",
            reason="an execution is already active for this fingerprint",
            reused_execution=active_existing if policy.reuse_recent_execution else None,
        )

    if policy.cooldown_seconds > 0:
        cooldown_since = now - timedelta(seconds=policy.cooldown_seconds)
        recent = _latest_reusable_execution(db, incident.fingerprint, cooldown_since)
        if recent:
            return SuppressionDecision(
                action="reuse" if policy.reuse_recent_execution else "suppress",
                reason=(
                    "same fingerprint was diagnosed "
                    f"within the last {policy.cooldown_seconds} seconds"
                ),
                reused_execution=recent if policy.reuse_recent_execution else None,
            )

    if incident.incident_id and policy.max_executions_per_incident > 0:
        incident_execution_count = db.scalar(
            select(func.count())
            .select_from(Execution)
            .where(Execution.incident_id == incident.incident_id)
            .where(Execution.policy_id == policy.id)
            .where(
                Execution.status.notin_(
                    [
                        ExecutionStatus.REUSED.value,
                        ExecutionStatus.SUPPRESSED.value,
                        ExecutionStatus.SKIPPED.value,
                    ]
                )
            )
        )
        if (incident_execution_count or 0) >= policy.max_executions_per_incident:
            latest = _latest_reusable_execution(db, incident.fingerprint)
            return SuppressionDecision(
                action="reuse" if policy.reuse_recent_execution and latest else "suppress",
                reason="max executions per incident reached",
                reused_execution=latest if policy.reuse_recent_execution else None,
            )

    if policy.max_executions_per_fingerprint_per_hour > 0:
        hour_since = now - timedelta(hours=1)
        fingerprint_count = db.scalar(
            select(func.count())
            .select_from(Execution)
            .where(Execution.fingerprint == incident.fingerprint)
            .where(Execution.created_at >= hour_since)
            .where(Execution.policy_id == policy.id)
            .where(
                Execution.status.notin_(
                    [
                        ExecutionStatus.REUSED.value,
                        ExecutionStatus.SUPPRESSED.value,
                        ExecutionStatus.SKIPPED.value,
                    ]
                )
            )
        )
        if (fingerprint_count or 0) >= policy.max_executions_per_fingerprint_per_hour:
            latest = _latest_reusable_execution(db, incident.fingerprint, hour_since)
            return SuppressionDecision(
                action="reuse" if policy.reuse_recent_execution and latest else "suppress",
                reason="max executions per fingerprint per hour reached",
                reused_execution=latest if policy.reuse_recent_execution else None,
            )

    return SuppressionDecision(action="execute", reason="policy allows execution")


def _latest_reusable_execution(
    db: Session,
    fingerprint: str,
    since: datetime | None = None,
) -> Execution | None:
    query = (
        select(Execution)
        .where(Execution.fingerprint == fingerprint)
        .where(Execution.status.in_(FINAL_REUSABLE_STATUSES))
        .order_by(Execution.created_at.desc())
    )
    if since:
        query = query.where(Execution.created_at >= since)
    return db.scalar(query)

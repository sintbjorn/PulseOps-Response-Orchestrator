from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.metrics import policy_simulation_counter
from app.domain.enums import PolicyMode
from app.domain.models import ResponsePolicy, RunbookVersion
from app.schemas.api import IncidentInput, PolicySimulationRequest, PolicySimulationResponse


def match_policy(
    db: Session,
    incident: IncidentInput | PolicySimulationRequest,
) -> ResponsePolicy | None:
    policies = db.scalars(
        select(ResponsePolicy)
        .where(ResponsePolicy.enabled.is_(True))
        .order_by(ResponsePolicy.priority.desc(), ResponsePolicy.id.asc())
    ).all()

    for policy in policies:
        if _policy_matches(policy, incident):
            return policy
    return None


def get_current_runbook_version(db: Session, policy: ResponsePolicy) -> RunbookVersion | None:
    return db.scalar(
        select(RunbookVersion).where(
            RunbookVersion.runbook_id == policy.runbook_id,
            RunbookVersion.version == policy.runbook.current_version,
        )
    )


def simulate_policy(db: Session, request: PolicySimulationRequest) -> PolicySimulationResponse:
    policy = match_policy(db, request)
    if policy is None:
        policy_simulation_counter.labels(matched="false").inc()
        return PolicySimulationResponse(
            matched_policy=None,
            runbook=None,
            runbook_version=None,
            mode=None,
            would_execute_steps=[],
            suppression={"action": "skip", "reason": "no matching enabled policy"},
        )

    runbook_version = get_current_runbook_version(db, policy)
    steps = []
    if runbook_version:
        steps = [
            step.get("name", "Unnamed step")
            for step in runbook_version.definition.get("steps", [])
        ]

    policy_simulation_counter.labels(matched="true").inc()
    return PolicySimulationResponse(
        matched_policy=policy.name,
        runbook=policy.runbook.name,
        runbook_version=runbook_version.version if runbook_version else None,
        mode=PolicyMode(policy.mode),
        would_execute_steps=steps,
        suppression={
            "cooldown_seconds": policy.cooldown_seconds,
            "max_executions_per_incident": policy.max_executions_per_incident,
            "max_executions_per_fingerprint_per_hour": (
                policy.max_executions_per_fingerprint_per_hour
            ),
            "reuse_recent_execution": policy.reuse_recent_execution,
        },
    )


def _policy_matches(
    policy: ResponsePolicy,
    incident: IncidentInput | PolicySimulationRequest,
) -> bool:
    if policy.severity and policy.severity != incident.severity.value:
        return False
    if policy.source and policy.source != incident.source:
        return False
    if policy.target and policy.target != incident.target:
        return False
    if policy.fingerprint and policy.fingerprint != incident.fingerprint:
        return False
    return not (
        policy.fingerprint_contains
        and policy.fingerprint_contains not in incident.fingerprint
    )

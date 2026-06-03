from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import DependencyCriticality, DependencyType, PolicyMode, RunbookStepType
from app.domain.models import ResponsePolicy, Runbook, RunbookVersion, ServiceDependency


def seed_demo_data(db: Session) -> None:
    runbook = db.scalar(select(Runbook).where(Runbook.name == "High API Latency Diagnostics"))
    if runbook is None:
        runbook = Runbook(name="High API Latency Diagnostics", current_version=1)
        db.add(runbook)
        db.flush()
        db.add(
            RunbookVersion(
                runbook_id=runbook.id,
                version=1,
                created_by="system",
                changelog="Initial diagnostic runbook for API latency incidents.",
                definition={
                    "description": (
                        "Collect readiness, dependency, metric, PulseWatch, "
                        "and remediation evidence."
                    ),
                    "steps": [
                        {
                            "name": "Check API readiness",
                            "type": RunbookStepType.HTTP_CHECK.value,
                            "config": {
                                "url": "{{metadata.healthcheck_url}}",
                                "expected_statuses": [200],
                                "timeout_seconds": 3,
                            },
                        },
                        {
                            "name": "Check dependency readiness",
                            "type": RunbookStepType.DEPENDENCY_HEALTH.value,
                            "config": {
                                "expected_statuses": [200],
                                "timeout_seconds": 3,
                            },
                        },
                        {
                            "name": "Check 5xx rate",
                            "type": RunbookStepType.METRIC_QUERY.value,
                            "config": {
                                "metric_path": "metrics.5xx_rate",
                                "threshold": 0.05,
                                "operator": "gt",
                            },
                        },
                        {
                            "name": "Find related incidents",
                            "type": RunbookStepType.PULSEWATCH_LOOKUP.value,
                            "config": {},
                        },
                        {
                            "name": "Add deployment investigation hint",
                            "type": RunbookStepType.STATIC_HINT.value,
                            "config": {
                                "message": (
                                    "Compare the incident timestamp with the latest deploy marker."
                                ),
                                "evidence": [
                                    "database readiness should be compared with API readiness",
                                    (
                                        "latency regressions after deploy often point "
                                        "to application changes"
                                    ),
                                ],
                            },
                        },
                        {
                            "name": "Preview safe remediation",
                            "type": RunbookStepType.REMEDIATION_PREVIEW.value,
                            "config": {
                                "risk_level": "MEDIUM",
                                "requires_approval": True,
                                "suggested_remediation": [
                                    {
                                        "action": (
                                            "Check deploy 1.8.4 and prepare rollback candidate."
                                        ),
                                        "risk_level": "MEDIUM",
                                        "requires_approval": True,
                                    },
                                    {
                                        "action": (
                                            "Restart API workers only after dependency health "
                                            "is confirmed."
                                        ),
                                        "risk_level": "MEDIUM",
                                        "requires_approval": True,
                                    },
                                ],
                            },
                        },
                    ],
                },
            )
        )

    db.flush()
    policy = db.scalar(
        select(ResponsePolicy).where(ResponsePolicy.name == "Critical API latency policy")
    )
    if policy is None:
        db.add(
            ResponsePolicy(
                name="Critical API latency policy",
                description=(
                    "Run diagnostics for critical latency fingerprints on renovation-flip-api."
                ),
                enabled=True,
                priority=200,
                severity="CRITICAL",
                target="renovation-flip-api",
                fingerprint_contains="latency",
                mode=PolicyMode.DIAGNOSTIC_ONLY.value,
                runbook_id=runbook.id,
                cooldown_seconds=300,
                max_executions_per_incident=1,
                max_executions_per_fingerprint_per_hour=3,
                reuse_recent_execution=True,
            )
        )

    dependencies = [
        ("postgres", DependencyType.DATABASE.value, DependencyCriticality.REQUIRED.value),
        ("redis", DependencyType.CACHE.value, DependencyCriticality.REQUIRED.value),
        (
            "notification-service",
            DependencyType.INTERNAL_SERVICE.value,
            DependencyCriticality.DEGRADED_OK.value,
        ),
        (
            "listing-parser",
            DependencyType.INTERNAL_SERVICE.value,
            DependencyCriticality.DEGRADED_OK.value,
        ),
        (
            "payment-webhook",
            DependencyType.EXTERNAL_PROVIDER.value,
            DependencyCriticality.OPTIONAL.value,
        ),
    ]
    for name, dependency_type, criticality in dependencies:
        existing = db.scalar(
            select(ServiceDependency).where(
                ServiceDependency.service_name == "renovation-flip-api",
                ServiceDependency.dependency_name == name,
            )
        )
        if existing is None:
            db.add(
                ServiceDependency(
                    service_name="renovation-flip-api",
                    dependency_name=name,
                    dependency_type=dependency_type,
                    criticality=criticality,
                    healthcheck_url=None,
                )
            )

    db.commit()

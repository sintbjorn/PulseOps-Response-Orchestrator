from datetime import UTC, datetime
from typing import Any

from app.domain.enums import ExecutionStatus, Severity, StepStatus
from app.domain.models import Execution, ExecutionFeedback, ExecutionStep
from app.schemas.api import ExecutionTimelineEvent, ExecutionTimelineRead


def build_execution_timeline(execution: Execution) -> ExecutionTimelineRead:
    events: list[tuple[int, ExecutionTimelineEvent]] = []
    base_time = execution.started_at or execution.created_at

    _append(
        events,
        "incident_received",
        "Incident received",
        execution.status,
        base_time,
        {
            "incident_id": execution.incident_id,
            "severity": execution.severity,
            "source": execution.source,
            "target": execution.target,
            "fingerprint": execution.fingerprint,
        },
    )

    _append_policy_event(events, execution, base_time)
    _append_context_event(events, execution, base_time)
    _append_suppression_event(events, execution)

    if execution.started_at:
        _append(
            events,
            "execution_started",
            "Runbook execution started",
            ExecutionStatus.RUNNING.value,
            execution.started_at,
            {
                "mode": execution.mode,
                "runbook_version_id": execution.runbook_version_id,
            },
        )

    for step in execution.steps:
        _append_step_events(events, step)

    _append_analysis_event(events, execution)
    _append_integration_event(events, execution)
    _append_execution_completed_event(events, execution)

    for feedback in execution.feedback:
        _append_feedback_event(events, feedback)

    ordered_events = [
        event
        for _, event in sorted(
            events,
            key=lambda item: (item[1].occurred_at or datetime.max.replace(tzinfo=UTC), item[0]),
        )
    ]

    return ExecutionTimelineRead(
        execution_id=execution.id,
        incident_id=execution.incident_id,
        fingerprint=execution.fingerprint,
        target=execution.target,
        severity=Severity(execution.severity),
        status=ExecutionStatus(execution.status),
        generated_at=datetime.now(UTC),
        events=ordered_events,
    )


def _append_policy_event(
    events: list[tuple[int, ExecutionTimelineEvent]],
    execution: Execution,
    occurred_at: datetime,
) -> None:
    if execution.policy:
        _append(
            events,
            "policy_matched",
            "Response policy matched",
            "MATCHED",
            occurred_at,
            {
                "policy_id": execution.policy_id,
                "policy": execution.policy.name,
                "mode": execution.mode,
                "runbook_id": execution.runbook_id,
                "runbook_version_id": execution.runbook_version_id,
                "runbook": _runbook_name(execution),
            },
        )
        return

    _append(
        events,
        "policy_matched",
        "No response policy matched",
        "NOT_MATCHED",
        occurred_at,
        {
            "policy_id": execution.policy_id,
            "runbook_id": execution.runbook_id,
            "reason": (execution.summary or {}).get("reason"),
        },
    )


def _append_context_event(
    events: list[tuple[int, ExecutionTimelineEvent]],
    execution: Execution,
    occurred_at: datetime,
) -> None:
    context = execution.context or {}
    if not context:
        return

    dependencies = context.get("dependencies", [])
    _append(
        events,
        "context_built",
        "Incident context built",
        "READY",
        occurred_at,
        {
            "fingerprint_occurrences_24h": context.get("fingerprint_occurrences_24h", 0),
            "previous_executions_count": len(
                context.get("previous_executions_for_fingerprint", []),
            ),
            "similar_active_incidents_count": len(context.get("similar_active_incidents", [])),
            "last_notifications_count": len(context.get("last_notifications", [])),
            "dependency_count": len(dependencies),
            "dependencies": [
                {
                    "name": item.get("dependency_name"),
                    "type": item.get("dependency_type"),
                    "criticality": item.get("criticality"),
                }
                for item in dependencies
            ],
            "recent_deploy_marker": context.get("recent_deploy_marker"),
            "context_notes": context.get("context_notes", []),
        },
    )


def _append_suppression_event(
    events: list[tuple[int, ExecutionTimelineEvent]],
    execution: Execution,
) -> None:
    suppression = (execution.summary or {}).get("suppression")
    if not suppression and execution.status not in {
        ExecutionStatus.REUSED.value,
        ExecutionStatus.SUPPRESSED.value,
    }:
        return

    details = suppression or {}
    if execution.reused_execution_id and "reused_execution_id" not in details:
        details = {**details, "reused_execution_id": execution.reused_execution_id}

    title = "Suppression reused recent execution"
    if execution.status == ExecutionStatus.SUPPRESSED.value:
        title = "Suppression skipped runbook execution"

    _append(
        events,
        "suppression_evaluated",
        title,
        execution.status,
        execution.completed_at or execution.created_at,
        details,
    )


def _append_step_events(
    events: list[tuple[int, ExecutionTimelineEvent]],
    step: ExecutionStep,
) -> None:
    if step.started_at:
        _append(
            events,
            "step_started",
            step.name,
            StepStatus.RUNNING.value,
            step.started_at,
            {
                "step_order": step.step_order,
                "step_type": step.step_type,
                "requires_operator": step.requires_operator,
            },
            related_step_id=step.id,
        )

    finished_at = step.completed_at or step.started_at
    event_type = "step_completed"
    if step.status == StepStatus.WAITING_FOR_OPERATOR.value:
        event_type = "step_waiting_for_operator"
    elif step.status == StepStatus.FAILED.value:
        event_type = "step_failed"
    elif step.status == StepStatus.SKIPPED.value:
        event_type = "step_skipped"

    _append(
        events,
        event_type,
        step.name,
        step.status,
        finished_at,
        {
            "step_order": step.step_order,
            "step_type": step.step_type,
            "requires_operator": step.requires_operator,
            "input": step.input,
            "output": step.output,
            "error": step.error,
        },
        duration_ms=_duration_ms(step.started_at, step.completed_at),
        related_step_id=step.id,
    )


def _append_analysis_event(
    events: list[tuple[int, ExecutionTimelineEvent]],
    execution: Execution,
) -> None:
    summary = execution.summary or {}
    if not summary.get("suspected_cause") and not summary.get("evidence"):
        return

    _append(
        events,
        "analysis_completed",
        "Evidence analysis completed",
        execution.status,
        execution.completed_at or execution.created_at,
        {
            "suspected_cause": summary.get("suspected_cause"),
            "confidence": summary.get("confidence"),
            "evidence": summary.get("evidence", []),
            "next_action": summary.get("next_action"),
            "suggested_remediation": summary.get("suggested_remediation", []),
        },
    )


def _append_integration_event(
    events: list[tuple[int, ExecutionTimelineEvent]],
    execution: Execution,
) -> None:
    integrations = (execution.summary or {}).get("integrations")
    if not integrations:
        return

    _append(
        events,
        "integrations_notified",
        "Enriched summary handed off",
        "COMPLETED",
        execution.completed_at or execution.created_at,
        integrations,
    )


def _append_execution_completed_event(
    events: list[tuple[int, ExecutionTimelineEvent]],
    execution: Execution,
) -> None:
    if not execution.completed_at:
        return

    _append(
        events,
        "execution_completed",
        "Execution completed",
        execution.status,
        execution.completed_at,
        {
            "suspected_cause": execution.suspected_cause,
            "confidence": execution.confidence,
            "evidence_count": len(execution.evidence or []),
        },
        duration_ms=_duration_ms(execution.started_at, execution.completed_at),
    )


def _append_feedback_event(
    events: list[tuple[int, ExecutionTimelineEvent]],
    feedback: ExecutionFeedback,
) -> None:
    _append(
        events,
        "feedback_received",
        "Operator feedback received",
        feedback.rating,
        feedback.created_at,
        {
            "feedback_id": feedback.id,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "created_by": feedback.created_by,
        },
        actor=feedback.created_by,
    )


def _append(
    events: list[tuple[int, ExecutionTimelineEvent]],
    event_type: str,
    title: str,
    status: str | None,
    occurred_at: datetime | None,
    details: dict[str, Any],
    *,
    actor: str = "pulseops",
    duration_ms: float | None = None,
    related_step_id: int | None = None,
) -> None:
    events.append(
        (
            len(events),
            ExecutionTimelineEvent(
                event_type=event_type,
                title=title,
                status=status,
                actor=actor,
                occurred_at=occurred_at,
                duration_ms=duration_ms,
                related_step_id=related_step_id,
                details=details,
            ),
        )
    )


def _duration_ms(started_at: datetime | None, completed_at: datetime | None) -> float | None:
    if not started_at or not completed_at:
        return None
    return round((completed_at - started_at).total_seconds() * 1000, 2)


def _runbook_name(execution: Execution) -> str | None:
    if not execution.runbook_version or not execution.runbook_version.runbook:
        return None
    return execution.runbook_version.runbook.name

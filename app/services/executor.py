from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import execution_counter, execution_duration_seconds, step_counter
from app.domain.enums import ExecutionStatus, RunbookStepType, StepStatus
from app.domain.models import Execution, ExecutionFeedback, ExecutionStep
from app.schemas.api import ExecutionFeedbackCreate, IncidentInput, ManualStepCompleteRequest
from app.services.analysis import build_execution_summary
from app.services.context_builder import build_incident_context
from app.services.integrations import send_enriched_notification, send_summary_to_pulsewatch
from app.services.policy_engine import get_current_runbook_version, match_policy
from app.services.suppression import evaluate_suppression


def execute_incident(db: Session, incident: IncidentInput) -> Execution:
    policy = match_policy(db, incident)
    if policy is None:
        return _record_skipped_execution(db, incident, "no matching enabled policy")

    runbook_version = get_current_runbook_version(db, policy)
    if runbook_version is None:
        return _record_skipped_execution(
            db,
            incident,
            f"policy {policy.name} has no current runbook version",
            policy_id=policy.id,
            runbook_id=policy.runbook_id,
        )

    context = build_incident_context(db, incident)
    suppression = evaluate_suppression(db, incident, policy)
    if suppression.action == "reuse" and suppression.reused_execution:
        return _record_reused_execution(
            db=db,
            incident=incident,
            policy_id=policy.id,
            runbook_id=policy.runbook_id,
            runbook_version_id=runbook_version.id,
            context=context,
            reason=suppression.reason,
            reused_execution=suppression.reused_execution,
        )
    if suppression.action == "suppress":
        return _record_suppressed_execution(
            db=db,
            incident=incident,
            policy_id=policy.id,
            runbook_id=policy.runbook_id,
            runbook_version_id=runbook_version.id,
            mode=policy.mode,
            context=context,
            reason=suppression.reason,
        )

    execution = Execution(
        incident_id=incident.incident_id,
        fingerprint=incident.fingerprint,
        target=incident.target,
        severity=incident.severity.value,
        source=incident.source,
        policy_id=policy.id,
        runbook_id=policy.runbook_id,
        runbook_version_id=runbook_version.id,
        status=ExecutionStatus.RUNNING.value,
        mode=policy.mode,
        idempotency_key=incident.idempotency_key,
        context=context,
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    started = perf_counter()
    steps: list[ExecutionStep] = []
    for index, step_definition in enumerate(runbook_version.definition.get("steps", []), start=1):
        step = _run_step(db, execution, incident, context, step_definition, index)
        steps.append(step)
        if step.status == StepStatus.WAITING_FOR_OPERATOR.value:
            summary = build_execution_summary(context, steps)
            summary["waiting_for_operator"] = {
                "step_id": step.id,
                "step": step.name,
                "instructions": step.output.get("instructions"),
            }
            _finish_execution(
                db=db,
                execution=execution,
                status=ExecutionStatus.WAITING_FOR_OPERATOR.value,
                summary=summary,
                keep_open=True,
            )
            return execution

    summary = build_execution_summary(context, steps)
    summary["integrations"] = {
        "pulsewatch": send_summary_to_pulsewatch(incident, summary),
        "notification_service": send_enriched_notification(incident, summary),
    }

    _finish_execution(
        db=db,
        execution=execution,
        status=ExecutionStatus.FAILED.value
        if any(step.status == StepStatus.FAILED.value for step in steps)
        else ExecutionStatus.SUCCEEDED.value,
        summary=summary,
    )
    execution_duration_seconds.observe(perf_counter() - started)
    return execution


def complete_manual_step(
    db: Session,
    step_id: int,
    request: ManualStepCompleteRequest,
) -> ExecutionStep | None:
    step = db.get(ExecutionStep, step_id)
    if step is None:
        return None

    output = dict(step.output or {})
    output.update(request.output)
    if request.comment:
        output["operator_comment"] = request.comment

    step.output = output
    step.status = StepStatus.SUCCEEDED.value
    step.completed_at = datetime.now(UTC)

    execution = step.execution
    waiting_steps = [
        item
        for item in execution.steps
        if item.status == StepStatus.WAITING_FOR_OPERATOR.value and item.id != step.id
    ]
    if not waiting_steps and execution.status == ExecutionStatus.WAITING_FOR_OPERATOR.value:
        summary = build_execution_summary(execution.context, execution.steps)
        _finish_execution(
            db=db,
            execution=execution,
            status=ExecutionStatus.SUCCEEDED.value,
            summary=summary,
        )
    else:
        db.commit()
        db.refresh(step)

    return step


def create_execution_feedback(
    db: Session,
    execution_id: str,
    request: ExecutionFeedbackCreate,
) -> ExecutionFeedback | None:
    execution = db.get(Execution, execution_id)
    if execution is None:
        return None

    feedback = ExecutionFeedback(
        execution_id=execution_id,
        rating=request.rating.value,
        comment=request.comment,
        created_by=request.created_by,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def _run_step(
    db: Session,
    execution: Execution,
    incident: IncidentInput,
    context: dict[str, Any],
    step_definition: dict[str, Any],
    step_order: int,
) -> ExecutionStep:
    step_type = step_definition.get("type", RunbookStepType.STATIC_HINT.value)
    step = ExecutionStep(
        execution_id=execution.id,
        step_order=step_order,
        name=step_definition.get("name", f"Step {step_order}"),
        step_type=step_type,
        status=StepStatus.RUNNING.value,
        input=step_definition,
        requires_operator=step_type == RunbookStepType.MANUAL_CHECK.value,
        started_at=datetime.now(UTC),
    )
    db.add(step)
    db.commit()
    db.refresh(step)

    try:
        status, output, error = _execute_step_by_type(db, incident, context, step_definition)
    except Exception as exc:  # noqa: BLE001 - audit trail should capture unexpected step failures.
        status, output, error = StepStatus.FAILED.value, {}, str(exc)

    step.status = status
    step.output = output
    step.error = error
    if status != StepStatus.WAITING_FOR_OPERATOR.value:
        step.completed_at = datetime.now(UTC)

    db.commit()
    db.refresh(step)
    step_counter.labels(step_type=step.step_type, status=step.status).inc()
    return step


def _execute_step_by_type(
    db: Session,
    incident: IncidentInput,
    context: dict[str, Any],
    step_definition: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    step_type = step_definition.get("type")
    config = step_definition.get("config", {})

    if step_type == RunbookStepType.HTTP_CHECK.value:
        return _execute_http_check(incident, config)
    if step_type == RunbookStepType.DEPENDENCY_HEALTH.value:
        return _execute_dependency_health(db, incident, config)
    if step_type == RunbookStepType.METRIC_QUERY.value:
        return _execute_metric_query(incident, config)
    if step_type == RunbookStepType.PULSEWATCH_LOOKUP.value:
        return (
            StepStatus.SUCCEEDED.value,
            {
                "similar_active_incidents": context.get("similar_active_incidents", []),
                "previous_executions_for_fingerprint": context.get(
                    "previous_executions_for_fingerprint",
                    [],
                ),
            },
            None,
        )
    if step_type == RunbookStepType.MANUAL_CHECK.value:
        return (
            StepStatus.WAITING_FOR_OPERATOR.value,
            {
                "instructions": config.get("instructions", "Operator confirmation required."),
                "expected_output": config.get("expected_output", {}),
            },
            None,
        )
    if step_type == RunbookStepType.REMEDIATION_PREVIEW.value:
        return (
            StepStatus.SUCCEEDED.value,
            {
                "suggested_remediation": config.get("suggested_remediation", []),
                "risk_level": config.get("risk_level", "MEDIUM"),
                "requires_approval": config.get("requires_approval", True),
            },
            None,
        )

    return (
        StepStatus.SUCCEEDED.value,
        {
            "message": config.get("message", "Static diagnostic hint."),
            "evidence": config.get("evidence", []),
        },
        None,
    )


def _execute_http_check(
    incident: IncidentInput,
    config: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    settings = get_settings()
    url = _resolve_config_value(config.get("url"), incident)
    if not url:
        return (
            StepStatus.SKIPPED.value,
            {"status": "skipped", "reason": "healthcheck_url_not_configured"},
            None,
        )

    expected_statuses = set(config.get("expected_statuses", [200]))
    started = perf_counter()
    try:
        timeout_seconds = config.get("timeout_seconds", settings.http_timeout_seconds)
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url)
        latency_ms = round((perf_counter() - started) * 1000, 2)
        healthy = response.status_code in expected_statuses
        return (
            StepStatus.SUCCEEDED.value,
            {
                "url": url,
                "status_code": response.status_code,
                "expected_statuses": sorted(expected_statuses),
                "healthy": healthy,
                "latency_ms": latency_ms,
            },
            None,
        )
    except httpx.HTTPError as exc:
        return (
            StepStatus.SUCCEEDED.value,
            {
                "url": url,
                "healthy": False,
                "transport_error": str(exc),
            },
            None,
        )


def _execute_dependency_health(
    db: Session,
    incident: IncidentInput,
    config: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    from app.domain.models import ServiceDependency

    settings = get_settings()
    dependencies = db.scalars(
        select(ServiceDependency)
        .where(ServiceDependency.service_name == incident.target)
        .order_by(ServiceDependency.dependency_name.asc())
    ).all()

    results = []
    expected_statuses = set(config.get("expected_statuses", [200]))
    for dependency in dependencies:
        item: dict[str, Any] = {
            "dependency_name": dependency.dependency_name,
            "dependency_type": dependency.dependency_type,
            "criticality": dependency.criticality,
            "healthcheck_url": dependency.healthcheck_url,
        }
        if not dependency.healthcheck_url:
            item.update({"status": "skipped", "healthy": None, "reason": "no healthcheck_url"})
            results.append(item)
            continue

        try:
            started = perf_counter()
            timeout_seconds = config.get("timeout_seconds", settings.http_timeout_seconds)
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(dependency.healthcheck_url)
            item.update(
                {
                    "status": "checked",
                    "status_code": response.status_code,
                    "healthy": response.status_code in expected_statuses,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
        except httpx.HTTPError as exc:
            item.update({"status": "checked", "healthy": False, "transport_error": str(exc)})
        results.append(item)

    return StepStatus.SUCCEEDED.value, {"dependencies": results}, None


def _execute_metric_query(
    incident: IncidentInput,
    config: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    metric_path = config.get("metric_path")
    threshold = config.get("threshold")
    value = (
        _metadata_value(incident.metadata, metric_path)
        if metric_path
        else config.get("sample_value")
    )
    if value is None or threshold is None:
        return (
            StepStatus.SKIPPED.value,
            {
                "status": "skipped",
                "reason": "metric_value_or_threshold_not_configured",
                "metric_path": metric_path,
            },
            None,
        )

    operator = config.get("operator", "gt")
    threshold_exceeded = value > threshold if operator == "gt" else value < threshold
    return (
        StepStatus.SUCCEEDED.value,
        {
            "metric_path": metric_path,
            "value": value,
            "threshold": threshold,
            "operator": operator,
            "threshold_exceeded": threshold_exceeded,
        },
        None,
    )


def _record_skipped_execution(
    db: Session,
    incident: IncidentInput,
    reason: str,
    policy_id: int | None = None,
    runbook_id: int | None = None,
) -> Execution:
    execution = Execution(
        incident_id=incident.incident_id,
        fingerprint=incident.fingerprint,
        target=incident.target,
        severity=incident.severity.value,
        source=incident.source,
        policy_id=policy_id,
        runbook_id=runbook_id,
        status=ExecutionStatus.SKIPPED.value,
        summary={"reason": reason},
        evidence=[reason],
        completed_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    _record_execution_metric(execution)
    return execution


def _record_reused_execution(
    db: Session,
    incident: IncidentInput,
    policy_id: int,
    runbook_id: int,
    runbook_version_id: int,
    context: dict[str, Any],
    reason: str,
    reused_execution: Execution,
) -> Execution:
    summary = dict(reused_execution.summary or {})
    summary["suppression"] = {
        "action": "reuse",
        "reason": reason,
        "reused_execution_id": reused_execution.id,
    }
    execution = Execution(
        incident_id=incident.incident_id,
        fingerprint=incident.fingerprint,
        target=incident.target,
        severity=incident.severity.value,
        source=incident.source,
        policy_id=policy_id,
        runbook_id=runbook_id,
        runbook_version_id=runbook_version_id,
        status=ExecutionStatus.REUSED.value,
        mode=reused_execution.mode,
        context=context,
        summary=summary,
        suspected_cause=reused_execution.suspected_cause,
        confidence=reused_execution.confidence,
        evidence=[*list(reused_execution.evidence or []), reason],
        reused_execution_id=reused_execution.id,
        completed_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    _record_execution_metric(execution)
    return execution


def _record_suppressed_execution(
    db: Session,
    incident: IncidentInput,
    policy_id: int,
    runbook_id: int,
    runbook_version_id: int,
    mode: str,
    context: dict[str, Any],
    reason: str,
) -> Execution:
    execution = Execution(
        incident_id=incident.incident_id,
        fingerprint=incident.fingerprint,
        target=incident.target,
        severity=incident.severity.value,
        source=incident.source,
        policy_id=policy_id,
        runbook_id=runbook_id,
        runbook_version_id=runbook_version_id,
        status=ExecutionStatus.SUPPRESSED.value,
        mode=mode,
        context=context,
        summary={"suppression": {"action": "suppress", "reason": reason}},
        evidence=[reason],
        completed_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    _record_execution_metric(execution)
    return execution


def _finish_execution(
    db: Session,
    execution: Execution,
    status: str,
    summary: dict[str, Any],
    keep_open: bool = False,
) -> None:
    execution.status = status
    execution.summary = summary
    execution.suspected_cause = summary.get("suspected_cause")
    execution.confidence = summary.get("confidence", 0.0)
    execution.evidence = summary.get("evidence", [])
    if not keep_open:
        execution.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(execution)
    _record_execution_metric(execution)


def _record_execution_metric(execution: Execution) -> None:
    execution_counter.labels(
        status=execution.status,
        severity=execution.severity,
        target=execution.target,
    ).inc()


def _resolve_config_value(value: Any, incident: IncidentInput) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith("{{metadata.") and value.endswith("}}"):
        key = value.removeprefix("{{metadata.").removesuffix("}}")
        return incident.metadata.get(key)
    return value.replace("{target}", incident.target).replace("{fingerprint}", incident.fingerprint)


def _metadata_value(metadata: dict[str, Any], path: str | None) -> Any:
    if not path:
        return None
    current: Any = metadata
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current

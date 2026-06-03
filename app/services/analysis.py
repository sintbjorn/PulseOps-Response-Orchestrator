from typing import Any

from app.domain.enums import RunbookStepType
from app.domain.models import ExecutionStep


def build_execution_summary(context: dict[str, Any], steps: list[ExecutionStep]) -> dict[str, Any]:
    evidence = _collect_evidence(context, steps)
    suspected_cause, confidence = _score_suspected_cause(context, steps, evidence)
    next_action = _select_next_action(context, steps, suspected_cause)

    incident = context.get("incident_details", {})
    headline = (
        f"{incident.get('severity', 'UNKNOWN')}: "
        f"{incident.get('title') or incident.get('fingerprint')}"
    )

    return {
        "headline": headline,
        "suspected_cause": suspected_cause,
        "confidence": confidence,
        "evidence": evidence,
        "next_action": next_action,
        "context_notes": context.get("context_notes", []),
        "suggested_remediation": _extract_remediation(steps),
    }


def _collect_evidence(context: dict[str, Any], steps: list[ExecutionStep]) -> list[str]:
    evidence: list[str] = []

    occurrence_count = context.get("fingerprint_occurrences_24h", 0)
    if occurrence_count:
        evidence.append(f"fingerprint occurred {occurrence_count} times in the last 24h")

    deploy_marker = context.get("recent_deploy_marker")
    if deploy_marker:
        version = deploy_marker.get("version") or "unknown"
        evidence.append(f"recent deploy marker detected: {version}")

    for step in steps:
        output = step.output or {}
        if step.step_type == RunbookStepType.HTTP_CHECK.value:
            if output.get("healthy") is True:
                evidence.append(f"{step.name} passed")
            elif output.get("healthy") is False:
                evidence.append(f"{step.name} failed")
        elif step.step_type == RunbookStepType.DEPENDENCY_HEALTH.value:
            for item in output.get("dependencies", []):
                state = "passed" if item.get("healthy") else "failed"
                if item.get("status") == "skipped":
                    state = "was not configured"
                evidence.append(f"{item.get('dependency_name')} readiness {state}")
        elif step.step_type == RunbookStepType.METRIC_QUERY.value:
            if output.get("threshold_exceeded") is True:
                evidence.append(f"{step.name} above threshold")
            elif output.get("threshold_exceeded") is False:
                evidence.append(f"{step.name} within threshold")
        elif step.step_type == RunbookStepType.PULSEWATCH_LOOKUP.value:
            related = output.get("similar_active_incidents", [])
            if related:
                evidence.append(f"found {len(related)} related active incidents")
        elif step.step_type == RunbookStepType.STATIC_HINT.value:
            for item in output.get("evidence", []):
                evidence.append(str(item))

    return _dedupe(evidence)


def _score_suspected_cause(
    context: dict[str, Any],
    steps: list[ExecutionStep],
    evidence: list[str],
) -> tuple[str, float]:
    deploy_marker = bool(context.get("recent_deploy_marker"))
    repeated_fingerprint = context.get("fingerprint_occurrences_24h", 0) >= 3
    api_failed = any(
        step.step_type == RunbookStepType.HTTP_CHECK.value
        and (step.output or {}).get("healthy") is False
        for step in steps
    )
    dependency_failed = any(
        item.get("healthy") is False
        and item.get("criticality") == "REQUIRED"
        for step in steps
        if step.step_type == RunbookStepType.DEPENDENCY_HEALTH.value
        for item in (step.output or {}).get("dependencies", [])
    )
    metric_high = any(
        step.step_type == RunbookStepType.METRIC_QUERY.value
        and (step.output or {}).get("threshold_exceeded") is True
        for step in steps
    )

    if deploy_marker and api_failed and not dependency_failed:
        return "recent_deploy_regression", 0.76
    if dependency_failed:
        return "dependency_outage_or_degradation", 0.72
    if repeated_fingerprint and metric_high:
        return "recurring_capacity_or_latency_regression", 0.68
    if metric_high:
        return "traffic_or_error_rate_regression", 0.60
    if repeated_fingerprint:
        return "recurring_known_failure", 0.55
    if evidence:
        return "insufficient_evidence_needs_operator_review", 0.42
    return "unknown", 0.30


def _select_next_action(
    context: dict[str, Any],
    steps: list[ExecutionStep],
    suspected_cause: str,
) -> str:
    remediation = _extract_remediation(steps)
    if remediation:
        first = remediation[0]
        action = first.get("action") if isinstance(first, dict) else str(first)
        if action:
            return action

    if suspected_cause == "recent_deploy_regression":
        version = (context.get("recent_deploy_marker") or {}).get("version", "latest deploy")
        return f"Check deploy {version} and prepare rollback candidate."
    if suspected_cause == "dependency_outage_or_degradation":
        return "Confirm required dependency health before restarting the application."
    if suspected_cause == "recurring_capacity_or_latency_regression":
        return "Review recurrence pattern and compare capacity metrics for the same target."
    return "Escalate to an operator with the collected evidence and context notes."


def _extract_remediation(steps: list[ExecutionStep]) -> list[dict[str, Any]]:
    for step in steps:
        if step.step_type == RunbookStepType.REMEDIATION_PREVIEW.value:
            return (step.output or {}).get("suggested_remediation", [])
    return []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

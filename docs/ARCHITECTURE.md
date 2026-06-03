# Architecture

PulseOps Response Orchestrator sits between incident detection and notification delivery.
Its job is to turn a raw critical incident into an auditable diagnostic execution and an
enriched response summary.

## Runtime Flow

```text
1. PulseWatch sends a CRITICAL incident webhook.
2. PulseOps validates the payload and computes an idempotency key.
3. The policy engine selects the best matching ResponsePolicy.
4. Suppression checks decide whether to execute or reuse a recent execution.
5. The context builder gathers incident history and target/dependency context.
6. The executor runs the selected RunbookVersion step by step.
7. The analyzer produces suspected cause, confidence, evidence, and next action.
8. PulseOps returns the summary to PulseWatch.
9. PulseWatch records the summary and asks Notification Service to send the alert.
```

## Main Components

### API Layer

FastAPI routes live under `app/api/` and expose:

- health and metrics endpoints
- PulseWatch webhook ingestion
- policy simulation
- execution lookup and feedback
- runbook lookup

### Domain Layer

SQLAlchemy models in `app/domain/models.py` represent policies, runbooks, versions,
executions, steps, feedback, and service dependencies.

### Service Layer

The service layer owns orchestration behavior:

- `policy_engine.py` selects matching policies.
- `suppression.py` handles cooldowns and reuse.
- `context_builder.py` builds incident context.
- `executor.py` runs versioned runbooks.
- `analysis.py` computes confidence and evidence.
- `integrations.py` handles outbound callbacks.
- `bootstrap.py` seeds demo policies, runbooks, and dependencies.

## Runbook Versioning

Runbooks are split into two records:

```text
Runbook
  id
  name
  current_version

RunbookVersion
  id
  runbook_id
  version
  definition
  created_by
  created_at
  changelog
```

An execution references a concrete `runbook_version_id`. This prevents old execution
history from becoming ambiguous after a runbook is edited.

## Suppression Model

Policies can define:

- `cooldown_seconds`
- `max_executions_per_incident`
- `max_executions_per_fingerprint_per_hour`
- `reuse_recent_execution`

This lets PulseOps cooperate with PulseWatch deduplication instead of adding more alert
noise during repeated incidents.

## Evidence Model

PulseOps does not need machine learning to produce useful incident summaries. The analyzer
uses deterministic rules over runbook outputs and incident context to produce:

- `suspected_cause`
- `confidence`
- `evidence`
- `suggested_remediation`
- `risk_level`
- `requires_approval`

The result is explainable and suitable for an operator-facing alert.

## Integration Boundaries

PulseOps is designed to degrade gracefully:

- PulseWatch callback failures do not erase execution history.
- Notification callback failures do not make the runbook execution disappear.
- HTTP calls use timeouts.
- Missing healthcheck URLs become evidence instead of hard crashes.

The three-service demo documents the happy path and the idempotency path.

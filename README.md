# PulseOps Response Orchestrator

PulseOps Response Orchestrator automates the first phase of incident response. It receives
critical incidents from PulseWatch, matches a response policy, builds operational context,
runs a versioned diagnostic runbook, applies suppression rules, produces evidence-based
suspected causes, and returns an enriched response summary that PulseWatch and Notification
Service can use immediately.

The service is intentionally designed like a production incident-response component rather
than a simple health-check script. It preserves execution history, keeps runbook versions
auditable, understands repeated fingerprints, correlates related incidents, and explains its
conclusions with confidence and evidence.

## What This Demonstrates

- Incident response orchestration across multiple services
- Policy-driven runbook selection
- Versioned runbooks for auditability and reliability
- Incident context building before diagnostics run
- Suppression and idempotency for noisy repeated alerts
- Evidence-based suspected cause analysis without ML
- Human feedback loop for improving future runbooks
- Integration with PulseWatch and Notification Service
- Health checks, metrics, structured configuration, and Dockerized demos

## System Role

```text
PulseWatch detects and deduplicates incidents.
PulseOps enriches and diagnoses critical incidents.
Notification Service delivers the enriched alert.
```

In the three-service demo the flow is:

```text
PulseWatch CRITICAL signal
  -> PulseOps policy match
  -> Incident context builder
  -> Versioned diagnostic runbook execution
  -> Evidence + confidence + suspected cause
  -> PulseWatch audit comment
  -> Notification Service enriched email alert
  -> Mailpit inbox
```

## Core Capabilities

- **PulseWatch webhook**
  `POST /api/v1/webhooks/pulsewatch/incidents` starts the orchestration flow for an
  incoming incident.

- **Policy simulation**
  `POST /api/v1/policies/simulate` shows which policy and runbook would match a proposed
  incident before anything is executed.

- **Runbook versioning**
  Executions point to immutable `RunbookVersion` records, so historical executions remain
  honest even after a runbook changes.

- **Incident context builder**
  The service collects incident details, recent fingerprint recurrence, previous
  executions, similar active incidents, dependency health, recent deploy hints, and prior
  notifications.

- **Declarative diagnostic steps**
  Supported step types include `HTTP_CHECK`, `METRIC_QUERY`, `PULSEWATCH_LOOKUP`,
  `STATIC_HINT`, `DEPENDENCY_HEALTH`, `MANUAL_CHECK`, and `REMEDIATION_PREVIEW`.

- **Noise control**
  Policies can define cooldowns, per-incident execution limits, per-fingerprint hourly
  limits, and recent execution reuse.

- **Evidence and confidence**
  PulseOps produces a suspected cause, confidence score, evidence list, and suggested next
  action from deterministic rules.

- **Human feedback**
  Operators can rate executions as `HELPFUL`, `NOT_HELPFUL`, `WRONG_RUNBOOK`, or
  `NEEDS_MORE_CONTEXT`.

- **Production observability**
  The service exposes health endpoints and Prometheus metrics for local and containerized
  environments.

## Data Model Highlights

```text
ResponsePolicy
  -> Runbook
     -> RunbookVersion
        -> Execution
           -> ExecutionStep
           -> ExecutionFeedback

ServiceDependency
  -> target dependency map used during incident context building
```

The important auditability detail is that `Execution` references `runbook_version_id`, not
only `runbook_id`.

## Quick Start

Create a local environment:

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.entrypoints.api:app --reload
```

Open:

```text
http://localhost:8000/docs
http://localhost:8000/health/live
http://localhost:8000/metrics
```

Run quality gates:

```bash
ruff check .
pytest
mypy app
```

## Docker

For PulseOps only:

```bash
cp .env.example .env
docker compose up --build
```

Open:

```text
http://localhost:8000/docs
```

## Three-Service Demo

The full demo connects this service with:

- [PulseWatch Incident Service](https://github.com/sintbjorn/PulseWatch_Incident_Service)
- [Notification Service](https://github.com/sintbjorn/notification_service)

Expected local layout:

```text
integrations/PulseWatch_Incident_Service
integrations/notification_service
```

Start the complete stack:

```bash
docker compose -f docker-compose.integration.yml up -d --build
```

Run the smoke scenario:

```bash
bash scripts/integration_smoke.sh
```

Demo URLs:

```text
PulseOps:              http://127.0.0.1:8010/docs
PulseWatch:            http://127.0.0.1:8011/docs
Notification Service:  http://127.0.0.1:8020/api/docs/
Mailpit:               http://127.0.0.1:8025
```

See [Integration Demo](docs/INTEGRATION_DEMO.md) for expected output and reset commands.

## Example Policy Simulation

```bash
curl -X POST http://localhost:8000/api/v1/policies/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "CRITICAL",
    "source": "monitoring",
    "target": "renovation-flip-api",
    "fingerprint": "renovation-flip-api:latency:p95"
  }'
```

Example response:

```json
{
  "matched_policy": "Critical API latency policy",
  "runbook": "High API Latency Diagnostics",
  "mode": "DIAGNOSTIC_ONLY",
  "would_execute_steps": [
    "Check API readiness",
    "Check database readiness",
    "Check 5xx rate",
    "Find related incidents"
  ]
}
```

## Example Diagnostic Execution

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/pulsewatch/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "42",
    "title": "High API latency",
    "description": "P95 latency is above 1500ms",
    "status": "NEW",
    "severity": "CRITICAL",
    "source": "monitoring",
    "target": "renovation-flip-api",
    "fingerprint": "renovation-flip-api:latency:p95",
    "metadata": {
      "deploy_version": "1.8.4",
      "healthcheck_url": "http://localhost:8000/health/live"
    }
  }'
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [PulseWatch Integration](docs/PULSEWATCH_INTEGRATION.md)
- [Integration Demo](docs/INTEGRATION_DEMO.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

This project is licensed under the [MIT License](LICENSE).

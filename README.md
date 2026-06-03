# PulseOps Response Orchestrator

PulseOps automates the first phase of incident response. It receives incidents from
PulseWatch, matches a response policy, builds incident context, runs a versioned diagnostic
runbook, applies suppression/noise control, produces evidence-based suspected causes, and
returns an enriched summary for PulseWatch or Notification Service.

## MVP Capabilities

- PulseWatch webhook: `POST /api/v1/webhooks/pulsewatch/incidents`
- Policy simulation: `POST /api/v1/policies/simulate`
- Response policies with cooldowns, fingerprint limits, and reuse behavior
- Declarative runbooks with immutable `RunbookVersion` records
- Execution audit timeline with per-step inputs, outputs, and errors
- Incident context builder with prior executions, fingerprint recurrence, and dependency map
- Step types: `HTTP_CHECK`, `METRIC_QUERY`, `PULSEWATCH_LOOKUP`, `STATIC_HINT`,
  `DEPENDENCY_HEALTH`, `MANUAL_CHECK`, `REMEDIATION_PREVIEW`
- Human feedback loop for executions
- Optional enriched alert handoff to Notification Service
- Health and Prometheus metrics endpoints

## Architecture

```text
PulseWatch
  -> PulseOps Response Orchestrator
     -> ResponsePolicy match
     -> IncidentContextBuilder
     -> RunbookVersion execution
     -> Evidence + confidence + summary
  -> PulseWatch audit comment
  -> Notification Service enriched alert
```

## Quick Start

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

Docker:

```bash
cp .env.example .env
docker compose up --build
```

## Three-Service Demo

Run the full PulseWatch -> PulseOps -> Notification Service flow with:

```bash
docker compose -f docker-compose.integration.yml up -d --build
bash scripts/integration_smoke.sh
```

See [Integration Demo](docs/INTEGRATION_DEMO.md) for ports, expected output, and reset
commands.

## Simulate A Policy

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

## Run A Diagnostic Execution

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

## Quality Gates

```bash
pytest
ruff check .
mypy app
```

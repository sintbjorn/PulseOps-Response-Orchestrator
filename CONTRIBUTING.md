# Contributing

Thanks for improving PulseOps Response Orchestrator.

This repository is structured as a small production-style service: keep changes scoped,
auditable, and covered by the quality gates that match the risk of the change.

## Local Setup

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the API:

```bash
uvicorn app.entrypoints.api:app --reload
```

## Quality Gates

Run these before opening a pull request:

```bash
ruff check .
pytest
mypy app
```

For the full integration demo:

```bash
docker compose -f docker-compose.integration.yml up -d --build
bash scripts/integration_smoke.sh
```

## Development Guidelines

- Keep runbook execution behavior deterministic and auditable.
- Preserve historical execution integrity; never rewrite old execution results in place.
- Prefer adding a new `RunbookVersion` over mutating existing execution history.
- Include tests for policy matching, suppression, callbacks, and runbook step behavior.
- Keep external integrations timeout-bound and failure-tolerant.
- Do not commit secrets, local databases, Docker volumes, or generated caches.

## Commit Style

Use short, direct commit messages:

```text
Add policy simulation endpoint
Fix PulseWatch notification payload
Document integration demo
```

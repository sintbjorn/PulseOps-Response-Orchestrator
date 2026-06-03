# Roadmap

PulseOps Response Orchestrator already covers the core MVP. These are natural next steps
for turning the demo into a deeper incident-response platform.

## Near Term

- Add a dedicated execution timeline endpoint optimized for UI rendering.
- Add runbook create/update endpoints that always create a new `RunbookVersion`.
- Add a richer policy simulator response with suppression decisions and dependency checks.
- Add operator completion for `MANUAL_CHECK` steps.
- Add more tests for callback failure handling and execution reuse.

## Product Depth

- Add an admin UI for policies, runbooks, execution history, and feedback.
- Add dependency graph visualization for service-to-service impact analysis.
- Add deploy marker ingestion from CI/CD systems.
- Add saved simulation examples for demos and runbook reviews.
- Add richer feedback analytics to identify weak or noisy runbooks.

## Production Hardening

- Add webhook authentication and request signing.
- Add structured JSON logs with correlation IDs.
- Add OpenTelemetry traces across PulseWatch, PulseOps, and Notification Service.
- Add database migrations for seeded demo data instead of runtime bootstrapping.
- Add background execution mode for longer runbooks.
- Add multi-tenant policy scoping if incidents span multiple teams.

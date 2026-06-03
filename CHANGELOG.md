# Changelog

All notable changes to PulseOps Response Orchestrator are documented here.

This project follows a lightweight changelog style inspired by Keep a Changelog.

## [0.1.0] - 2026-06-03

### Added

- PulseWatch incident webhook for diagnostic orchestration.
- Response policy matching and policy simulation endpoint.
- Declarative, versioned runbooks with immutable `RunbookVersion` records.
- Execution audit timeline with per-step inputs, outputs, status, and errors.
- Incident context builder with prior executions, fingerprint recurrence, and dependencies.
- Suppression and recent execution reuse for repeated fingerprints.
- Evidence-based suspected cause, confidence score, and remediation preview.
- Human execution feedback model.
- Optional PulseWatch and Notification Service callback adapters.
- Three-service Docker integration demo.
- Smoke script for PulseWatch -> PulseOps -> Notification Service verification.

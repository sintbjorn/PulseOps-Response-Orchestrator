# Security

PulseOps Response Orchestrator is a portfolio/demo-grade service that models production
incident-response patterns. Treat webhook payloads, incident metadata, API keys, and
notification content as sensitive operational data.

## Supported Versions

The `main` branch is the only supported development line.

## Reporting A Vulnerability

If you find a vulnerability, please avoid posting exploit details in a public issue.
Use a private GitHub security advisory when available, or open a minimal public issue that
asks for a secure contact path without including sensitive details.

## Security Expectations

- Do not commit real API keys, tokens, webhook secrets, database dumps, or customer data.
- Keep `.env` local and use `.env.example` for documented configuration.
- Use timeout-bound HTTP clients for integrations.
- Keep callbacks idempotent where possible.
- Validate external payloads with Pydantic schemas before using them.
- Prefer least-privilege credentials for PulseWatch and Notification Service integrations.

## Demo Defaults

The local Docker compose files use development credentials and demo mail delivery. They are
intended for local demos only and must be changed before any real deployment.

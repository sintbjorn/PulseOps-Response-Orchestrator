# Integration Demo

This demo runs the full incident-response chain locally:

```text
PulseWatch CRITICAL signal
  -> PulseOps Response Orchestrator runbook execution
  -> PulseWatch COMMENT_ADDED audit summary
  -> Notification Service enriched email alert
  -> Mailpit inbox
```

## Start The Stack

The compose file expects the two sibling repositories to be present in `integrations/`:

```text
integrations/PulseWatch_Incident_Service
integrations/notification_service
```

Start everything:

```bash
docker compose -f docker-compose.integration.yml up -d --build
```

Useful URLs:

```text
PulseOps:              http://127.0.0.1:8010/docs
PulseWatch:            http://127.0.0.1:8011/docs
Notification Service:  http://127.0.0.1:8020/api/docs/
Mailpit:               http://127.0.0.1:8025
```

## Run Smoke Demo

```bash
bash scripts/integration_smoke.sh
```

The script creates a `CRITICAL` PulseWatch signal, repeats the same fingerprint, then prints:

- PulseWatch audit events, including `[PulseOps] Response summary`
- PulseOps execution timeline
- PulseWatch notification attempts
- Mailpit messages from Notification Service

## Stop The Stack

```bash
docker compose -f docker-compose.integration.yml down
```

To reset local demo data:

```bash
docker compose -f docker-compose.integration.yml down -v
```

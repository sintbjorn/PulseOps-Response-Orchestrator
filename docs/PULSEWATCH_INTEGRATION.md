# PulseWatch Integration

This service is designed to sit between PulseWatch and Notification Service during the
first phase of incident response.

## Flow

```text
PulseWatch CRITICAL incident
  -> POST /api/v1/webhooks/pulsewatch/incidents
  -> PulseOps policy match + context + runbook execution
  -> PulseOps returns execution summary in the webhook response
  -> PulseWatch appends that summary as COMMENT_ADDED
  -> PulseWatch requests Notification Service delivery with the enriched message
  -> PulseWatch audit trail contains enriched response summary
```

## PulseWatch Settings

Add these variables to PulseWatch:

```env
RESPONSE_ORCHESTRATOR_URL=http://pulseops:8000
RESPONSE_ORCHESTRATOR_API_KEY=
RESPONSE_ORCHESTRATOR_TIMEOUT_SECONDS=5

NOTIFICATION_SERVICE_URL=http://notification-service:8000
NOTIFICATION_SERVICE_API_KEY=dev-notification-api-key
NOTIFICATION_USER_ID=1
NOTIFICATION_CHANNEL=telegram
```

PulseWatch should call PulseOps only for `CRITICAL` incidents. The request payload is:

```json
{
  "incident_id": "42",
  "title": "High API latency",
  "description": "P95 latency is above 1500ms",
  "status": "NEW",
  "severity": "CRITICAL",
  "source": "monitoring",
  "target": "renovation-flip-api",
  "fingerprint": "renovation-flip-api:latency:p95",
  "occurrence_count": 1,
  "idempotency_key": "pulsewatch:42:v1",
  "metadata": {
    "pulsewatch_incident_id": 42,
    "pulsewatch_version": 1
  }
}
```

## PulseOps Callback

The current MVP works best when PulseWatch writes the returned summary into its own audit
trail. PulseOps also supports a direct callback for a future async execution mode. Enable
it only when the PulseWatch incident is guaranteed to be committed before the callback:

```env
PULSEOPS_PULSEWATCH_BASE_URL=http://pulsewatch:8000
PULSEOPS_PULSEWATCH_CALLBACK_ENABLED=1
PULSEOPS_PULSEWATCH_SUMMARY_PATH=/api/v1/incidents/{incident_id}/comments
```

The callback body matches PulseWatch `CommentCreate`:

```json
{
  "comment": "CRITICAL: High API latency\n\nSuspected cause: recent_deploy_regression..."
}
```

## Notification Service Payload

PulseWatch sends the final enriched alert to Notification Service using the real
Notification Service REST contract:

```json
{
  "user_id": 1,
  "subject": "CRITICAL: High API latency",
  "message": "CRITICAL: High API latency\n\nIncident: #42\nTarget: renovation-flip-api\n...\n[PulseOps] Response summary\n...",
  "idempotency_key": "pulsewatch:42:v2"
}
```

The Notification Service chooses the actual delivery channel from the target user's
`channel_priority`, so PulseWatch's `NOTIFICATION_CHANNEL` remains local audit metadata
for the `incident_notifications` row rather than a field sent to Notification Service.

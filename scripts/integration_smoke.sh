#!/usr/bin/env bash
set -euo pipefail

PULSEWATCH_URL="${PULSEWATCH_URL:-http://127.0.0.1:8011}"
PULSEOPS_URL="${PULSEOPS_URL:-http://127.0.0.1:8010}"
NOTIFICATION_URL="${NOTIFICATION_URL:-http://127.0.0.1:8020}"
MAILPIT_URL="${MAILPIT_URL:-http://127.0.0.1:8025}"

fingerprint="${1:-renovation-flip-api:latency:p95:$(date +%s)}"

echo "Checking service readiness..."
curl -fsS "$PULSEOPS_URL/health/ready" >/dev/null
curl -fsS "$PULSEWATCH_URL/health/ready" >/dev/null
curl -fsS "$NOTIFICATION_URL/health/ready" >/dev/null

payload="$(
  cat <<JSON
{
  "source": "monitoring",
  "target": "renovation-flip-api",
  "title": "High API latency",
  "description": "P95 latency is above 1500ms",
  "severity": "CRITICAL",
  "fingerprint": "$fingerprint"
}
JSON
)"

echo "Creating CRITICAL PulseWatch signal for fingerprint: $fingerprint"
first_response="$(
  curl -fsS -X POST "$PULSEWATCH_URL/api/v1/signals" \
    -H "Content-Type: application/json" \
    -d "$payload"
)"

incident_id="$(
  printf '%s' "$first_response" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
)"

echo "Incident id: $incident_id"
echo

echo "Repeating the same signal to demonstrate PulseWatch deduplication/PulseOps reuse..."
curl -fsS -X POST "$PULSEWATCH_URL/api/v1/signals" \
  -H "Content-Type: application/json" \
  -d "$payload" >/dev/null

echo
echo "PulseWatch events:"
curl -fsS "$PULSEWATCH_URL/api/v1/incidents/$incident_id/events" \
  | python3 -m json.tool

executions_response="$(
  curl -fsS -G "$PULSEOPS_URL/api/v1/executions" \
    --data-urlencode "fingerprint=$fingerprint" \
    --data-urlencode "limit=1"
)"
execution_id="$(
  printf '%s' "$executions_response" \
    | python3 -c 'import json,sys; items=json.load(sys.stdin); print(items[0]["id"] if items else "")'
)"

if [ -n "$execution_id" ]; then
  echo
  echo "PulseOps execution timeline:"
  curl -fsS "$PULSEOPS_URL/api/v1/executions/$execution_id/timeline" \
    | python3 -m json.tool
fi

echo
echo "PulseWatch notification attempts:"
curl -fsS "$PULSEWATCH_URL/api/v1/incidents/$incident_id/notifications" \
  | python3 -m json.tool

echo
echo "Notification Service Mailpit messages:"
curl -fsS "$MAILPIT_URL/api/v1/messages" \
  | python3 -m json.tool

echo
echo "Open these URLs:"
echo "- PulseWatch: $PULSEWATCH_URL/docs"
echo "- PulseOps: $PULSEOPS_URL/docs"
echo "- Notification Service: $NOTIFICATION_URL/api/docs/"
echo "- Mailpit: $MAILPIT_URL"

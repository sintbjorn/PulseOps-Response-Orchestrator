import os

os.environ.setdefault("PULSEOPS_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("PULSEOPS_AUTO_CREATE_SCHEMA", "1")
os.environ.setdefault("PULSEOPS_SEED_DEMO_DATA", "1")
os.environ.setdefault("PULSEOPS_PULSEWATCH_CALLBACK_ENABLED", "0")
os.environ.setdefault("PULSEOPS_NOTIFICATION_CALLBACK_ENABLED", "0")

from fastapi.testclient import TestClient

from app.entrypoints.api import app
from app.services.integrations import _render_summary_comment


def test_policy_simulation_matches_latency_policy() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/policies/simulate",
            json={
                "severity": "CRITICAL",
                "source": "monitoring",
                "target": "renovation-flip-api",
                "fingerprint": "renovation-flip-api:latency:p95",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_policy"] == "Critical API latency policy"
    assert payload["runbook"] == "High API Latency Diagnostics"
    assert payload["mode"] == "DIAGNOSTIC_ONLY"
    assert "Check API readiness" in payload["would_execute_steps"]
    assert "Find related incidents" in payload["would_execute_steps"]


def test_webhook_executes_and_reuses_recent_summary() -> None:
    incident_payload = {
        "incident_id": "incident-100",
        "title": "High API latency",
        "description": "P95 latency is above 1500ms",
        "status": "NEW",
        "severity": "CRITICAL",
        "source": "monitoring",
        "target": "renovation-flip-api",
        "fingerprint": "renovation-flip-api:latency:p95",
        "metadata": {
            "deploy_version": "1.8.4",
            "metrics": {"5xx_rate": 0.12},
        },
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/webhooks/pulsewatch/incidents", json=incident_payload)
        second = client.post(
            "/api/v1/webhooks/pulsewatch/incidents",
            json={**incident_payload, "incident_id": "incident-101"},
        )

    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["status"] == "SUCCEEDED"
    assert first_payload["runbook_version_id"] is not None
    assert first_payload["suspected_cause"] in {
        "traffic_or_error_rate_regression",
        "recent_deploy_regression",
        "recurring_capacity_or_latency_regression",
    }
    assert first_payload["summary"]["confidence"] > 0
    assert any("5xx" in item for item in first_payload["evidence"])

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["status"] == "REUSED"
    assert second_payload["reused_execution_id"] == first_payload["id"]
    assert second_payload["summary"]["suppression"]["action"] == "reuse"


def test_execution_feedback_loop() -> None:
    with TestClient(app) as client:
        execution = client.post(
            "/api/v1/webhooks/pulsewatch/incidents",
            json={
                "incident_id": "incident-200",
                "title": "High API latency",
                "severity": "CRITICAL",
                "source": "monitoring",
                "target": "renovation-flip-api",
                "fingerprint": "renovation-flip-api:latency:p200",
                "metadata": {"metrics": {"5xx_rate": 0.08}},
            },
        ).json()
        response = client.post(
            f"/api/v1/executions/{execution['id']}/feedback",
            json={
                "rating": "NEEDS_MORE_CONTEXT",
                "comment": "Add deploy owner and dashboard links.",
                "created_by": "operator@example.com",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rating"] == "NEEDS_MORE_CONTEXT"
    assert payload["created_by"] == "operator@example.com"


def test_pulsewatch_summary_comment_respects_comment_limit() -> None:
    comment = _render_summary_comment(
        {
            "headline": "CRITICAL: High API latency",
            "suspected_cause": "recent_deploy_regression",
            "confidence": 0.76,
            "evidence": ["x" * 500 for _ in range(20)],
            "next_action": "Check deploy 1.8.4 and prepare rollback candidate.",
        }
    )

    assert len(comment) <= 2000
    assert comment.endswith("...")

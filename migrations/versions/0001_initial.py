"""Initial PulseOps schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runbooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runbooks_name", "runbooks", ["name"], unique=True)

    op.create_table(
        "runbook_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("runbook_id", sa.Integer(), sa.ForeignKey("runbooks.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("runbook_id", "version", name="uq_runbook_version"),
    )
    op.create_index("ix_runbook_versions_runbook_id", "runbook_versions", ["runbook_id"])

    op.create_table(
        "response_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("target", sa.String(length=160), nullable=True),
        sa.Column("fingerprint", sa.String(length=300), nullable=True),
        sa.Column("fingerprint_contains", sa.String(length=300), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("runbook_id", sa.Integer(), sa.ForeignKey("runbooks.id"), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False),
        sa.Column("max_executions_per_incident", sa.Integer(), nullable=False),
        sa.Column("max_executions_per_fingerprint_per_hour", sa.Integer(), nullable=False),
        sa.Column("reuse_recent_execution", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_response_policies_name", "response_policies", ["name"], unique=True)
    op.create_index("ix_response_policies_enabled", "response_policies", ["enabled"])
    op.create_index("ix_response_policies_priority", "response_policies", ["priority"])
    op.create_index("ix_response_policies_severity", "response_policies", ["severity"])
    op.create_index("ix_response_policies_source", "response_policies", ["source"])
    op.create_index("ix_response_policies_target", "response_policies", ["target"])
    op.create_index("ix_response_policies_fingerprint", "response_policies", ["fingerprint"])
    op.create_index("ix_response_policies_runbook_id", "response_policies", ["runbook_id"])

    op.create_table(
        "service_dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_name", sa.String(length=160), nullable=False),
        sa.Column("dependency_name", sa.String(length=160), nullable=False),
        sa.Column("dependency_type", sa.String(length=40), nullable=False),
        sa.Column("healthcheck_url", sa.String(length=600), nullable=True),
        sa.Column("criticality", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("service_name", "dependency_name", name="uq_service_dependency_name"),
    )
    op.create_index(
        "ix_service_dependencies_service_name",
        "service_dependencies",
        ["service_name"],
    )
    op.create_index(
        "ix_service_dependencies_dependency_name",
        "service_dependencies",
        ["dependency_name"],
    )

    op.create_table(
        "executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("incident_id", sa.String(length=80), nullable=True),
        sa.Column("fingerprint", sa.String(length=300), nullable=False),
        sa.Column("target", sa.String(length=160), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("response_policies.id"), nullable=True),
        sa.Column("runbook_id", sa.Integer(), sa.ForeignKey("runbooks.id"), nullable=True),
        sa.Column(
            "runbook_version_id",
            sa.Integer(),
            sa.ForeignKey("runbook_versions.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=True),
        sa.Column("idempotency_key", sa.String(length=300), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("suspected_cause", sa.String(length=120), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("reused_execution_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_executions_incident_id", "executions", ["incident_id"])
    op.create_index("ix_executions_fingerprint", "executions", ["fingerprint"])
    op.create_index("ix_executions_target", "executions", ["target"])
    op.create_index("ix_executions_severity", "executions", ["severity"])
    op.create_index("ix_executions_source", "executions", ["source"])
    op.create_index("ix_executions_runbook_version_id", "executions", ["runbook_version_id"])
    op.create_index("ix_executions_status", "executions", ["status"])
    op.create_index("ix_executions_idempotency_key", "executions", ["idempotency_key"], unique=True)
    op.create_index("ix_executions_reused_execution_id", "executions", ["reused_execution_id"])
    op.create_index("ix_executions_created_at", "executions", ["created_at"])

    op.create_table(
        "execution_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.String(length=36),
            sa.ForeignKey("executions.id"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("step_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requires_operator", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("execution_id", "step_order", name="uq_execution_step_order"),
    )
    op.create_index("ix_execution_steps_execution_id", "execution_steps", ["execution_id"])
    op.create_index("ix_execution_steps_status", "execution_steps", ["status"])

    op.create_table(
        "execution_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.String(length=36),
            sa.ForeignKey("executions.id"),
            nullable=False,
        ),
        sa.Column("rating", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_execution_feedback_execution_id", "execution_feedback", ["execution_id"])


def downgrade() -> None:
    op.drop_table("execution_feedback")
    op.drop_table("execution_steps")
    op.drop_table("executions")
    op.drop_table("service_dependencies")
    op.drop_table("response_policies")
    op.drop_table("runbook_versions")
    op.drop_table("runbooks")

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import (
    DependencyCriticality,
    DependencyType,
    ExecutionStatus,
    FeedbackRating,
    PolicyMode,
    RunbookStepType,
    StepStatus,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Runbook(Base):
    __tablename__ = "runbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    versions: Mapped[list["RunbookVersion"]] = relationship(
        back_populates="runbook",
        cascade="all, delete-orphan",
        order_by="RunbookVersion.version",
    )
    policies: Mapped[list["ResponsePolicy"]] = relationship(back_populates="runbook")


class RunbookVersion(Base):
    __tablename__ = "runbook_versions"
    __table_args__ = (UniqueConstraint("runbook_id", "version", name="uq_runbook_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    runbook_id: Mapped[int] = mapped_column(ForeignKey("runbooks.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(120), default="system")
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    runbook: Mapped[Runbook] = relationship(back_populates="versions")
    executions: Mapped[list["Execution"]] = relationship(back_populates="runbook_version")


class ResponsePolicy(Base):
    __tablename__ = "response_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)

    severity: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    target: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    fingerprint_contains: Mapped[str | None] = mapped_column(String(300), nullable=True)

    mode: Mapped[str] = mapped_column(String(40), default=PolicyMode.DIAGNOSTIC_ONLY.value)
    runbook_id: Mapped[int] = mapped_column(ForeignKey("runbooks.id"), index=True)

    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    max_executions_per_incident: Mapped[int] = mapped_column(Integer, default=1)
    max_executions_per_fingerprint_per_hour: Mapped[int] = mapped_column(Integer, default=3)
    reuse_recent_execution: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    runbook: Mapped[Runbook] = relationship(back_populates="policies")
    executions: Mapped[list["Execution"]] = relationship(back_populates="policy")


class ServiceDependency(Base):
    __tablename__ = "service_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "service_name",
            "dependency_name",
            name="uq_service_dependency_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_name: Mapped[str] = mapped_column(String(160), index=True)
    dependency_name: Mapped[str] = mapped_column(String(160), index=True)
    dependency_type: Mapped[str] = mapped_column(
        String(40),
        default=DependencyType.INTERNAL_SERVICE.value,
    )
    healthcheck_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    criticality: Mapped[str] = mapped_column(
        String(40),
        default=DependencyCriticality.REQUIRED.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    incident_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    fingerprint: Mapped[str] = mapped_column(String(300), index=True)
    target: Mapped[str] = mapped_column(String(160), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    policy_id: Mapped[int | None] = mapped_column(ForeignKey("response_policies.id"), nullable=True)
    runbook_id: Mapped[int | None] = mapped_column(ForeignKey("runbooks.id"), nullable=True)
    runbook_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("runbook_versions.id"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        default=ExecutionStatus.RUNNING.value,
        index=True,
    )
    mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(300), unique=True, nullable=True)

    context: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    suspected_cause: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    reused_execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        index=True,
    )

    policy: Mapped[ResponsePolicy | None] = relationship(back_populates="executions")
    runbook_version: Mapped[RunbookVersion | None] = relationship(back_populates="executions")
    steps: Mapped[list["ExecutionStep"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionStep.step_order",
    )
    feedback: Mapped[list["ExecutionFeedback"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionFeedback.created_at",
    )


class ExecutionStep(Base):
    __tablename__ = "execution_steps"
    __table_args__ = (
        UniqueConstraint("execution_id", "step_order", name="uq_execution_step_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    step_type: Mapped[str] = mapped_column(String(40), default=RunbookStepType.STATIC_HINT.value)
    status: Mapped[str] = mapped_column(String(40), default=StepStatus.PENDING.value, index=True)
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_operator: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    execution: Mapped[Execution] = relationship(back_populates="steps")


class ExecutionFeedback(Base):
    __tablename__ = "execution_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    rating: Mapped[str] = mapped_column(String(40), default=FeedbackRating.HELPFUL.value)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    execution: Mapped[Execution] = relationship(back_populates="feedback")

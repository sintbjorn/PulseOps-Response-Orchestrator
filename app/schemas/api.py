from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ExecutionStatus, FeedbackRating, PolicyMode, Severity, StepStatus


class IncidentInput(BaseModel):
    incident_id: str | None = None
    title: str | None = None
    description: str | None = None
    status: str | None = None
    severity: Severity
    source: str | None = None
    target: str
    fingerprint: str
    occurrence_count: int | None = None
    last_seen_at: datetime | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicySimulationRequest(BaseModel):
    severity: Severity
    source: str | None = None
    target: str
    fingerprint: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicySimulationResponse(BaseModel):
    matched_policy: str | None
    runbook: str | None
    runbook_version: int | None
    mode: PolicyMode | None
    would_execute_steps: list[str]
    suppression: dict[str, Any] = Field(default_factory=dict)
    context_notes: list[str] = Field(default_factory=list)


class StepRead(BaseModel):
    id: int
    step_order: int
    name: str
    step_type: str
    status: StepStatus
    input: dict[str, Any]
    output: dict[str, Any]
    error: str | None
    requires_operator: bool
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class FeedbackRead(BaseModel):
    id: int
    execution_id: str
    rating: FeedbackRating
    comment: str | None
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionRead(BaseModel):
    id: str
    incident_id: str | None
    fingerprint: str
    target: str
    severity: Severity
    source: str | None
    policy_id: int | None
    runbook_id: int | None
    runbook_version_id: int | None
    status: ExecutionStatus
    mode: PolicyMode | None
    context: dict[str, Any]
    summary: dict[str, Any]
    suspected_cause: str | None
    confidence: float
    evidence: list[Any]
    reused_execution_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    steps: list[StepRead] = Field(default_factory=list)
    feedback: list[FeedbackRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ExecutionTimelineEvent(BaseModel):
    event_type: str
    title: str
    status: str | None = None
    actor: str = "pulseops"
    occurred_at: datetime | None = None
    duration_ms: float | None = None
    related_step_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionTimelineRead(BaseModel):
    execution_id: str
    incident_id: str | None
    fingerprint: str
    target: str
    severity: Severity
    status: ExecutionStatus
    generated_at: datetime
    events: list[ExecutionTimelineEvent]


class ExecutionFeedbackCreate(BaseModel):
    rating: FeedbackRating
    comment: str | None = None
    created_by: str = "operator"


class ManualStepCompleteRequest(BaseModel):
    output: dict[str, Any] = Field(default_factory=dict)
    comment: str | None = None


class RunbookVersionRead(BaseModel):
    id: int
    runbook_id: int
    version: int
    definition: dict[str, Any]
    created_by: str
    changelog: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunbookRead(BaseModel):
    id: int
    name: str
    current_version: int
    versions: list[RunbookVersionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ResponsePolicyRead(BaseModel):
    id: int
    name: str
    description: str | None
    enabled: bool
    priority: int
    severity: str | None
    source: str | None
    target: str | None
    fingerprint: str | None
    fingerprint_contains: str | None
    mode: PolicyMode
    runbook_id: int
    cooldown_seconds: int
    max_executions_per_incident: int
    max_executions_per_fingerprint_per_hour: int
    reuse_recent_execution: bool

    model_config = ConfigDict(from_attributes=True)

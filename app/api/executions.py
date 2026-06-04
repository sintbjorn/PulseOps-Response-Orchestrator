from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.domain.models import Execution, RunbookVersion
from app.schemas.api import (
    ExecutionFeedbackCreate,
    ExecutionRead,
    ExecutionTimelineRead,
    FeedbackRead,
    ManualStepCompleteRequest,
    StepRead,
)
from app.services.executor import complete_manual_step, create_execution_feedback
from app.services.timeline import build_execution_timeline

router = APIRouter(prefix="/api/v1", tags=["executions"])


@router.get("/executions", response_model=list[ExecutionRead])
def list_executions(
    fingerprint: str | None = None,
    incident_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Execution]:
    query = select(Execution).order_by(Execution.created_at.desc()).limit(limit).offset(offset)
    if fingerprint:
        query = query.where(Execution.fingerprint == fingerprint)
    if incident_id:
        query = query.where(Execution.incident_id == incident_id)
    if status:
        query = query.where(Execution.status == status)
    return list(db.scalars(query).all())


@router.get("/executions/{execution_id}", response_model=ExecutionRead)
def get_execution(execution_id: str, db: Session = Depends(get_db)) -> Execution:
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return execution


@router.get("/executions/{execution_id}/timeline", response_model=ExecutionTimelineRead)
def get_execution_timeline(
    execution_id: str,
    db: Session = Depends(get_db),
) -> ExecutionTimelineRead:
    execution = db.scalar(
        select(Execution)
        .where(Execution.id == execution_id)
        .options(
            selectinload(Execution.policy),
            selectinload(Execution.runbook_version).selectinload(RunbookVersion.runbook),
            selectinload(Execution.steps),
            selectinload(Execution.feedback),
        )
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return build_execution_timeline(execution)


@router.post("/executions/{execution_id}/feedback", response_model=FeedbackRead)
def add_feedback(
    execution_id: str,
    request: ExecutionFeedbackCreate,
    db: Session = Depends(get_db),
):
    feedback = create_execution_feedback(db, execution_id, request)
    if feedback is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return feedback


@router.post("/steps/{step_id}/complete", response_model=StepRead)
def complete_step(
    step_id: int,
    request: ManualStepCompleteRequest,
    db: Session = Depends(get_db),
):
    step = complete_manual_step(db, step_id, request)
    if step is None:
        raise HTTPException(status_code=404, detail="step not found")
    return step
